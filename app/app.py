"""
GTM Deal Intelligence Agent — Streamlit App
Powered by Databricks

Memory support:
  Short-term: thread_id tracked per session for multi-turn conversations
  Long-term:  ae_id passed to agent for cross-session preference recall
"""

import json
import os
import uuid

import streamlit as st

st.set_page_config(page_title="GTM Deal Intelligence Agent", layout="wide")

st.markdown("""
<style>
    .tech-badge {
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 11px; font-weight: 600; margin: 2px 3px; letter-spacing: 0.02em;
    }
    .badge-vectorsearch { background: rgba(75,156,245,0.15); color: #4b9cf5; border: 1px solid rgba(75,156,245,0.3); }
    .badge-ucfunctions  { background: rgba(232,93,46,0.15);  color: #e85d2e; border: 1px solid rgba(232,93,46,0.3); }
    .badge-modelserving { background: rgba(124,109,240,0.15); color: #7c6df0; border: 1px solid rgba(124,109,240,0.3); }
    .badge-mlflow       { background: rgba(23,200,160,0.15); color: #17c8a0; border: 1px solid rgba(23,200,160,0.3); }
    .badge-langgraph    { background: rgba(94,189,58,0.15);  color: #5ebd3a; border: 1px solid rgba(94,189,58,0.3); }
    .badge-gateway      { background: rgba(255,54,33,0.12);  color: #FF3621; border: 1px solid rgba(255,54,33,0.25); }
    .badge-lakebase     { background: rgba(255,179,0,0.15);  color: #e6a800; border: 1px solid rgba(255,179,0,0.3); }
    .tech-callout {
        background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px;
    }
    .memory-indicator {
        background: rgba(255,179,0,0.08); border: 1px solid rgba(255,179,0,0.2);
        border-radius: 6px; padding: 6px 10px; margin: 4px 0; font-size: 12px;
        color: #e6a800;
    }
</style>
""", unsafe_allow_html=True)

# ── Config ───────────────────────────────────────────────────────────────

ENDPOINT_NAME = os.environ.get(
    "GTM_ENDPOINT", "agents_users-aradhya_chouhan-gtm_deal_intelligence_agent"
)

# Demo AE profiles (for long-term memory demo)
AE_PROFILES = {
    "Jamie Torres": "ae-jamie@company.com",
    "Sarah Kim": "ae-sarah@company.com",
    "(None)": "",
}

DEMO_PROMPTS = {
    "Meridian Health — Deal Health + Email": (
        "What's the deal health on OPP-3001 (Meridian Health)? "
        "Give me the score, risk flags, key contacts, and draft a follow-up email for the champion."
    ),
    "Apex Financial — Competitive Analysis": (
        "Analyze the Apex Financial security deal (OPP-3002). "
        "What's our competitive position against Palo Alto and Splunk? Pull battlecard intel."
    ),
    "NovaTech — Discovery Workshop Email": (
        "NovaTech (OPP-3003) wants to move fast on cloud migration. "
        "Draft a short email to the CTO proposing a discovery workshop."
    ),
    "Pacific Retail — POC Under Price Pressure": (
        "The Pacific Retail POC (OPP-3004) is halfway through and Freshworks is undercutting us 40% on price. "
        "What's the POC showing and how do we defend our position?"
    ),
    "Atlas Cloud — Re-engage Silent Champion": (
        "Atlas Cloud champion (OPP-3006) went quiet 2 months ago. "
        "What happened and how do we re-engage James Liu?"
    ),
}

# ── Agent query function ─────────────────────────────────────────────────


