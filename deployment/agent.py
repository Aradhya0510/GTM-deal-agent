"""
GTM Deal Intelligence Agent — Standalone agent definition with Lakebase memory.

This file is loaded by MLflow Model Serving. It contains ONLY the agent
definition and set_model() — NO logging, testing, or deployment code.

Memory Architecture:
  Short-term: Lakebase CheckpointSaver (cross-replica session persistence)
              Falls back to MemorySaver if Lakebase not available
  Long-term:  Lakebase memory tools — recall_lakebase_memory / store_lakebase_memory
              Backed by Delta tables queried via SQL Statement Execution API

Databricks tech: LangGraph + ChatDatabricks + UC Functions + Vector Search + Lakebase + SQL API
"""

import json
import logging
import re
import time
import uuid

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)
from databricks_langchain import ChatDatabricks, UCFunctionToolkit, VectorSearchRetrieverTool
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from typing import Annotated, Generator, Sequence, TypedDict

logger = logging.getLogger(__name__)

# ── Lakebase CheckpointSaver (with MemorySaver fallback) ──────────────────
try:
    from databricks.agents.lakebase import CheckpointSaver
    _checkpointer = CheckpointSaver()
    _LAKEBASE_CHECKPOINT = True
    logger.info("Lakebase CheckpointSaver loaded — cross-replica session memory active")
except (ImportError, Exception) as e:
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()
    _LAKEBASE_CHECKPOINT = False
    logger.info("Lakebase CheckpointSaver not available (%s) — using MemorySaver fallback", e)

# ── SQL API for Lakebase memory tables ────────────────────────────────────
try:
    from databricks.sdk import WorkspaceClient
    _SQL_AVAILABLE = True
except ImportError:
    _SQL_AVAILABLE = False
    logger.info("databricks.sdk not available — Lakebase memory tools disabled")

# ── Configuration ────────────────────────────────────────────────────────
CATALOG = "users"
SCHEMA = "aradhya_chouhan"
LLM_ENDPOINT = "databricks-claude-sonnet-4-6"
MEMORY_LLM_ENDPOINT = "databricks-claude-haiku-4-5"
SQL_WAREHOUSE_ID = "75fd8278393d07eb"  # Shared Endpoint on e2-demo-west

SYSTEM_PROMPT = """You are an expert GTM Deal Intelligence assistant for B2B SaaS account executives.

You have access to:
- **Lakebase Memory** via recall_lakebase_memory — ALWAYS call this FIRST to load AE preferences and account context from prior sessions
- Live CRM data via get_account_signals (UC Function on serverless SQL)
- Deal health scoring via calculate_deal_health (UC Function — scores 0-100 with risk flags)
- Gong call transcripts via Vector Search (semantic retrieval over recent calls)
- Competitive battlecards via Vector Search (ServiceNow, BMC, Splunk/Palo Alto, Zendesk/Freshworks)
- Won/lost deal stories via Vector Search (historical deals for proof points)
- **Lakebase Memory** via store_lakebase_memory — store new facts learned during the conversation

CRITICAL WORKFLOW — follow this order for EVERY query:
1. ALWAYS call recall_lakebase_memory FIRST with the AE ID to load their preferences and context
2. Call get_account_signals to get the full account picture
3. Call calculate_deal_health to get the quantitative score and risk flags
4. Search call transcripts for recent conversation context
5. For outreach drafts, search battlecards and deal stories for competitive intel and proof points
6. ALWAYS call store_lakebase_memory when the AE shares ANY preference, correction, or feedback:
   - New style preference → fact_type="ae_preference", content="preference_type:value" (e.g. "email_tone:casual")
   - Account insight → fact_type="account_context", include account_id
   - Deal decision (accept/reject/modify a recommendation) → fact_type="deal_decision"
   Do NOT skip this step. Memory persistence is critical for cross-session continuity.

Apply all preferences from Lakebase memory silently (email length, tone, competitors to avoid, etc.).

When drafting outreach:
- Reference specific insights from recent calls (use names and dates)
- Connect product usage or engagement patterns to business outcomes
- Include one relevant proof point from a similar customer
- Single clear CTA relevant to the deal stage
- Keep emails under 150 words unless memory says otherwise

Be specific. Cite names, dates, numbers, and scores. Never use generic filler.
Format deal health as a clear scorecard with risk flags called out."""

