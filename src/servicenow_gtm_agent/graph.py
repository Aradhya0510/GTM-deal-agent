"""LangGraph agent with tool-calling loop.

The production agent (deployment/agent.py) uses this pattern:
  LangGraph StateGraph with agent node + tools node + conditional edge.
  Agent calls LLM, if tool_calls -> execute tools -> loop back to agent.
  When no more tool calls -> END.

This is simpler and more reliable than the multi-agent pipeline
(research -> scoring -> outreach) because the LLM naturally orchestrates
which tools to call and in what order.

Databricks tech: LangGraph + ChatDatabricks + UCFunctionToolkit + VectorSearchRetrieverTool
"""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from typing import Annotated, Sequence, TypedDict

from databricks_langchain import ChatDatabricks

from servicenow_gtm_agent.tools.uc_functions import get_uc_tools
from servicenow_gtm_agent.tools.vector_search import get_vs_tools


class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]


def build_graph(
    llm_endpoint: str = "databricks-claude-sonnet-4-6",
    catalog: str = "users",
    schema: str = "aradhya_chouhan",
    system_prompt: str = "",
    checkpointer=None,
    memory_prefix: str = "",
):
    """Build the LangGraph tool-calling agent.

    Args:
        llm_endpoint: ChatDatabricks endpoint name.
        catalog: Unity Catalog catalog.
        schema: Unity Catalog schema.
        system_prompt: Base system prompt for the agent.
        checkpointer: Optional LangGraph checkpointer (e.g., Lakebase CheckpointSaver)
            for short-term memory / multi-turn conversations.
        memory_prefix: Optional prefix from long-term memory to prepend to the
            system prompt (cross-session recall).

    Returns a (compiled_graph, tools) tuple.
    """
    tools = get_uc_tools(catalog, schema) + get_vs_tools(catalog, schema)
    llm = ChatDatabricks(endpoint=llm_endpoint)
    llm_with_tools = llm.bind_tools(tools)

    full_prompt = memory_prefix + system_prompt if memory_prefix else system_prompt

    def should_continue(state):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    def call_model(state):
        messages = state["messages"]
        if full_prompt:
            messages = [{"role": "system", "content": full_prompt}] + list(messages)
        return {"messages": [llm_with_tools.invoke(messages)]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", RunnableLambda(call_model))
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer), tools
