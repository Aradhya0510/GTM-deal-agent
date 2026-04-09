"""Scoring agent — calculates deal health and identifies risk flags.

Databricks tech: UC Functions (calculate_deal_health) + Model Serving (LLM)
                 + MLflow Tracing (auto)
"""

from databricks.agents import create_agent_executor

from servicenow_gtm_agent.config import AgentConfig
from servicenow_gtm_agent.prompts import SCORING_AGENT_PROMPT
from servicenow_gtm_agent.tools.uc_functions import get_deal_health_tool


def create_scoring_agent(config: AgentConfig):
    """Create the scoring sub-agent.

    Tools:
      - calculate_deal_health (UC Function) → score 0-100 + risk flags
    """
    return create_agent_executor(
        model=config.model.scoring_model,
        tools=[
            get_deal_health_tool(config.data.catalog),
        ],
        system_prompt=SCORING_AGENT_PROMPT,
    )
