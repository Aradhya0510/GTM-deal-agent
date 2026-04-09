"""Research agent — gathers account context from CRM, call transcripts, and signals.

Databricks tech: UC Functions (get_account_signals) + Vector Search (call_transcripts)
                 + Model Serving (LLM) + MLflow Tracing (auto)
"""

from databricks.agents import create_agent_executor

from servicenow_gtm_agent.config import AgentConfig
from servicenow_gtm_agent.prompts import RESEARCH_AGENT_PROMPT
from servicenow_gtm_agent.tools.uc_functions import get_account_signals_tool
from servicenow_gtm_agent.tools.vector_search import get_transcript_retriever


def create_research_agent(config: AgentConfig):
    """Create the research sub-agent.

    Tools:
      - get_account_signals (UC Function) → CRM data, contacts, open opps
      - call_transcripts (Vector Search) → 4 most relevant Gong transcripts
    """
    return create_agent_executor(
        model=config.model.research_model,
        tools=[
            get_account_signals_tool(config.data.catalog),
            get_transcript_retriever(config.data, num_results=4),
        ],
        system_prompt=RESEARCH_AGENT_PROMPT,
    )
