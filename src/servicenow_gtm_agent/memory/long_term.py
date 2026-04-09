"""Long-term memory — extraction at session close, retrieval at session start.

At session close: a lightweight extraction agent (haiku) reads the full
conversation and distills concrete facts into three Lakebase tables.

At session start: relevant facts are retrieved and injected into the
system prompt so the agent "remembers" across sessions.

Databricks tech: Lakebase (memory tables) + Model Serving (extraction LLM)
                 + Unity Catalog (row-level security on memory tables)
"""

import json
import logging

from databricks.sdk import WorkspaceClient

from servicenow_gtm_agent.agents.memory_extractor import create_memory_extractor
from servicenow_gtm_agent.config import AgentConfig

logger = logging.getLogger(__name__)


def extract_and_store_memories(
    config: AgentConfig,
    thread_id: str,
    ae_id: str,
    conversation_history: list[dict],
) -> None:
    """Extract facts from a conversation and store in long-term memory.

    Called at session close. Runs the memory extraction agent (haiku)
    and upserts results to Lakebase memory tables.

    Designed to run async (fire-and-forget) so it doesn't block the session.
    """
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation_history if m.get("content")
    )

    if not conversation_text.strip():
        return

    extractor = create_memory_extractor(config)
    result = extractor.predict(
        {"messages": [{"role": "user", "content": f"Extract memories from:\n\n{conversation_text}"}]}
    )

    try:
        extracted = json.loads(result["messages"][-1]["content"])
    except (json.JSONDecodeError, KeyError, IndexError):
        logger.warning("Memory extraction failed — skipping for thread %s", thread_id)
        return

    w = WorkspaceClient()
    conn = w.lakebase.connect(instance_name=config.lakebase.instance_name)

    # --- Upsert AE preferences (confidence >= 0.75) ---
    for pref in extracted.get("ae_preferences", []):
        if pref.get("confidence", 0) < 0.75:
            continue
        try:
            conn.execute(
                """
                INSERT INTO gtm.memory_ae_profiles (ae_id, raw_preferences, updated_at)
                VALUES (%s, ARRAY[%s::TEXT], NOW())
                ON CONFLICT (ae_id) DO UPDATE SET
                    raw_preferences = array_append(memory_ae_profiles.raw_preferences, EXCLUDED.raw_preferences[1]),
                    updated_at = NOW()
                """,
                [ae_id, f"{pref['preference_type']}:{pref['value']}"],
            )
        except Exception:
            logger.exception("Failed to upsert AE preference")

    # --- Insert account context (confidence >= 0.80) ---
    for ctx in extracted.get("account_context", []):
        if ctx.get("confidence", 0) < 0.80:
            continue
        try:
            conn.execute(
                """
                INSERT INTO gtm.memory_account_context
                    (account_id, context_type, content, source_thread_id, ae_id, confidence, extracted_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                [ctx["account_id"], ctx["context_type"], ctx["content"], thread_id, ae_id, ctx["confidence"]],
            )
        except Exception:
            logger.exception("Failed to insert account context")

    # --- Log deal decisions ---
    for dec in extracted.get("deal_decisions", []):
        try:
            conn.execute(
                """
                INSERT INTO gtm.memory_deal_decisions
                    (opp_id, ae_id, session_thread_id, recommendation, ae_action, ae_feedback)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [dec["opp_id"], ae_id, thread_id, dec["recommendation"], dec["ae_action"], dec.get("ae_feedback", "")],
            )
        except Exception:
            logger.exception("Failed to log deal decision")

    logger.info("Memories extracted and stored for thread %s", thread_id)


def load_long_term_memory(
    config: AgentConfig,
    ae_id: str,
    account_id: str | None = None,
) -> dict:
    """Retrieve long-term memory for an AE (and optionally an account).

    Called at session start. Returns a dict with:
      - ae_preferences: AE's stored profile (style, prefs, avoidances)
      - account_context: recent facts about the account (last 90 days)
      - recent_decisions: what the agent recommended and what the AE did
    """
    w = WorkspaceClient()
    conn = w.lakebase.connect(instance_name=config.lakebase.instance_name)

    # --- AE preferences ---
    ae_prefs = None
    try:
        row = conn.execute(
            """
            SELECT email_style, outreach_prefs, avoid_competitors,
                   formatting_prefs, raw_preferences
            FROM gtm.memory_ae_profiles
            WHERE ae_id = %s
            """,
            [ae_id],
        ).fetchone()
        if row:
            ae_prefs = dict(row)
    except Exception:
        logger.warning("Failed to load AE preferences for %s", ae_id)

    # --- Account context (last 90 days, confidence > 0.80) ---
    account_context = []
    if account_id:
        try:
            rows = conn.execute(
                """
                SELECT context_type, content, ae_id, confidence, extracted_at
                FROM gtm.memory_account_context
                WHERE account_id = %s
                  AND extracted_at > NOW() - INTERVAL '90 days'
                  AND confidence > 0.80
                ORDER BY extracted_at DESC
                LIMIT 10
                """,
                [account_id],
            ).fetchall()
            account_context = [dict(r) for r in rows]
        except Exception:
            logger.warning("Failed to load account context for %s", account_id)

    # --- Recent deal decisions (last 30 days) ---
    recent_decisions = []
    if account_id:
        try:
            rows = conn.execute(
                """
                SELECT d.recommendation, d.ae_action, d.ae_feedback, d.decided_at
                FROM gtm.memory_deal_decisions d
                JOIN gtm.opportunities o ON d.opp_id = o.opp_id
                WHERE o.account_id = %s
                  AND d.decided_at > NOW() - INTERVAL '30 days'
                ORDER BY d.decided_at DESC
                LIMIT 5
                """,
                [account_id],
            ).fetchall()
            recent_decisions = [dict(r) for r in rows]
        except Exception:
            logger.warning("Failed to load deal decisions for account %s", account_id)

    return {
        "ae_preferences": ae_prefs,
        "account_context": account_context,
        "recent_decisions": recent_decisions,
    }
