"""Outreach agent — drafts personalized emails grounded in account context.

Databricks tech: Vector Search (battlecards + deal_stories) + Model Serving (LLM)
                 + LLM Gateway (rate limits, PII blocking) + MLflow Tracing (auto)
"""

from databricks.agents import create_agent_executor

from servicenow_gtm_agent.config import AgentConfig
from servicenow_gtm_agent.prompts import OUTREACH_AGENT_PROMPT
from servicenow_gtm_agent.tools.vector_search import get_battlecard_retriever, get_deal_stories_retriever


def create_outreach_agent(config: AgentConfig):
    """Create the outreach sub-agent.

    Tools:
      - battlecards (Vector Search) → competitive intel for the deal context
      - deal_stories (Vector Search) → relevant won/lost stories for proof points
    """
    return create_agent_executor(
        model=config.model.outreach_model,
        tools=[
            get_battlecard_retriever(config.data, num_results=2),
            get_deal_stories_retriever(config.data, num_results=2),
        ],
        system_prompt=OUTREACH_AGENT_PROMPT,
    )
