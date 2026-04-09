"""Shared state for the LangGraph multi-agent deal intelligence pipeline."""

from typing import Annotated, Any

import operator
from typing_extensions import TypedDict


class DealState(TypedDict):
    """State passed between agents in the deal intelligence graph.

    Memory fields (memory_prefix, session_summary) are added by the
    load_memory and save_memory bookend nodes. Core agent fields
    (deal_health, account_signals, etc.) are populated by the
    Research → Scoring → Outreach pipeline.
    """

    # --- Session identity ---
    messages: Annotated[list[dict[str, Any]], operator.add]
    thread_id: str
    ae_id: str
    account_id: str
    opp_id: str

    # --- Memory (populated by bookend nodes) ---
    memory_prefix: str
    session_summary: str

    # --- Agent outputs ---
    deal_health: dict[str, Any]
    account_signals: dict[str, Any]
    retrieved_transcripts: list[dict[str, Any]]
    retrieved_battlecards: list[dict[str, Any]]
    outreach_draft: str
    risk_flags: list[str]

    # --- Observability metadata ---
    tech_stack_used: Annotated[list[str], operator.add]
