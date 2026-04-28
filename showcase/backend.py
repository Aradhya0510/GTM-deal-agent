"""Backend infrastructure — no Streamlit dependency. Databricks WorkspaceClient, SQL, agent endpoint, streaming, MLflow, Lakebase."""

import json
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

ENDPOINT_NAME = os.environ.get("GTM_ENDPOINT", "")
CATALOG = os.environ.get("UC_CATALOG", "")
SCHEMA = os.environ.get("UC_SCHEMA", "")
SQL_WAREHOUSE_ID = os.environ.get("SQL_WAREHOUSE_ID", "")
WORKSPACE_URL = os.environ.get("DATABRICKS_HOST", "")
WORKSPACE_ID = os.environ.get("DATABRICKS_WORKSPACE_ID", "")
LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "")
EMBEDDING_ENDPOINT = os.environ.get("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")

AE_PROFILES = {
    "Jamie Torres": {"email": "ae-jamie@company.com", "id": "ae-jamie"},
    "Sarah Kim": {"email": "ae-sarah@company.com", "id": "ae-sarah"},
    "(None — no memory)": {"email": "", "id": ""},
}

_sql_cache: dict[str, tuple[float, list[dict]]] = {}
_SQL_CACHE_TTL = 60

# Lakebase DatabricksStore for reading memory in the showcase app.
#
# Auth strategy: the App's Service Principal does not always get an
# auto-provisioned Postgres role on its host Lakebase instance, which causes
# `password authentication failed for user '<sp-uuid>'`. To work around that,
# if LAKEBASE_PAT is provided (typically via a Databricks Secret resource
# wired through app.yaml `valueFrom`), we use it to authenticate as the PAT
# owner — same pattern the agent uses on Model Serving.
_lakebase_store = None
_LAKEBASE_READY = False
try:
    from databricks_langchain import DatabricksStore
    from databricks.sdk import WorkspaceClient as _LBWorkspaceClient
    from databricks.sdk.config import Config as _LBConfig

    _lb_kwargs = {"instance_name": LAKEBASE_INSTANCE_NAME}
    _lakebase_token = os.environ.get("LAKEBASE_PAT")
    _lakebase_host = os.environ.get("DATABRICKS_HOST", "")
    if _lakebase_token:
        # Force PAT auth explicitly. On Databricks Apps, DATABRICKS_CLIENT_ID
        # and DATABRICKS_CLIENT_SECRET are auto-injected for the App SP, so
        # the default WorkspaceClient resolver sees BOTH PAT and OAuth and
        # raises "more than one authorization method configured". auth_type
        # locks the resolver to PAT only.
        _lb_cfg = _LBConfig(
            host=_lakebase_host,
            token=_lakebase_token,
            auth_type="pat",
            client_id=None,
            client_secret=None,
        )
        _lb_wc = _LBWorkspaceClient(config=_lb_cfg)
        _lb_kwargs["workspace_client"] = _lb_wc
        logger.info("Showcase app: using explicit LAKEBASE_PAT for Lakebase auth")
    else:
        logger.info("Showcase app: using App SP for Lakebase auth (no LAKEBASE_PAT set)")

    _lakebase_store = DatabricksStore(
        **_lb_kwargs,
        embedding_endpoint=EMBEDDING_ENDPOINT,
        embedding_dims=1024,
    )
    _LAKEBASE_READY = True
    logger.info("Showcase app connected to Lakebase instance: %s", LAKEBASE_INSTANCE_NAME)
except Exception as e:
    logger.warning("Lakebase DatabricksStore not available in showcase app: %s", e)


def invalidate_sql_cache():
    """Clear the SQL cache so Observatory shows fresh data after agent interactions."""
    _sql_cache.clear()


def _get_workspace_client():
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.config import Config
    return WorkspaceClient(config=Config(http_timeout_seconds=300))


# ── SQL ──
def run_app_sql(statement: str, params: list[dict] | None = None) -> list[dict]:
    cache_key = statement + (json.dumps(params, sort_keys=True) if params else "")
    now = time.time()
    if cache_key in _sql_cache:
        cached_at, result = _sql_cache[cache_key]
        if now - cached_at < _SQL_CACHE_TTL:
            return result
    try:
        w = _get_workspace_client()
        exec_kwargs = {"statement": statement, "warehouse_id": SQL_WAREHOUSE_ID, "wait_timeout": "30s"}
        if params:
            from databricks.sdk.service.sql import StatementParameterListItem
            exec_kwargs["parameters"] = [StatementParameterListItem(**p) for p in params]
        resp = w.statement_execution.execute_statement(**exec_kwargs)
        if resp.status and resp.status.state and resp.status.state.value == "SUCCEEDED":
            if not resp.result or not resp.result.data_array:
                _sql_cache[cache_key] = (now, [])
                return []
            columns = [c.name for c in resp.manifest.schema.columns]
            result = [dict(zip(columns, row)) for row in resp.result.data_array]
            _sql_cache[cache_key] = (now, result)
            return result
        _sql_cache[cache_key] = (now, [])
        return []
    except Exception:
        return []