def query_agent(conversation: list[dict], thread_id: str, ae_id: str = "", account_id: str = "", save_memories: bool = False) -> dict:
    """Query the deployed agent with full conversation history + memory context.

    Sends the entire conversation (not just the last message) so the agent
    has full context for multi-turn follow-ups like "make it shorter".
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.config import Config
    # Use a 5-minute timeout — complex queries with multiple tool calls can take 2-3 min
    cfg = Config(http_timeout_seconds=300)
    w = WorkspaceClient(config=cfg)

    # Build input from full conversation (user + assistant messages)
    input_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation
        if msg["role"] in ("user", "assistant") and msg.get("content")
    ]

    body = {
        "input": input_messages,
        "custom_inputs": {
            "thread_id": thread_id,
            "ae_id": ae_id,
            "save_memories": save_memories,
        },
    }
    if account_id:
        body["custom_inputs"]["account_id"] = account_id

    return w.api_client.do(
        "POST",
        f"/serving-endpoints/{ENDPOINT_NAME}/invocations",
        body=body,
    )


def extract_text(response: dict) -> str:
    texts = []
    for item in response.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content["text"])
    return "\n".join(texts) if texts else ""


def extract_tool_calls(response: dict) -> list:
    calls = []
    for item in response.get("output", []):
        if isinstance(item, dict) and item.get("type") == "function_call":
            calls.append(item.get("name", "unknown"))
    return calls


# ── Session state ────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0

# ── Sidebar ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### GTM Deal Intelligence")
    st.caption("Powered by Databricks")
    st.divider()

    # AE selector (for long-term memory)
    st.markdown("**AE Identity** (for memory)")
    ae_name = st.selectbox(
        "Select AE",
        options=list(AE_PROFILES.keys()),
        index=0,
        label_visibility="collapsed",
    )
    ae_id = AE_PROFILES[ae_name]

    if ae_id:
        st.markdown(
            f'<div class="memory-indicator">Long-term memory active for <b>{ae_name}</b></div>',
            unsafe_allow_html=True,
        )

    # Thread info
    short_thread = st.session_state.thread_id[:8]
    st.caption(f"Session: `{short_thread}...` ({st.session_state.turn_count} turns)")

    st.divider()

    st.markdown("**Quick Scenarios**")
    for label, prompt in DEMO_PROMPTS.items():
        if st.button(label, key=f"btn_{label}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.rerun()

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("New Session", use_container_width=True):
            # Save memories from current session before clearing
            if st.session_state.messages and ae_id:
                try:
                    save_msgs = st.session_state.messages + [
                        {"role": "user", "content": "Summarize what we discussed."}
                    ]
                    query_agent(
                        save_msgs,
                        thread_id=st.session_state.thread_id,
                        ae_id=ae_id,
                        save_memories=True,
                    )
                except Exception:
                    pass  # Best-effort memory save
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.turn_count = 0
            st.rerun()
    with col2:
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.turn_count = 0
            st.rerun()

# ── Main ─────────────────────────────────────────────────────────────────

st.markdown("## Deal Intelligence Chat")

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tech_html"):
            st.markdown(msg["tech_html"], unsafe_allow_html=True)

# If last message is user and needs a response
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Querying agent (UC Functions + Vector Search + Claude Sonnet 4.6)..."):
            try:
                raw = query_agent(
                    st.session_state.messages,
                    thread_id=st.session_state.thread_id,
                    ae_id=ae_id,
                )
                text = extract_text(raw)
                tool_calls = extract_tool_calls(raw)

                st.session_state.turn_count += 1
                st.markdown(text)

                # Build tech badges
                badges = ['<span class="tech-badge badge-langgraph">LangGraph</span>']
                badges.append('<span class="tech-badge badge-modelserving">Model Serving</span>')
                for tc in tool_calls:
                    if "deal_health" in tc or "account_signals" in tc:
                        badges.append('<span class="tech-badge badge-ucfunctions">UC Functions</span>')
                    if "transcripts" in tc or "battlecards" in tc or "stories" in tc:
                        badges.append('<span class="tech-badge badge-vectorsearch">Vector Search</span>')
                badges.append('<span class="tech-badge badge-mlflow">MLflow Tracing</span>')
                # Add Lakebase badge when memory features are active
                if ae_id or st.session_state.turn_count > 1:
                    badges.append('<span class="tech-badge badge-lakebase">Lakebase Memory</span>')

                # Deduplicate
                seen = set()
                unique = [b for b in badges if not (b in seen or seen.add(b))]
                tech_html = f'<div class="tech-callout">Powered by: {" ".join(unique)}</div>'
                st.markdown(tech_html, unsafe_allow_html=True)

                st.session_state.messages.append({
                    "role": "assistant", "content": text, "tech_html": tech_html,
                })
            except Exception as e:
                st.error(f"Agent error: {str(e)[:500]}")
                st.session_state.messages.append({
                    "role": "assistant", "content": f"Error: {str(e)[:200]}",
                })

# Chat input
if prompt := st.chat_input("Ask about a deal, account, or generate outreach..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()
