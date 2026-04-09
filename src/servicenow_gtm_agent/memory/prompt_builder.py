"""Build memory-augmented system prompt prefix.

At session start, long-term memory is retrieved from Lakebase and formatted
as a structured prefix that gets prepended to each sub-agent's system prompt.
This makes the agent "remember" AE preferences, account context, and past
decisions without any explicit user action.

Databricks tech: Lakebase (read) + LangGraph state injection
"""

from servicenow_gtm_agent.config import AgentConfig
from servicenow_gtm_agent.memory.long_term import load_long_term_memory


def build_memory_system_prompt(
    config: AgentConfig,
    ae_id: str,
    account_id: str | None = None,
) -> str:
    """Build the memory prefix injected at the top of every system prompt.

    Keeps it concise — only high-signal facts that change agent behavior.
    Returns empty string for first-time sessions (no prior memory).
    """
    memory = load_long_term_memory(config, ae_id, account_id)
    sections: list[str] = []

    # --- AE Preferences ---
    if memory["ae_preferences"]:
        prefs = memory["ae_preferences"]
        pref_lines: list[str] = []

        email_style = prefs.get("email_style") or {}
        if email_style.get("max_words"):
            pref_lines.append(f"- Keep emails under {email_style['max_words']} words")
        if email_style.get("tone"):
            pref_lines.append(f"- Tone: {email_style['tone']}")

        if prefs.get("avoid_competitors"):
            pref_lines.append(f"- Do not mention: {', '.join(prefs['avoid_competitors'])}")

        outreach_prefs = prefs.get("outreach_prefs") or {}
        if outreach_prefs.get("preferred_cta"):
            pref_lines.append(f"- Preferred CTA: {outreach_prefs['preferred_cta']}")

        # Include last 5 raw verbatim preferences
        for p in (prefs.get("raw_preferences") or [])[-5:]:
            if ":" in p:
                pref_lines.append(f"- {p.split(':', 1)[-1].strip()}")

        if pref_lines:
            sections.append("## AE PREFERENCES (from prior sessions)\n" + "\n".join(pref_lines))

    # --- Account Context ---
    if memory["account_context"]:
        ctx_lines = []
        for row in memory["account_context"]:
            extracted_at = row.get("extracted_at")
            date_str = extracted_at.strftime("%b %Y") if hasattr(extracted_at, "strftime") else str(extracted_at)
            ctx_lines.append(f"- [{row['context_type']}] {row['content']} (surfaced {date_str})")
        sections.append("## ACCOUNT CONTEXT (from prior sessions)\n" + "\n".join(ctx_lines))

    # --- Recent Decisions ---
    if memory["recent_decisions"]:
        dec_lines = []
        for row in memory["recent_decisions"]:
            rec_summary = row["recommendation"][:80]
            line = f"- Recommended: \"{rec_summary}...\" → AE {row['ae_action']}"
            if row.get("ae_feedback"):
                line += f": \"{row['ae_feedback']}\""
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