# ── Agent (blocking) ──
def query_agent(conversation: list[dict], thread_id: str, ae_id: str = "", account_id: str = "") -> dict:
    w = _get_workspace_client()
    input_messages = [{"role": m["role"], "content": m["content"]} for m in conversation if m["role"] in ("user", "assistant") and m.get("content")]
    save = bool(ae_id)
    body = {"input": input_messages, "custom_inputs": {"thread_id": thread_id, "ae_id": ae_id, "save_memories": save}}
    if account_id:
        body["custom_inputs"]["account_id"] = account_id
    return w.api_client.do("POST", f"/serving-endpoints/{ENDPOINT_NAME}/invocations", body=body)


# ── Agent (streaming via DatabricksOpenAI) ──
def query_agent_stream(conversation: list[dict], thread_id: str, ae_id: str = "", account_id: str = ""):
    """Stream agent via DatabricksOpenAI SDK. Yields normalized dicts. Falls back to blocking on error."""
    from databricks_openai import DatabricksOpenAI

    w = _get_workspace_client()
    client = DatabricksOpenAI(workspace_client=w)
    input_messages = [{"role": m["role"], "content": m["content"]} for m in conversation if m["role"] in ("user", "assistant") and m.get("content")]
    save = bool(ae_id)
    custom_inputs = {"thread_id": thread_id, "ae_id": ae_id, "save_memories": save}
    if account_id:
        custom_inputs["account_id"] = account_id

    try:
        stream = client.responses.create(
            model=ENDPOINT_NAME,
            input=input_messages,
            stream=True,
            extra_body={"custom_inputs": custom_inputs},
        )
        for chunk in stream:
            event = {"type": getattr(chunk, "type", None)}
            item = getattr(chunk, "item", None)
            if item is not None:
                event["item"] = item.model_dump() if hasattr(item, "model_dump") else (dict(item) if isinstance(item, dict) else {"raw": str(item)})
            yield event
    except Exception:
        result = query_agent(conversation, thread_id, ae_id, account_id)
        for item in result.get("output", []):
            yield {"type": "response.output_item.done", "item": item}


# ── Response parsing ──
def extract_text(response: dict) -> str:
    texts = []
    for item in response.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content["text"])
    return "\n".join(texts) if texts else ""


def extract_tool_calls(response: dict) -> list[dict]:
    calls = {}
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            cid = item.get("call_id", item.get("id", str(uuid.uuid4())))
            calls[cid] = {"name": item.get("name", "unknown"), "arguments": item.get("arguments", ""), "call_id": cid, "output": None}
        elif item.get("type") == "function_call_output":
            cid = item.get("call_id", "")
            if cid in calls:
                calls[cid]["output"] = item.get("output", "")
    return list(calls.values())


# ── Error classification ──
def format_agent_error(e: Exception) -> tuple[str, str]:
    """Classify an agent exception into (friendly_message, raw_detail)."""
    raw = f"{type(e).__name__}: {e}"
    name_lower = type(e).__name__.lower()
    msg_lower = str(e).lower()
    if "timeout" in name_lower or "timeout" in msg_lower or "timed out" in msg_lower:
        return "Agent request timed out. The endpoint may be cold-starting — try again in 30s.", raw
    if "status" in name_lower or "http" in name_lower:
        return "Agent endpoint returned an error. It may be temporarily unavailable.", raw
    if "connection" in name_lower or "connection" in msg_lower:
        return "Could not connect to the agent endpoint. Check network and endpoint status.", raw
    return "An unexpected error occurred while calling the agent.", raw


# ── Tool classification ──
def classify_tool(name: str) -> str:
    if "lakebase" in name.lower() or "memory" in name.lower():
        return "memory"
    if "deal_health" in name or "account_signals" in name:
        return "scoring"
    if "transcripts" in name or "battlecards" in name or "stories" in name:
        return "research"
    return "memory"

def tool_type_label(name: str) -> str:
    if "lakebase" in name.lower() or "memory" in name.lower():
        return "Lakebase"
    if "deal_health" in name or "account_signals" in name:
        return "UC Function"
    if "transcripts" in name or "battlecards" in name or "stories" in name:
        return "Vector Search"
    return "Tool"

def tool_color(name: str) -> str:
    return {"memory": "violet", "scoring": "amber", "research": "cyan"}.get(classify_tool(name), "txt2")