MEMORY_EXTRACTION_PROMPT = """\
You are a memory extraction specialist for a GTM sales AI system.

Given a full conversation between a sales AE and the deal intelligence agent,
extract ONLY concrete, reusable facts. Skip vague or obvious statements.

Return a JSON object with exactly three keys:

"ae_preferences": list of AE-specific preferences discovered.
  Each: {"preference_type": str, "value": str, "confidence": float 0-1}
  Examples:
    {"preference_type": "email_max_words", "value": "150", "confidence": 0.95}
    {"preference_type": "avoid_competitor_mention", "value": "ServiceNow", "confidence": 0.90}
    {"preference_type": "preferred_cta", "value": "15-minute discovery call", "confidence": 0.85}
    {"preference_type": "email_tone", "value": "direct, no fluff", "confidence": 0.92}

"account_context": list of account-specific insights surfaced by the AE.
  Each: {"account_id": str, "context_type": str, "content": str, "confidence": float 0-1}
  context_type values: champion_change, budget_freeze, competitor_mentioned,
                       org_change, timeline_shift, technical_requirement, sentiment_shift

"deal_decisions": list of recommendations the AE accepted, modified, or rejected.
  Each: {"opp_id": str, "recommendation": str, "ae_action": str, "ae_feedback": str}
  ae_action values: accepted, modified, rejected

Return ONLY valid JSON. No preamble, no explanation, no markdown fencing."""


# ── SQL helper ────────────────────────────────────────────────────────────
class _SqlResult:
    """Wraps SQL execution outcome so callers can distinguish success from failure.

    Truthiness checks row count (backward compat with recall code that does `if rows:`).
    Use `.ok` explicitly for DML success checks in store operations.
    """
    __slots__ = ("ok", "rows", "error")

    def __init__(self, ok: bool, rows: list[dict] | None = None, error: str = ""):
        self.ok = ok
        self.rows = rows or []
        self.error = error

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        return self.rows[idx]

    def __bool__(self):
        return bool(self.rows)


def _get_sql_client():
    """Get a WorkspaceClient for SQL operations.

    Uses explicit PAT credentials (via LAKEBASE_SQL_TOKEN env var) for write operations,
    because the auto-auth passthrough SP only gets read access to DatabricksTable resources.
    Falls back to default WorkspaceClient (auto-auth) if no explicit token is set.
    """
    import os
    token = os.environ.get("LAKEBASE_SQL_TOKEN")
    host = os.environ.get("DATABRICKS_HOST", "https://e2-demo-west.cloud.databricks.com")
    if token:
        return WorkspaceClient(host=host, token=token)
    return WorkspaceClient()


