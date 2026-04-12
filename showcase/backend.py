"""Backend infrastructure — no Streamlit dependency. Databricks WorkspaceClient, SQL, agent endpoint, streaming, MLflow."""

import json
import os
import time
import uuid

ENDPOINT_NAME = os.environ.get("GTM_ENDPOINT", "agents_users-aradhya_chouhan-gtm_deal_intelligence_agent")
CATALOG = "users"
SCHEMA = "aradhya_chouhan"
SQL_WAREHOUSE_ID = "75fd8278393d07eb"
WORKSPACE_URL = "https://e2-demo-west.cloud.databricks.com"
WORKSPACE_ID = "2556758628403379"

AE_PROFILES = {
    "Jamie Torres": {"email": "ae-jamie@company.com", "id": "ae-jamie"},
    "Sarah Kim": {"email": "ae-sarah@company.com", "id": "ae-sarah"},
    "(None — no memory)": {"email": "", "id": ""},
}

_sql_cache: dict[str, tuple[float, list[dict]]] = {}
_SQL_CACHE_TTL = 60


def _get_workspace_client():
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.config import Config
    return WorkspaceClient(config=Config(http_timeout_seconds=300))


# ── SQL ──
def run_app_sql(statement: str) -> list[dict]:
    now = time.time()
    if statement in _sql_cache:
        cached_at, result = _sql_cache[statement]
        if now - cached_at < _SQL_CACHE_TTL:
            return result
    try:
        w = _get_workspace_client()
        resp = w.statement_execution.execute_statement(statement=statement, warehouse_id=SQL_WAREHOUSE_ID, wait_timeout="30s")
        if resp.status and resp.status.state and resp.status.state.value == "SUCCEEDED":
            if not resp.result or not resp.result.data_array:
                _sql_cache[statement] = (now, [])
                return []
            columns = [c.name for c in resp.manifest.schema.columns]
            result = [dict(zip(columns, row)) for row in resp.result.data_array]
            _sql_cache[statement] = (now, result)
            return result
        _sql_cache[statement] = (now, [])
        return []
    except Exception:
        return []


# ── Agent (blocking) ──
def query_agent(conversation: list[dict], thread_id: str, ae_id: str = "", account_id: str = "") -> dict:
    w = _get_workspace_client()
    input_messages = [{"role": m["role"], "content": m["content"]} for m in conversation if m["role"] in ("user", "assistant") and m.get("content")]
    body = {"input": input_messages, "custom_inputs": {"thread_id": thread_id, "ae_id": ae_id, "save_memories": False}}
    if account_id:
        body["custom_inputs"]["account_id"] = account_id
    return w.api_client.do("POST", f"/serving-endpoints/{ENDPOINT_NAME}/invocations", body=body)


# ── Agent (streaming SSE) ──
def query_agent_stream(conversation: list[dict], thread_id: str, ae_id: str = "", account_id: str = ""):
    """Stream agent response via SSE. Yields dicts (parsed events). Falls back to blocking on error."""
    import requests as _requests

    w = _get_workspace_client()
    input_messages = [{"role": m["role"], "content": m["content"]} for m in conversation if m["role"] in ("user", "assistant") and m.get("content")]
    body = {"input": input_messages, "custom_inputs": {"thread_id": thread_id, "ae_id": ae_id, "save_memories": False}}
    if account_id:
        body["custom_inputs"]["account_id"] = account_id

    url = f"{w.config.host}/serving-endpoints/{ENDPOINT_NAME}/invocations"
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    try:
        auth_headers = w.config.authenticate()
        headers.update(auth_headers)
    except Exception:
        # Fallback: try getting token from config directly
        if w.config.token:
            headers["Authorization"] = f"Bearer {w.config.token}"

    try:
        resp = _requests.post(url, json=body, headers=headers, stream=True, timeout=300)
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    continue
    except Exception:
        # Fallback: blocking call, yield items as if streamed
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
        exp_resp = w.api_client.do("GET", "/api/2.0/mlflow/experiments/get-by-name",
                                    query={"experiment_name": "/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence"})
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
