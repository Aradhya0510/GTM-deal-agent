"""
GTM Deal Intelligence Agent — Standalone agent definition with memory.

This file is loaded by MLflow Model Serving. It contains ONLY the agent
definition and set_model() — NO logging, testing, or deployment code.

Memory Architecture:
  Short-term: LangGraph MemorySaver (in-process, multi-turn within endpoint lifetime)
  Long-term:  Delta tables queried via SQL Statement Execution API (cross-session)

Databricks tech: LangGraph + ChatDatabricks + UC Functions + Vector Search + SQL API
"""

import json
import logging
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
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated, Generator, Sequence, TypedDict

logger = logging.getLogger(__name__)

# ── Optional: SQL API for long-term memory ──────────────────────────────
try:
    from databricks.sdk import WorkspaceClient

    _SQL_AVAILABLE = True
except ImportError:
    _SQL_AVAILABLE = False
    logger.info("databricks.sdk not available — long-term memory disabled")

# ── Configuration ────────────────────────────────────────────────────────
CATALOG = "users"
SCHEMA = "aradhya_chouhan"
LLM_ENDPOINT = "databricks-claude-sonnet-4-6"
MEMORY_LLM_ENDPOINT = "databricks-claude-haiku-4-5"
SQL_WAREHOUSE_ID = "75fd8278393d07eb"  # Shared Endpoint on e2-demo-west