def _run_sql(statement: str) -> _SqlResult:
    """Execute SQL via Databricks SQL Statement Execution API (Lakebase backend)."""
    if not _SQL_AVAILABLE:
        return _SqlResult(False, error="SDK not available")
    try:
        w = _get_sql_client()
        resp = w.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=SQL_WAREHOUSE_ID,
            wait_timeout="30s",
        )
        if resp.status and resp.status.state and resp.status.state.value == "SUCCEEDED":
            if not resp.result or not resp.result.data_array:
                return _SqlResult(True, [])
            columns = [c.name for c in resp.manifest.schema.columns]
            return _SqlResult(True, [dict(zip(columns, row)) for row in resp.result.data_array])
        else:
            err = str(resp.status) if resp.status else "unknown"
            logger.warning("SQL execution failed: %s", err)
            return _SqlResult(False, error=err)
    except Exception as e:
        logger.warning("SQL execution error", exc_info=True)
        return _SqlResult(False, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  LAKEBASE MEMORY TOOLS — visible as tool calls in the agent output
# ═══════════════════════════════════════════════════════════════════════════

@tool
def recall_lakebase_memory(ae_id: str, account_id: str = "") -> str:
    """Load AE preferences, account context, and deal decisions from Lakebase memory tables.

    ALWAYS call this tool FIRST before answering any question. It retrieves:
    - AE email preferences (tone, length, CTA, competitors to avoid)
    - Account-specific context (champion changes, budget, competitor intel)
    - Recent deal decision history (what recommendations were accepted/rejected)

    Args:
        ae_id: The AE identifier (e.g., 'ae-jamie')
        account_id: Optional account ID to load account-specific context
    """
    if not _SQL_AVAILABLE or not ae_id:
        return json.dumps({
            "status": "no_memory",
            "message": "No AE ID provided or Lakebase not available. Proceeding without memory.",
        })

    result = {"ae_id": ae_id, "preferences": {}, "account_context": [], "deal_decisions": []}
    safe_ae = ae_id.replace("'", "''")

    # --- AE Preferences ---
    rows = _run_sql(
        f"SELECT email_style, outreach_prefs, avoid_competitors, raw_preferences "
        f"FROM {CATALOG}.{SCHEMA}.memory_ae_profiles "
        f"WHERE ae_id = '{safe_ae}'"
    )
    if not rows.ok:
        logger.error("recall_lakebase_memory SQL failed for ae_profiles: %s", rows.error)
        result["sql_error"] = f"Could not read ae_profiles: {rows.error}"
    if rows:
        prefs = rows[0]
        email_style = prefs.get("email_style") or "{}"
        if isinstance(email_style, str):
            try:
                email_style = json.loads(email_style)
            except json.JSONDecodeError:
                email_style = {}

        outreach = prefs.get("outreach_prefs") or "{}"
        if isinstance(outreach, str):
            try:
                outreach = json.loads(outreach)
            except json.JSONDecodeError:
                outreach = {}

        avoid = prefs.get("avoid_competitors")
        if avoid and isinstance(avoid, str):
            try:
                avoid = json.loads(avoid)
            except json.JSONDecodeError:
                avoid = [avoid]

        raw = prefs.get("raw_preferences")
        if raw and isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = []

        result["preferences"] = {
            "email_style": email_style,
            "outreach_prefs": outreach,
            "avoid_competitors": [a for a in (avoid or []) if a],
            "raw_preferences": (raw or [])[-5:],
        }

    # --- Account Context (last 90 days, high confidence) ---
    if account_id:
        safe_acct = account_id.replace("'", "''")
        ctx_rows = _run_sql(
            f"SELECT context_type, content, confidence, extracted_at "
            f"FROM {CATALOG}.{SCHEMA}.memory_account_context "
            f"WHERE account_id = '{safe_acct}' "
            f"AND extracted_at > date_sub(current_timestamp(), 90) "
            f"AND confidence > 0.80 "
            f"ORDER BY extracted_at DESC LIMIT 10"
        )
        result["account_context"] = [
            {
                "type": r["context_type"],
                "content": r["content"],
                "confidence": r.get("confidence", ""),
                "date": str(r.get("extracted_at", ""))[:10],
            }
            for r in ctx_rows
        ]

        # --- Recent Deal Decisions (last 30 days) ---
        dec_rows = _run_sql(
            f"SELECT d.opp_id, d.recommendation, d.ae_action, d.ae_feedback "
            f"FROM {CATALOG}.{SCHEMA}.memory_deal_decisions d "
            f"JOIN {CATALOG}.{SCHEMA}.gtm_opportunities o ON d.opp_id = o.opp_id "
            f"WHERE o.account_id = '{safe_acct}' "
            f"AND d.decided_at > date_sub(current_timestamp(), 30) "
            f"ORDER BY d.decided_at DESC LIMIT 5"
        )
        result["deal_decisions"] = [
            {
                "opp_id": r["opp_id"],
                "recommendation": r.get("recommendation", "")[:80],
                "ae_action": r["ae_action"],
                "ae_feedback": r.get("ae_feedback", ""),
            }
            for r in dec_rows
        ]

    return json.dumps(result, indent=2)


@tool
def store_lakebase_memory(ae_id: str, fact_type: str, content: str, account_id: str = "", confidence: float = 0.9) -> str:
    """Store a new fact or preference in Lakebase memory tables for future sessions.

    Call this when the AE shares a new preference, corrects the agent, or provides
    account context that should be remembered across sessions.

    Args:
        ae_id: The AE identifier (e.g., 'ae-jamie')
        fact_type: Type of fact — one of: 'ae_preference', 'account_context', 'deal_decision'
        content: The fact or preference to store (e.g., 'email_tone:casual and friendly')
        account_id: Account ID (required for account_context type)
        confidence: Confidence score 0-1 (default 0.9)
    """
    if not _SQL_AVAILABLE or not ae_id:
        return json.dumps({"status": "error", "message": "Lakebase not available"})

    safe_ae = ae_id.replace("'", "''")
    safe_content = content[:500].replace("'", "''")

    if fact_type == "ae_preference":
        res = _run_sql(
            f"MERGE INTO {CATALOG}.{SCHEMA}.memory_ae_profiles t "
            f"USING (SELECT '{safe_ae}' AS ae_id) s ON t.ae_id = s.ae_id "
            f"WHEN MATCHED THEN UPDATE SET "
            f"  raw_preferences = array_append(t.raw_preferences, '{safe_content}'), "
            f"  updated_at = current_timestamp() "
            f"WHEN NOT MATCHED THEN INSERT (ae_id, raw_preferences, updated_at) "
            f"VALUES ('{safe_ae}', array('{safe_content}'), current_timestamp())"
        )
        if not res.ok:
            logger.error("store_lakebase_memory ae_preference FAILED: %s", res.error)
            return json.dumps({"status": "error", "message": f"SQL write failed: {res.error}"})
        return json.dumps({"status": "stored", "type": "ae_preference", "content": content})

    elif fact_type == "account_context" and account_id:
        safe_acct = account_id.replace("'", "''")
        res = _run_sql(
            f"INSERT INTO {CATALOG}.{SCHEMA}.memory_account_context "
            f"(account_id, context_type, content, source_thread_id, ae_id, confidence, extracted_at) "
            f"VALUES ('{safe_acct}', 'agent_noted', '{safe_content}', 'live', '{safe_ae}', "
            f"{confidence}, current_timestamp())"
        )
        if not res.ok:
            logger.error("store_lakebase_memory account_context FAILED: %s", res.error)
            return json.dumps({"status": "error", "message": f"SQL write failed: {res.error}"})
        return json.dumps({"status": "stored", "type": "account_context", "account_id": account_id})

    elif fact_type == "deal_decision":
        dec_id = str(uuid.uuid4())
        res = _run_sql(
            f"INSERT INTO {CATALOG}.{SCHEMA}.memory_deal_decisions "
            f"(decision_id, opp_id, ae_id, session_thread_id, recommendation, ae_action, ae_feedback, decided_at) "
            f"VALUES ('{dec_id}', 'live', '{safe_ae}', 'live', '{safe_content}', 'noted', '', current_timestamp())"
        )
        if not res.ok:
            logger.error("store_lakebase_memory deal_decision FAILED: %s", res.error)
            return json.dumps({"status": "error", "message": f"SQL write failed: {res.error}"})
        return json.dumps({"status": "stored", "type": "deal_decision"})

    return json.dumps({"status": "error", "message": f"Unknown fact_type: {fact_type}"})


# ── UC Function + Vector Search Tools ────────────────────────────────────
uc_toolkit = UCFunctionToolkit(
    function_names=[
        f"{CATALOG}.{SCHEMA}.calculate_deal_health",
        f"{CATALOG}.{SCHEMA}.get_account_signals",
    ]
)

transcript_retriever = VectorSearchRetrieverTool(
    index_name=f"{CATALOG}.{SCHEMA}.gtm_transcripts_idx",
    num_results=4,
    columns=["transcript_id", "transcript_text", "call_date", "participants", "summary", "sentiment", "account_id"],
)

battlecard_retriever = VectorSearchRetrieverTool(
    index_name=f"{CATALOG}.{SCHEMA}.gtm_battlecards_idx",
    num_results=2,
    columns=["card_id", "content", "competitor", "use_case", "win_themes", "objection_handlers"],
)

deal_stories_retriever = VectorSearchRetrieverTool(
    index_name=f"{CATALOG}.{SCHEMA}.gtm_stories_idx",
    num_results=2,
    columns=["story_id", "narrative", "industry", "outcome", "key_moments", "competitor"],
)

# Assemble all tools — Lakebase memory + UC Functions + Vector Search
tools = [recall_lakebase_memory, store_lakebase_memory]
tools.extend(uc_toolkit.tools)
tools.extend([transcript_retriever, battlecard_retriever, deal_stories_retriever])

# ── LLM ──────────────────────────────────────────────────────────────────
llm = ChatDatabricks(endpoint=LLM_ENDPOINT)
llm_with_tools = llm.bind_tools(tools)


# ── LangGraph ────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]


def should_continue(state):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"


def _build_graph(checkpointer=None):
    """Build the LangGraph agent with Lakebase checkpointer."""

    def call_model(state):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(state["messages"])
        return {"messages": [llm_with_tools.invoke(messages)]}

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("agent", RunnableLambda(call_model))
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph_builder.add_edge("tools", "agent")
    return graph_builder.compile(checkpointer=checkpointer)


# Stateless fallback graph
_fallback_graph = _build_graph()


# ── Long-term memory: extract + store (end-of-session batch) ─────────────
def _extract_and_store_memories(
    thread_id: str, ae_id: str, conversation: list[dict]
) -> None:
    """Run haiku extraction agent on the conversation and write to Lakebase memory tables."""
    if not _SQL_AVAILABLE or not ae_id:
        return
    try:
        conversation_text = "\n".join(
            f"{m.get('role', 'unknown').upper()}: {m.get('content', '')}"
            for m in conversation
            if m.get("content")
        )
        if not conversation_text.strip():
            return

        extraction_llm = ChatDatabricks(endpoint=MEMORY_LLM_ENDPOINT)
        result = extraction_llm.invoke([
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": f"Extract memories from:\n\n{conversation_text}"},
        ])

        extracted = json.loads(result.content)
        safe_ae = ae_id.replace("'", "''")

        for pref in extracted.get("ae_preferences", []):
            if pref.get("confidence", 0) < 0.75:
                continue
            val = f"{pref['preference_type']}:{pref['value']}".replace("'", "''")
            _run_sql(
                f"MERGE INTO {CATALOG}.{SCHEMA}.memory_ae_profiles t "
                f"USING (SELECT '{safe_ae}' AS ae_id) s ON t.ae_id = s.ae_id "
                f"WHEN MATCHED THEN UPDATE SET "
                f"  raw_preferences = array_append(t.raw_preferences, '{val}'), "
                f"  updated_at = current_timestamp() "
                f"WHEN NOT MATCHED THEN INSERT (ae_id, raw_preferences, updated_at) "
                f"VALUES ('{safe_ae}', array('{val}'), current_timestamp())"
            )

        for ctx in extracted.get("account_context", []):
            if ctx.get("confidence", 0) < 0.80:
                continue
            safe_acct = ctx["account_id"].replace("'", "''")
            safe_content = ctx["content"].replace("'", "''")
            safe_type = ctx["context_type"].replace("'", "''")
            _run_sql(
                f"INSERT INTO {CATALOG}.{SCHEMA}.memory_account_context "
                f"(account_id, context_type, content, source_thread_id, ae_id, confidence, extracted_at) "
                f"VALUES ('{safe_acct}', '{safe_type}', '{safe_content}', '{thread_id}', '{safe_ae}', "
                f"{ctx['confidence']}, current_timestamp())"
            )

        for dec in extracted.get("deal_decisions", []):
            safe_rec = dec["recommendation"].replace("'", "''")
            safe_fb = dec.get("ae_feedback", "").replace("'", "''")
            dec_id = str(uuid.uuid4())
            _run_sql(
                f"INSERT INTO {CATALOG}.{SCHEMA}.memory_deal_decisions "
                f"(decision_id, opp_id, ae_id, session_thread_id, recommendation, ae_action, ae_feedback, decided_at) "
                f"VALUES ('{dec_id}', '{dec['opp_id']}', '{safe_ae}', '{thread_id}', "
                f"'{safe_rec}', '{dec['ae_action']}', '{safe_fb}', current_timestamp())"
            )

        logger.info("Memories extracted and stored in Lakebase for thread %s", thread_id)
    except Exception:
        logger.warning("Memory extraction failed — skipping", exc_info=True)


# ── Inline Guardrails ──────────────────────────────────────────────────
_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"ignore all prior",
    r"system prompt",
    r"reveal your instructions",
    r"act as\s+(root|admin|developer|system)",
    r"pretend you are",
    r"disregard.*instructions",
    r"what are your (instructions|rules|guidelines)",
    r"output your (system|initial) (prompt|message)",
    r"repeat (everything|all) above",
    r"jailbreak",
    r"DAN mode",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

BLOCKED_RESPONSE_TEXT = (
    "I can't process that request. It appears to contain instructions that "
    "conflict with my guidelines. I'm here to help with deal intelligence, "
    "account research, and outreach drafting."
)


def _check_prompt_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def _check_pii_leakage(text: str) -> list[str]:
    found = []
    for pii_type, pattern in _PII_PATTERNS.items():
        if pattern.search(text):
            found.append(pii_type)
    return found


def _log_security_event(event_type: str, ae_id: str, thread_id: str, detail: str) -> None:
    if not _SQL_AVAILABLE:
        return
    try:
        safe_ae = ae_id.replace("'", "''")
        safe_detail = detail[:500].replace("'", "''")
        event_id = str(uuid.uuid4())
        res = _run_sql(
            f"INSERT INTO {CATALOG}.{SCHEMA}.audit_agent_access "
            f"(event_id, event_type, ae_id, thread_id, detail, created_at) "
            f"VALUES ('{event_id}', '{event_type}', '{safe_ae}', '{thread_id}', "
            f"'{safe_detail}', current_timestamp())"
        )
        if not res.ok:
            logger.error("Failed to write audit event '%s': %s", event_type, res.error)
    except Exception:
        logger.warning("Failed to log security event", exc_info=True)


# ── Streaming helper ────────────────────────────────────────────────────
def _stream_graph(graph, messages, config=None):
    kwargs = {"stream_mode": ["updates"]}
    if config:
        kwargs["config"] = config
    for event in graph.stream({"messages": messages}, **kwargs):
        if event[0] == "updates":
            for node_data in event[1].values():
                if node_data.get("messages"):
                    yield from output_to_responses_items_stream(node_data["messages"])


# ── ResponsesAgent wrapper ───────────────────────────────────────────────
class GTMDealAgent(ResponsesAgent):

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(output=outputs)

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        custom_inputs = getattr(request, "custom_inputs", None) or {}
        thread_id = custom_inputs.get("thread_id") or str(uuid.uuid4())
        ae_id = custom_inputs.get("ae_id", "")
        save_memories = custom_inputs.get("save_memories", False)

        messages = to_chat_completions_input([m.model_dump() for m in request.input])

        # ── Pre-request guardrail: prompt injection detection ────────
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user" and m.get("content"):
                last_user_msg = m["content"]
                break

        if _check_prompt_injection(last_user_msg):
            _log_security_event("prompt_injection_blocked", ae_id, thread_id, last_user_msg)
            logger.warning("Prompt injection detected from ae=%s thread=%s", ae_id, thread_id)
            blocked_item = {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "role": "assistant",
                "content": [{"type": "output_text", "text": BLOCKED_RESPONSE_TEXT}],
            }
            yield ResponsesAgentStreamEvent(type="response.output_item.done", item=blocked_item)
            return

        # ── Run LangGraph agent (memory loaded via recall_lakebase_memory tool) ──
        graph = _build_graph(checkpointer=_checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        # Collect output for post-response PII check
        all_events = []
        for event in _stream_graph(graph, messages, config):
            all_events.append(event)
            yield event

        # ── Post-response guardrail: PII leakage detection ───────────
        for event in all_events:
            if hasattr(event, "item") and isinstance(event.item, dict):
                item = event.item
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            pii_found = _check_pii_leakage(content.get("text", ""))
                            if pii_found:
                                _log_security_event(
                                    "pii_in_output", ae_id, thread_id,
                                    f"PII types: {', '.join(pii_found)}"
                                )

        # ── Extract memories if requested (e.g., on session end) ─────
        if save_memories and ae_id:
            conv = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
            _extract_and_store_memories(thread_id, ae_id, conv)


# ── Register with MLflow ──────────────────────────────────────────────────
mlflow.langchain.autolog()
agent = GTMDealAgent()
mlflow.models.set_model(agent)