# ── AI Gateway stats ──
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "databricks-claude-sonnet-4-6")
_gw_cache: dict[str, tuple[float, dict]] = {}

def fetch_ai_gateway_stats() -> dict:
    now = time.time()
    if "gw" in _gw_cache:
        cached_at, result = _gw_cache["gw"]
        if now - cached_at < 120:
            return result
    try:
        rows = run_app_sql(
            "SELECT eu.request_time, eu.status_code, eu.input_token_count, eu.output_token_count, "
            "eu.requester, eu.request_streaming, se.endpoint_name "
            "FROM system.serving.endpoint_usage eu "
            "JOIN system.serving.served_entities se ON eu.served_entity_id = se.served_entity_id "
            f"WHERE se.endpoint_name = '{LLM_ENDPOINT}' "
            "AND eu.request_time > current_timestamp() - INTERVAL 24 HOURS "
            "ORDER BY eu.request_time DESC LIMIT 50"
        )
        total = len(rows)
        in_tok = sum(int(r.get("input_token_count", 0) or 0) for r in rows)
        out_tok = sum(int(r.get("output_token_count", 0) or 0) for r in rows)
        rate_limited = sum(1 for r in rows if str(r.get("status_code", "")) == "429")
        avg_tok = (in_tok + out_tok) // max(total, 1)
        recent = []
        for r in rows[:10]:
            recent.append({
                "time": str(r.get("request_time", ""))[:19].replace("T", " "),
                "status": str(r.get("status_code", "")),
                "in_tok": r.get("input_token_count", "0"),
                "out_tok": r.get("output_token_count", "0"),
                "requester": str(r.get("requester", ""))[:24],
            })
        result = {
            "total_requests": total, "total_input_tokens": in_tok, "total_output_tokens": out_tok,
            "rate_limited_count": rate_limited, "avg_tokens_per_request": avg_tok,
            "recent_requests": recent,
        }
        _gw_cache["gw"] = (now, result)
        return result
    except Exception:
        return {"total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0,
                "rate_limited_count": 0, "avg_tokens_per_request": 0, "recent_requests": []}


# ── MLflow experiment stats ──
_mlflow_cache: dict[str, tuple[float, dict]] = {}

def fetch_mlflow_experiment_stats() -> dict:
    now = time.time()
    if "mlflow" in _mlflow_cache:
        cached_at, result = _mlflow_cache["mlflow"]
        if now - cached_at < 120:
            return result
    try:
        w = _get_workspace_client()
        experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "/Users/default/gtm-deal-intelligence")
        exp_resp = w.api_client.do("GET", "/api/2.0/mlflow/experiments/get-by-name",
                                    query={"experiment_name": experiment_name})
        exp_id = exp_resp.get("experiment", {}).get("experiment_id")
        if not exp_id:
            return {"run_count": 0, "recent_runs": [], "experiment_id": None}
        runs_resp = w.api_client.do("POST", "/api/2.0/mlflow/runs/search", body={
            "experiment_ids": [exp_id], "max_results": 10, "order_by": ["start_time DESC"]})
        runs = runs_resp.get("runs", [])
        recent = []
        for r in runs[:10]:
            info = r.get("info", {})
            recent.append({
                "run_id": info.get("run_id", "")[:8],
                "status": info.get("status", "UNKNOWN"),
                "start_time": info.get("start_time", 0),
                "duration_ms": (info.get("end_time", 0) or 0) - (info.get("start_time", 0) or 0),
            })
        result = {"run_count": len(runs), "recent_runs": recent, "experiment_id": exp_id}
        _mlflow_cache["mlflow"] = (now, result)
        return result
    except Exception:
        return {"run_count": 0, "recent_runs": [], "experiment_id": None}


# ── Lakebase memory queries ──
_mem_cache: dict[str, tuple[float, list[dict]]] = {}
_MEM_CACHE_TTL = 60


def fetch_lakebase_memories(ae_id: str, namespace_type: str = "ae_memories", query: str = "preferences", limit: int = 10) -> list[dict]:
    """Query Lakebase DatabricksStore for memory items."""
    if not _LAKEBASE_READY or not _lakebase_store or not ae_id:
        return []
    cache_key = f"{namespace_type}:{ae_id}:{query}:{limit}"
    now = time.time()
    if cache_key in _mem_cache:
        cached_at, result = _mem_cache[cache_key]
        if now - cached_at < _MEM_CACHE_TTL:
            return result
    try:
        results = _lakebase_store.search((namespace_type, ae_id), query=query, limit=limit)
        items = [{"key": item.key, **item.value} for item in results]
        _mem_cache[cache_key] = (now, items)
        return items
    except Exception as e:
        logger.warning("Lakebase memory query failed: %s", e)
        return []


def invalidate_memory_cache():
    _mem_cache.clear()
