"""Memory extraction agent — distills reusable facts at session close.

Runs once per session. Reads the full conversation and extracts:
  - AE preferences (email style, tone, CTA preferences)
  - Account context (champion changes, budget freezes, competitor mentions)
  - Deal decisions (what the AE accepted/rejected)

Uses ChatDatabricks directly (no tools needed — pure text-to-JSON extraction).

Databricks tech: Model Serving (claude-haiku-4-5 for cost efficiency)
"""

from databricks_langchain import ChatDatabricks

from servicenow_gtm_agent.config import AgentConfig
from servicenow_gtm_agent.prompts import MEMORY_EXTRACTION_PROMPT


def create_memory_extractor(config: AgentConfig) -> ChatDatabricks:
    """Create the memory extraction LLM.

    Returns a ChatDatabricks instance pre-configured for extraction.
    Usage:

        extractor = create_memory_extractor(config)
        result = extractor.invoke([
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": f"Extract memories from:\\n\\n{conversation_text}"},
        ])
        extracted = json.loads(result.content)
    """
    return ChatDatabricks(endpoint=config.model.memory_extraction_model)


def extract_memories(config: AgentConfig, conversation_text: str) -> dict:
    """Run memory extraction on a conversation and return structured facts.

    Returns a dict with keys: ae_preferences, account_context, deal_decisions.
    Raises ValueError if the LLM response is not valid JSON.
    """
    import json

    llm = create_memory_extractor(config)
    result = llm.invoke([
        {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
        {"role": "user", "content": f"Extract memories from:\n\n{conversation_text}"},
    ])
    return json.loads(result.content)
