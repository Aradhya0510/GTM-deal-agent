# Databricks notebook source
# MAGIC %md
# MAGIC # GTM Deal Intelligence Agent — Deployment
# MAGIC
# MAGIC **Powered by:** LangGraph + Model Serving + MLflow 3.0 + Vector Search + UC Functions

# COMMAND ----------

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)
from mlflow.models.resources import (
    DatabricksServingEndpoint,
    DatabricksFunction,
    DatabricksVectorSearchIndex,
)

# Configuration
CATALOG = "users"
SCHEMA = "aradhya_chouhan"
LLM_ENDPOINT = "databricks-claude-sonnet-4-6"

EXPERIMENT_NAME = "/Users/aradhya.chouhan@databricks.com/gtm-deal-intelligence"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.gtm_deal_intelligence_agent"

mlflow.set_experiment(EXPERIMENT_NAME)
print(f"Config: LLM={LLM_ENDPOINT}, Catalog={CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define Tools
# MAGIC
# MAGIC - **UC Functions** (Serverless SQL): `calculate_deal_health`, `get_account_signals`
# MAGIC - **Vector Search**: call transcripts, battlecards, deal stories

# COMMAND ----------

from databricks_langchain import ChatDatabricks, UCFunctionToolkit, VectorSearchRetrieverTool

# UC Function tools
uc_toolkit = UCFunctionToolkit(
    function_names=[
        f"{CATALOG}.{SCHEMA}.calculate_deal_health",
        f"{CATALOG}.{SCHEMA}.get_account_signals",
    ]
)

# Vector Search retriever tools
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

# Combine all tools
tools = []
tools.extend(uc_toolkit.tools)
tools.extend([transcript_retriever, battlecard_retriever, deal_stories_retriever])

print(f"Tools configured: {len(tools)}")
for t in tools:
    print(f"  - {t.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build LangGraph Agent

# COMMAND ----------

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from typing import Annotated, Generator, Sequence, TypedDict

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


class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]


# LLM with tools bound
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


# Build LangGraph
graph_builder = StateGraph(AgentState)
graph_builder.add_node("agent", RunnableLambda(call_model))
graph_builder.add_node("tools", ToolNode(tools))
graph_builder.set_entry_point("agent")
graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
graph_builder.add_edge("tools", "agent")
compiled_graph = graph_builder.compile()

print("LangGraph compiled with tool-calling loop")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Wrap as ResponsesAgent

# COMMAND ----------

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


mlflow.langchain.autolog()
agent = GTMDealAgent()
mlflow.models.set_model(agent)
print("ResponsesAgent created and set as model")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test the Agent

# COMMAND ----------

result = agent.predict(ResponsesAgentRequest(
    input=[{"role": "user", "content": "What's the deal health on OPP-3001 (Meridian Health)? Give me the score, risk flags, and key contacts."}]
))

# Print the text output
for item in result.output:
    if isinstance(item, dict) and item.get("type") == "message":
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                print(content["text"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log to MLflow and Register

# COMMAND ----------

# Build resources list for auth passthrough
from unitycatalog.ai.langchain.toolkit import UnityCatalogTool

resources = [DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT)]

for tool in tools:
    if isinstance(tool, UnityCatalogTool):
        resources.append(DatabricksFunction(function_name=tool.uc_function_name))
    elif isinstance(tool, VectorSearchRetrieverTool):
        resources.extend(tool.resources)

print(f"Resources: {len(resources)}")
for r in resources:
    print(f"  - {r}")

# COMMAND ----------

mlflow.end_run()  # End any active autolog run

with mlflow.start_run(run_name="gtm-agent-v1"):
    model_info = mlflow.pyfunc.log_model(
        name="gtm_agent",
        python_model="agent_notebook",  # This notebook as the model source
        resources=resources,
        pip_requirements=[
            "mlflow>=3.6.0",
            "databricks-langchain",
            "langgraph>=0.3",
            "databricks-agents",
            "pydantic",
        ],
        input_example={
            "input": [{"role": "user", "content": "What's the deal health on OPP-3001?"}]
        },
        registered_model_name=MODEL_NAME,
    )
    print(f"Model URI: {model_info.model_uri}")
    print(f"Run ID: {model_info.run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy to Model Serving

# COMMAND ----------

from databricks.agents import deploy

deployment = deploy(
    model_name=MODEL_NAME,
    model_version=model_info.registered_model_version,
)

print(f"Endpoint: {deployment.endpoint_name}")
print(f"Query endpoint: {deployment.query_endpoint}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test Deployed Endpoint

# COMMAND ----------

import time
print("Waiting 60s for endpoint to warm up...")
time.sleep(60)

from databricks.sdk import WorkspaceClient
from openai import OpenAI

w = WorkspaceClient()
client = OpenAI(
    base_url=f"{w.config.host}/serving-endpoints",
    api_key=w.config.token,
)

response = client.chat.completions.create(
    model=deployment.endpoint_name,
    messages=[{
        "role": "user",
        "content": "Score the deal health for OPP-3002 (Apex Financial) and tell me the competitive threats."
    }],
    max_tokens=1000,
)

print(response.choices[0].message.content)
