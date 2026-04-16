"""
GTM Deal Intelligence Agent — Standalone agent definition with Lakebase memory.

This file is loaded by MLflow Model Serving. It contains ONLY the agent
definition and set_model() — NO logging, testing, or deployment code.

Memory Architecture:
  Short-term: Lakebase CheckpointSaver → Postgres (cross-replica session persistence)
              Falls back to MemorySaver if Lakebase instance not configured
  Long-term:  Lakebase DatabricksStore → Postgres with semantic search (via embeddings)
              recall_lakebase_memory / store_lakebase_memory as visible LangGraph tools

Databricks tech: LangGraph + ChatDatabricks + UC Functions + Vector Search + Lakebase Postgres
"""

import json
import logging
import os
import re
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

# ── Configuration ────────────────────────────────────────────────────────
CATALOG = os.environ.get("UC_CATALOG", "")
SCHEMA = os.environ.get("UC_SCHEMA", "")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "databricks-claude-sonnet-4-6")
MEMORY_LLM_ENDPOINT = os.environ.get("MEMORY_LLM_ENDPOINT", "databricks-claude-haiku-4-5")
LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "")
LAKEBASE_ENDPOINT = os.environ.get("LAKEBASE_AUTOSCALING_ENDPOINT", "")
EMBEDDING_ENDPOINT = os.environ.get("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")

SQL_WAREHOUSE_ID = os.environ.get("SQL_WAREHOUSE_ID", "")

# ── Lakebase Postgres: CheckpointSaver + DatabricksStore ──────────────────
_LAKEBASE_AVAILABLE = False
_checkpointer = None
_memory_store = None

try:
    from databricks_langchain import CheckpointSaver, DatabricksStore
    from databricks.sdk import WorkspaceClient as _LBWorkspaceClient

    _lb_kwargs = {"instance_name": LAKEBASE_INSTANCE_NAME}

    # Use explicit PAT for Lakebase auth — the auto-generated SP from agents.deploy()
    # is ephemeral (new per model version) and doesn't have a Postgres role.
    _lakebase_token = os.environ.get("LAKEBASE_PAT")
    _lakebase_host = os.environ.get("DATABRICKS_HOST", "")
    if _lakebase_token:
        _lb_wc = _LBWorkspaceClient(host=_lakebase_host, token=_lakebase_token)
        _lb_kwargs["workspace_client"] = _lb_wc
        logger.info("Using explicit PAT for Lakebase connection (user-level auth)")

    _checkpointer = CheckpointSaver(**_lb_kwargs)
    _memory_store = DatabricksStore(
        **_lb_kwargs,
        embedding_endpoint=EMBEDDING_ENDPOINT,
        embedding_dims=1024,
    )
    _memory_store.setup()
    _checkpointer.setup()
    _LAKEBASE_AVAILABLE = True
    logger.info(
        "Lakebase Postgres connected — %s, CheckpointSaver + DatabricksStore active",
        LAKEBASE_INSTANCE_NAME,
    )
except Exception as e:
    import traceback
    logger.error("Lakebase Postgres init FAILED — falling back to MemorySaver. Error: %s\n%s", e, traceback.format_exc())
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()
    _memory_store = None

# ── SQL helper (only for audit_agent_access Delta table) ──────────────────
try:
    from databricks.sdk import WorkspaceClient
    _SQL_AVAILABLE = True
except ImportError:
    _SQL_AVAILABLE = False

def _run_audit_sql(statement: str) -> bool:
    """Execute SQL for audit logging only. Returns True on success."""
    if not _SQL_AVAILABLE:
        return False
    try:
        w = WorkspaceClient()
        resp = w.statement_execution.execute_statement(
            statement=statement, warehouse_id=SQL_WAREHOUSE_ID, wait_timeout="10s",
        )
        return bool(resp.status and resp.status.state and resp.status.state.value == "SUCCEEDED")
    except Exception:
        logger.warning("Audit SQL execution error", exc_info=True)
        return False


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


# ═══════════════════════════════════════════════════════════════════════════
#  LAKEBASE MEMORY TOOLS — backed by real Lakebase Postgres via DatabricksStore
# ═══════════════════════════════════════════════════════════════════════════

@tool
def recall_lakebase_memory(ae_id: str, account_id: str = "") -> str:
    """Load AE preferences, account context, and deal decisions from Lakebase memory.

    ALWAYS call this tool FIRST before answering any question. It retrieves:
    - AE email preferences (tone, length, CTA, competitors to avoid)
    - Account-specific context (champion changes, budget, competitor intel)
    - Recent deal decision history (what recommendations were accepted/rejected)

    Args:
        ae_id: The AE identifier (e.g., 'ae-jamie')
        account_id: Optional account ID to load account-specific context
    """
    if not ae_id:
        return json.dumps({"status": "no_memory", "message": "No AE ID provided."})
    if not _LAKEBASE_AVAILABLE or not _memory_store:
        return json.dumps({
            "status": "no_memory",
            "message": f"Lakebase not available. LAKEBASE_AVAILABLE={_LAKEBASE_AVAILABLE}, "
                       f"instance={LAKEBASE_INSTANCE_NAME}, endpoint={LAKEBASE_ENDPOINT}",
        })

    result = {"ae_id": ae_id, "preferences": [], "account_context": [], "deal_decisions": []}

    try:
        # Search AE preferences
        ae_namespace = ("ae_memories", ae_id)
        pref_results = _memory_store.search(ae_namespace, query="preferences style tone email", limit=10)
        for item in pref_results:
            result["preferences"].append({"key": item.key, **item.value})

        # Search account context if account_id provided
        if account_id:
            acct_namespace = ("account_memories", account_id)
            ctx_results = _memory_store.search(
                acct_namespace, query="context champion budget competitor timeline", limit=10
            )
            for item in ctx_results:
                result["account_context"].append({"key": item.key, **item.value})

            # Search deal decisions
            dec_namespace = ("deal_decisions", ae_id)
            dec_results = _memory_store.search(
                dec_namespace, query=f"decisions recommendations {account_id}", limit=5
            )
            for item in dec_results:
                result["deal_decisions"].append({"key": item.key, **item.value})

    except Exception as e:
        logger.error("recall_lakebase_memory failed: %s", e, exc_info=True)
        result["error"] = str(e)

    return json.dumps(result, indent=2)


