"""
GTM Deal Intelligence Agent — Standalone agent definition.

This file is loaded by MLflow Model Serving. It contains ONLY the agent
definition and set_model() — NO logging, testing, or deployment code.
"""

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
from typing import Annotated, Generator, Sequence, TypedDict

# ── Configuration ────────────────────────────────────────────────────────
CATALOG = "users"
SCHEMA = "aradhya_chouhan"
LLM_ENDPOINT = "databricks-claude-sonnet-4-6"

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

# ── LangGraph ────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]

llm = ChatDatabricks(endpoint=LLM_ENDPOINT)
llm_with_tools = llm.bind_tools(tools)


def should_continue(state):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"


def call_model(state):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", RunnableLambda(call_model))
graph_builder.add_node("tools", ToolNode(tools))
graph_builder.set_entry_point("agent")
graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
graph_builder.add_edge("tools", "agent")
compiled_graph = graph_builder.compile()

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
        messages = to_chat_completions_input([m.model_dump() for m in request.input])
        for event in compiled_graph.stream({"messages": messages}, stream_mode=["updates"]):
            if event[0] == "updates":
                for node_data in event[1].values():
                    if node_data.get("messages"):
                        yield from output_to_responses_items_stream(node_data["messages"])

# ── Register with MLflow (this is what Model Serving loads) ──────────────
mlflow.langchain.autolog()
agent = GTMDealAgent()
mlflow.models.set_model(agent)
