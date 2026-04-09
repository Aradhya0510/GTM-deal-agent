"""Memory extraction agent — distills reusable facts at session close.

Runs once per session. Reads the full conversation and extracts:
  - AE preferences (email style, tone, CTA preferences)
  - Account context (champion changes, budget freezes, competitor mentions)
  - Deal decisions (what the AE accepted/rejected)

Databricks tech: Model Serving (claude-3-5-haiku for cost efficiency)
                 + Lakebase (write to long-term memory tables)
"""

from databricks.agents import create_agent_executor

from servicenow_gtm_agent.config import AgentConfig
from servicenow_gtm_agent.prompts import MEMORY_EXTRACTION_PROMPT


def create_memory_extractor(config: AgentConfig):
    """Create the memory extraction agent.

    Uses a fast/cheap model (haiku) since it runs at session close
    and doesn't need tool access — just conversation → JSON extraction.
    """
    return create_agent_executor(
        model=config.model.memory_extraction_model,
        tools=[],
        system_prompt=MEMORY_EXTRACTION_PROMPT,
    )