@tool
def store_lakebase_memory(ae_id: str, fact_type: str, content: str, account_id: str = "", confidence: float = 0.9) -> str:
    """Store a new fact or preference in Lakebase memory for future sessions.

    Call this when the AE shares a new preference, corrects the agent, or provides
    account context that should be remembered across sessions.

    Args:
        ae_id: The AE identifier (e.g., 'ae-jamie')
        fact_type: Type of fact — one of: 'ae_preference', 'account_context', 'deal_decision'
        content: The fact or preference to store (e.g., 'email_tone:casual and friendly')
        account_id: Account ID (required for account_context type)
        confidence: Confidence score 0-1 (default 0.9)
    """
    if not _LAKEBASE_AVAILABLE or not _memory_store or not ae_id:
        return json.dumps({"status": "error", "message": "Lakebase not available"})

    try:
        memory_key = f"{fact_type}_{uuid.uuid4().hex[:8]}"
        memory_data = {
            "type": fact_type,
            "content": content,
            "ae_id": ae_id,
            "confidence": confidence,
        }

        if fact_type == "ae_preference":
            namespace = ("ae_memories", ae_id)
            if ":" in content:
                pref_type, pref_value = content.split(":", 1)
                memory_data["preference_type"] = pref_type.strip()
                memory_data["preference_value"] = pref_value.strip()

        elif fact_type == "account_context" and account_id:
            namespace = ("account_memories", account_id)
            memory_data["account_id"] = account_id

        elif fact_type == "deal_decision":
            namespace = ("deal_decisions", ae_id)

        else:
            return json.dumps({"status": "error", "message": f"Unknown fact_type: {fact_type}"})

        _memory_store.put(namespace, memory_key, memory_data)
        return json.dumps({"status": "stored", "type": fact_type, "key": memory_key})

    except Exception as e:
        logger.error("store_lakebase_memory failed: %s", e, exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})


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


def _build_graph(checkpointer=None, store=None):
    """Build the LangGraph agent with Lakebase checkpointer and store."""

    def call_model(state):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(state["messages"])
        return {"messages": [llm_with_tools.invoke(messages)]}

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("agent", RunnableLambda(call_model))
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph_builder.add_edge("tools", "agent")
    return graph_builder.compile(checkpointer=checkpointer, store=store)


# ── Long-term memory: extract + store (end-of-session batch) ─────────────
def _extract_and_store_memories(
    thread_id: str, ae_id: str, conversation: list[dict]
) -> None:
    """Run haiku extraction agent on the conversation and write to Lakebase Postgres."""
    if not _LAKEBASE_AVAILABLE or not _memory_store or not ae_id:
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

        for pref in extracted.get("ae_preferences", []):
            if pref.get("confidence", 0) < 0.75:
                continue
            key = f"ae_pref_{uuid.uuid4().hex[:8]}"
            _memory_store.put(
                ("ae_memories", ae_id), key,
                {
                    "type": "ae_preference",
                    "preference_type": pref["preference_type"],
                    "preference_value": pref["value"],
                    "content": f"{pref['preference_type']}:{pref['value']}",
                    "confidence": pref["confidence"],
                    "source_thread": thread_id,
                },
            )

        for ctx in extracted.get("account_context", []):
            if ctx.get("confidence", 0) < 0.80:
                continue
            key = f"ctx_{uuid.uuid4().hex[:8]}"
            _memory_store.put(
                ("account_memories", ctx["account_id"]), key,
                {
                    "type": "account_context",
                    "context_type": ctx["context_type"],
                    "content": ctx["content"],
                    "confidence": ctx["confidence"],
                    "ae_id": ae_id,
                    "source_thread": thread_id,
                },
            )

        for dec in extracted.get("deal_decisions", []):
            key = f"dec_{uuid.uuid4().hex[:8]}"
            _memory_store.put(
                ("deal_decisions", ae_id), key,
                {
                    "type": "deal_decision",
                    "opp_id": dec.get("opp_id", ""),
                    "recommendation": dec["recommendation"],
                    "ae_action": dec["ae_action"],
                    "ae_feedback": dec.get("ae_feedback", ""),
                    "content": f"{dec['ae_action']}: {dec['recommendation']}",
                    "source_thread": thread_id,
                },
            )

        logger.info("Memories extracted and stored in Lakebase Postgres for thread %s", thread_id)
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
        _run_audit_sql(
            f"INSERT INTO {CATALOG}.{SCHEMA}.audit_agent_access "
            f"(event_id, event_type, ae_id, thread_id, detail, created_at) "
            f"VALUES ('{event_id}', '{event_type}', '{safe_ae}', '{thread_id}', "
            f"'{safe_detail}', current_timestamp())"
        )
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

        # ── Run LangGraph agent with Lakebase checkpointer + store ──
        graph = _build_graph(checkpointer=_checkpointer, store=_memory_store)
        config = {"configurable": {"thread_id": thread_id}}

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