SYSTEM_PROMPT = """You are an expert GTM Deal Intelligence assistant for B2B SaaS account executives.

You have access to:
- Live CRM data via get_account_signals (UC Function on serverless SQL)
- Deal health scoring via calculate_deal_health (UC Function — scores 0-100 with risk flags)
- Gong call transcripts via Vector Search (semantic retrieval over recent calls)
- Competitive battlecards via Vector Search (ServiceNow, BMC, Splunk/Palo Alto, Zendesk/Freshworks)
- Won/lost deal stories via Vector Search (historical deals for proof points)

When asked about a deal or account:
1. ALWAYS call get_account_signals first to get the full account picture
2. Call calculate_deal_health to get the quantitative score and risk flags
3. Search call transcripts for recent conversation context
4. For outreach drafts, search battlecards and deal stories for competitive intel and proof points

When drafting outreach:
- Reference specific insights from recent calls (use names and dates)
- Connect product usage or engagement patterns to business outcomes
- Include one relevant proof point from a similar customer
- Single clear CTA relevant to the deal stage
- Keep emails under 150 words unless told otherwise

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

# ── Tools ────────────────────────────────────────────────────────────────
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

tools = []
tools.extend(uc_toolkit.tools)
tools.extend([transcript_retriever, battlecard_retriever, deal_stories_retriever])

# ── LLM ──────────────────────────────────────────────────────────────────
llm = ChatDatabricks(endpoint=LLM_ENDPOINT)
llm_with_tools = llm.bind_tools(tools)

# ── Short-term memory: MemorySaver (in-process, persists across turns) ──
_checkpointer = MemorySaver()


# ── LangGraph ────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]


def should_continue(state):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"


def _build_graph(checkpointer=None, memory_prefix=""):
    """Build the LangGraph agent, optionally with checkpointer and memory prefix."""
    system_prompt = memory_prefix + SYSTEM_PROMPT if memory_prefix else SYSTEM_PROMPT

    def call_model(state):
        messages = [{"role": "system", "content": system_prompt}] + list(state["messages"])
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


# ── SQL helper for long-term memory ─────────────────────────────────────
def _run_sql(statement: str) -> list[dict]:
    """Execute a SQL statement via the Databricks SQL Statement Execution API.

    Returns a list of dicts (one per row). Returns [] on failure.
    """
    if not _SQL_AVAILABLE:
        return []
    try:
        w = WorkspaceClient()
        resp = w.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=SQL_WAREHOUSE_ID,
            wait_timeout="30s",
        )
        if resp.status and resp.status.state and resp.status.state.value == "SUCCEEDED":
            if not resp.result or not resp.result.data_array:
                return []
            columns = [c.name for c in resp.manifest.schema.columns]
            return [dict(zip(columns, row)) for row in resp.result.data_array]
        else:
            logger.warning("SQL execution failed: %s", resp.status)
            return []
    except Exception:
        logger.warning("SQL execution error", exc_info=True)
        return []


# ── Long-term memory: load ──────────────────────────────────────────────
def _load_memory_prefix(ae_id: str, account_id: str | None = None) -> str:
    """Load long-term memory from Delta tables and format as system prompt prefix."""
    if not _SQL_AVAILABLE or not ae_id:
        return ""
    try:
        sections: list[str] = []
        safe_ae = ae_id.replace("'", "''")

        # --- AE Preferences ---
        rows = _run_sql(
            f"SELECT email_style, outreach_prefs, avoid_competitors, raw_preferences "
            f"FROM {CATALOG}.{SCHEMA}.memory_ae_profiles "
            f"WHERE ae_id = '{safe_ae}'"
        )
        if rows:
            prefs = rows[0]
            pref_lines: list[str] = []

            email_style = prefs.get("email_style") or "{}"
            if isinstance(email_style, str):
                try:
                    email_style = json.loads(email_style)
                except json.JSONDecodeError:
                    email_style = {}
            if email_style.get("max_words"):
                pref_lines.append(f"- Keep emails under {email_style['max_words']} words")
            if email_style.get("tone"):
                pref_lines.append(f"- Tone: {email_style['tone']}")

            avoid = prefs.get("avoid_competitors")
            if avoid:
                if isinstance(avoid, str):
                    # Delta ARRAY<STRING> returned as JSON string like '["ServiceNow"]'
                    try:
                        avoid = json.loads(avoid)
                    except json.JSONDecodeError:
                        avoid = [avoid]
                if avoid and avoid != [""] and avoid != []:
                    pref_lines.append(f"- Do not mention: {', '.join(str(a) for a in avoid if a)}")

            outreach = prefs.get("outreach_prefs") or "{}"
            if isinstance(outreach, str):
                try:
                    outreach = json.loads(outreach)
                except json.JSONDecodeError:
                    outreach = {}
            if outreach.get("preferred_cta"):
                pref_lines.append(f"- Preferred CTA: {outreach['preferred_cta']}")

            raw = prefs.get("raw_preferences")
            if raw:
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        raw = []
                for p in (raw or [])[-5:]:
                    if ":" in str(p):
                        pref_lines.append(f"- {str(p).split(':', 1)[-1].strip()}")

            if pref_lines:
                sections.append("## AE PREFERENCES (from prior sessions)\n" + "\n".join(pref_lines))

        # --- Account Context (last 90 days, high confidence) ---
        if account_id:
            safe_acct = account_id.replace("'", "''")
            ctx_rows = _run_sql(
                f"SELECT context_type, content, extracted_at "
                f"FROM {CATALOG}.{SCHEMA}.memory_account_context "
                f"WHERE account_id = '{safe_acct}' "
                f"AND extracted_at > date_sub(current_timestamp(), 90) "
                f"AND confidence > 0.80 "
                f"ORDER BY extracted_at DESC LIMIT 10"
            )
            if ctx_rows:
                ctx_lines = []
                for r in ctx_rows:
                    date_str = str(r.get("extracted_at", ""))[:7]  # YYYY-MM
                    ctx_lines.append(f"- [{r['context_type']}] {r['content']} (surfaced {date_str})")
                sections.append("## ACCOUNT CONTEXT (from prior sessions)\n" + "\n".join(ctx_lines))

            # --- Recent Deal Decisions (last 30 days) ---
            dec_rows = _run_sql(
                f"SELECT d.recommendation, d.ae_action, d.ae_feedback "
                f"FROM {CATALOG}.{SCHEMA}.memory_deal_decisions d "
                f"JOIN {CATALOG}.{SCHEMA}.gtm_opportunities o ON d.opp_id = o.opp_id "
                f"WHERE o.account_id = '{safe_acct}' "
                f"AND d.decided_at > date_sub(current_timestamp(), 30) "
                f"ORDER BY d.decided_at DESC LIMIT 5"
            )
            if dec_rows:
                dec_lines = []
                for r in dec_rows:
                    rec = str(r.get("recommendation", ""))[:80]
                    line = f'- Recommended: "{rec}" -> AE {r["ae_action"]}'
                    if r.get("ae_feedback"):
                        line += f': "{r["ae_feedback"]}"'
                    dec_lines.append(line)
                sections.append("## RECENT DECISION HISTORY\n" + "\n".join(dec_lines))

        if not sections:
            return ""
        return (
            "# MEMORY FROM PRIOR SESSIONS\n"
            "The following was learned from previous conversations. Apply it silently.\n\n"
            + "\n\n".join(sections)
            + "\n\n---\n\n"
        )
    except Exception:
        logger.warning("Failed to load long-term memory — continuing without", exc_info=True)
        return ""


# ── Long-term memory: extract + store ───────────────────────────────────
def _extract_and_store_memories(
    thread_id: str, ae_id: str, conversation: list[dict]
) -> None:
    """Run haiku extraction agent on the conversation and write to Delta tables.

    Failures are logged but never propagated — memory extraction is best-effort.
    """
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

        # Append raw preferences
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

        # Insert account context
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

        # Log deal decisions
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

        logger.info("Memories extracted and stored for thread %s", thread_id)
    except Exception:
        logger.warning("Memory extraction failed — skipping", exc_info=True)


# ── Streaming helper ────────────────────────────────────────────────────
def _stream_graph(graph, messages, config=None):
    """Yield ResponsesAgent stream events from a LangGraph execution."""
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
        # ── Extract custom inputs ────────────────────────────────────
        custom_inputs = getattr(request, "custom_inputs", None) or {}
        thread_id = custom_inputs.get("thread_id") or str(uuid.uuid4())
        ae_id = custom_inputs.get("ae_id", "")
        account_id = custom_inputs.get("account_id")
        save_memories = custom_inputs.get("save_memories", False)

        messages = to_chat_completions_input([m.model_dump() for m in request.input])

        # ── Long-term memory (cross-session, from Delta tables) ──────
        memory_prefix = _load_memory_prefix(ae_id, account_id)

        # ── Short-term memory (multi-turn via MemorySaver) ───────────
        graph = _build_graph(checkpointer=_checkpointer, memory_prefix=memory_prefix)
        config = {"configurable": {"thread_id": thread_id}}
        yield from _stream_graph(graph, messages, config)

        # ── Extract memories if requested (e.g., on session end) ─────
        if save_memories and ae_id:
            conv = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
            _extract_and_store_memories(thread_id, ae_id, conv)


# ── Register with MLflow (this is what Model Serving loads) ──────────────
mlflow.langchain.autolog()
agent = GTMDealAgent()
mlflow.models.set_model(agent)
