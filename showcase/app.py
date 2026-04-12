"""ServiceNow · Mission Control — Powered by Databricks"""

import json, time, uuid
import streamlit as st

st.set_page_config(page_title="ServiceNow · Mission Control", page_icon="🟢", layout="wide", initial_sidebar_state="expanded")

from backend import (ENDPOINT_NAME, CATALOG, SCHEMA, SQL_WAREHOUSE_ID, WORKSPACE_URL, WORKSPACE_ID,
    AE_PROFILES, run_app_sql, query_agent, extract_text, extract_tool_calls,
    classify_tool, tool_type_label, tool_color, fetch_mlflow_experiment_stats)
from data import INDUSTRIES, risk_flag_class, gauge_color
from styles import CSS
from components import render_xray, render_dag

# Deep links
AL = {k: f"{WORKSPACE_URL}/explore/data/{CATALOG}/{SCHEMA}/{k}?o={WORKSPACE_ID}" for k in
      ["gtm_accounts","calculate_deal_health","get_account_signals","gtm_transcripts_idx","gtm_battlecards_idx",
       "gtm_stories_idx","memory_ae_profiles","memory_account_context","memory_deal_decisions","audit_agent_access"]}
AL["endpoint"] = f"{WORKSPACE_URL}/serving-endpoints/{ENDPOINT_NAME}/invocations?o={WORKSPACE_ID}"
AL["model"] = f"{WORKSPACE_URL}/explore/data/models/{CATALOG}/{SCHEMA}/gtm_deal_intelligence_agent?o={WORKSPACE_ID}"
AL["experiment"] = f"{WORKSPACE_URL}/ml/experiments?searchFilter=name%3D%27gtm-deal-intelligence%27&o={WORKSPACE_ID}"
AL["warehouse"] = f"{WORKSPACE_URL}/sql/warehouses/{SQL_WAREHOUSE_ID}?o={WORKSPACE_ID}"
AL["vs_endpoint"] = f"{WORKSPACE_URL}/compute/vector-search/dbdemos_vs_endpoint?o={WORKSPACE_ID}"

st.markdown(CSS, unsafe_allow_html=True)


# ── Reliable blocking agent call ──
def _call_agent(ae_id):
    msgs = []
    uc = 0
    for m in st.session_state.messages:
        r, c = m["role"], m.get("content", "")
        if r == "user":
            uc += 1
            if uc == 1 and ae_id:
                c = f"[AE: {ae_id}] {c}"
        if r in ("user", "assistant") and c:
            msgs.append({"role": r, "content": c})
    with st.spinner("Agent processing..."):
        t0 = time.time()
        try:
            resp = query_agent(msgs, thread_id=st.session_state.thread_id, ae_id=ae_id)
            lat = time.time() - t0
            tcs = extract_tool_calls(resp)
            st.session_state.messages.append({"role": "assistant", "content": extract_text(resp), "tool_calls": tcs, "latency": lat})
            st.session_state.total_latency += lat
            st.session_state.tool_call_history.extend(tcs)
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Error: `{type(e).__name__}: {e}`", "tool_calls": [], "latency": 0})


# ── State ──
for k, v in [("industry","finserv"),("pipe_filter","all"),("messages",[]),("thread_id",str(uuid.uuid4())),
             ("tool_call_history",[]),("total_latency",0),("pending_prompt",None),("active_tab",0),
             ("dag_result",None),("dag_animating",False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ──
with st.sidebar:
    st.markdown('<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px"><div style="width:28px;height:28px;background:var(--sn);border-radius:5px;display:flex;align-items:center;justify-content:center"><svg viewBox="0 0 16 16" width="15" height="15"><polygon points="8,1 15,5 15,11 8,15 1,11 1,5" fill="white"/></svg></div><span style="font-family:var(--display);font-size:15px;font-weight:800;color:#fff">ServiceNow</span></div><div style="font-size:9px;color:var(--txt3);font-family:var(--mono);margin-bottom:16px">Powered by <span style="color:var(--db)">Databricks</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="rail-section">AE identity</div>', unsafe_allow_html=True)
    ae_name = st.selectbox("AE", list(AE_PROFILES.keys()), index=0, label_visibility="collapsed")
    ae_id = AE_PROFILES[ae_name]["id"]
    if ae_id:
        st.markdown(f'<div class="mem-chip"><span>Lakebase ·</span> {ae_name}</div>', unsafe_allow_html=True)

    st.markdown('<div class="rail-section">Industry vertical</div>', unsafe_allow_html=True)
    ik = ["finserv","health","retail","mfg","tech","energy"]
    il = ["🏦 Financial Services","🏥 Healthcare","🛍️ Retail","🏭 Manufacturing","💻 Technology","⚡ Energy"]
    ci = ik.index(st.session_state.industry) if st.session_state.industry in ik else 0
    sel = st.radio("Ind", il, index=ci, label_visibility="collapsed", key="ir")
    ni = ik[il.index(sel)]
    if ni != st.session_state.industry:
        st.session_state.industry = ni
        st.session_state.messages, st.session_state.tool_call_history = [], []
        st.session_state.thread_id, st.session_state.total_latency = str(uuid.uuid4()), 0
        st.rerun()

    st.markdown(f'<div style="margin-top:20px;padding-top:12px;border-top:1px solid var(--b2)"><div class="rail-section">Session</div><div class="uc-strip"><div class="uc-dot" style="background:var(--violet)"></div>thread · {st.session_state.thread_id[:8]}</div><div class="uc-strip"><div class="uc-dot"></div>turns · {len([m for m in st.session_state.messages if m["role"]=="user"])}</div></div>', unsafe_allow_html=True)
    if st.button("New session", use_container_width=True, key="ns"):
        st.session_state.messages, st.session_state.tool_call_history = [], []
        st.session_state.thread_id, st.session_state.total_latency = str(uuid.uuid4()), 0
        st.session_state.dag_result, st.session_state.dag_animating = None, False
        st.rerun()

    st.markdown('<div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--b2)"><div class="rail-section">System</div><div class="uc-strip"><span class="pulse"></span>&nbsp;Lakewatch: 0 alerts</div><div class="uc-strip"><div class="uc-dot"></div>UC · West Territory</div><div class="uc-strip"><div class="uc-dot"></div>MLflow traced</div></div>', unsafe_allow_html=True)

# ── Topbar + Nav ──
d = INDUSTRIES[st.session_state.industry]
st.markdown('<div class="topbar"><div class="tb-logo"><div class="tb-logo-mark"><svg viewBox="0 0 16 16" width="13" height="13"><polygon points="8,1 15,5 15,11 8,15 1,11 1,5" fill="white"/></svg></div><span class="tb-logo-text">ServiceNow · Mission Control</span></div><div class="tb-cobrand"><span style="font-size:9px;color:var(--txt3);font-family:var(--mono)">Powered by</span><span style="font-size:9px;color:var(--db);font-family:var(--mono);font-weight:600;margin-left:3px">Databricks</span></div><div class="tb-right"><div class="tb-status"><span class="pulse"></span>&nbsp;Lakewatch</div><div class="tb-status">UC · West</div><div class="tb-status">MLflow</div></div></div>', unsafe_allow_html=True)

TAB_NAMES = ["Morning Briefing", "Deal Room", "Architecture", "Outreach Studio", "Pipeline", "Observatory"]
active = st.radio("nav", TAB_NAMES, index=st.session_state.active_tab, horizontal=True, label_visibility="collapsed", key="nav")
st.session_state.active_tab = TAB_NAMES.index(active)
page = st.session_state.active_tab


# ══════════════════════════════════════════
# PAGE 0: MORNING BRIEFING
# ══════════════════════════════════════════
if page == 0:
    st.markdown(f'<div style="font-family:var(--display);font-size:22px;font-weight:800;color:#fff">Good morning. Here\'s your <span style="color:var(--sn)">{d["label"]}</span> intelligence.</div><div style="font-size:11px;color:var(--txt3);font-family:var(--mono);margin:4px 0 12px">{d["meta"]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="overnight-banner"><span style="font-size:16px">⚙️</span><div class="ob-text"><strong>Lakeflow pipeline</strong> ran overnight · Deal health scored · Memory extracted · 3 anomalies</div><div class="ob-badge">Genie Code</div></div>', unsafe_allow_html=True)
    colors = ["sn","cyan","teal","amber"]
    labels = ["At-risk pipeline","Avg health score","Drafts ready","Champion changes"]
    kh = '<div class="kpi-strip">'
    for i in range(4):
        kh += f'<div class="kpi {colors[i]}"><div class="kpi-val">{d["kpi"][i]}</div><div class="kpi-label">{labels[i]}</div><div class="kpi-sub">{d["kpi_sub"][i]}</div></div>'
    st.markdown(kh+'</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Priority actions · agent-ranked</div>', unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns(3)
    for i, (col, p) in enumerate(zip([pc1, pc2, pc3], d["priority"])):
        with col:
            rh = ''.join(f'<span class="rflag {risk_flag_class(r)}">{r}</span>' for r in p["risks"])
            st.markdown(f'<div class="pcard"><div class="pcard-top"><div style="width:32px;height:32px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:14px;background:{p["bg"]}">{p["icon"]}</div><div style="flex:1"><div class="pcard-company">{p["company"]}</div><div class="pcard-deal">{p["deal"]}</div></div><div class="score-ring {p["scoreClass"]}">{p["score"]}</div></div><div style="display:flex;flex-wrap:wrap;gap:5px">{rh}</div></div>', unsafe_allow_html=True)
            if st.button(f"⚡ {p['action']}", key=f"pa{i}", use_container_width=True):
                st.session_state.pending_prompt = f"{p['action']} for {p['company']}. Context: {p['deal']}. Risks: {', '.join(p['risks'])}. Use my AE preferences."
                st.session_state.active_tab = 1
                st.rerun()
            if st.button(f"🔍 View intel", key=f"pi{i}", use_container_width=True):
                st.session_state.pending_prompt = f"Full intelligence briefing on {p['company']}. {p['deal']}. Pull deal health, signals, transcripts, battlecards."
                st.session_state.active_tab = 1
                st.rerun()


# ══════════════════════════════════════════
# PAGE 1: DEAL ROOM
# Pattern: render history, detect unprocessed user msg, call agent in-place,
#          reveal tool cards one-by-one with delays, then show text. No st.rerun() after call.
# ══════════════════════════════════════════
elif page == 1:
    dr = d["dr"]
    cc, cr2 = st.columns([3, 1])

    with cc:
        color = gauge_color(dr["gaugeVal"])
        st.markdown(f'''<div class="dr-compact-header">
            <div class="dr-item"><div class="dr-label">AE</div><div class="dr-value">{ae_name if ae_id else "None"}</div></div>
            <div class="dr-item"><div class="dr-label">Account</div><div class="dr-value">{dr["company"]}</div></div>
            <div class="dr-item"><div class="dr-label">Thread</div><div class="dr-value">{st.session_state.thread_id[:6]}</div></div>
            <div class="dr-item"><div class="dr-label">Health</div><div class="dr-value" style="color:{color}">{dr["gaugeVal"]}</div></div>
            <div class="dr-item"><div class="dr-label">Stage</div><div class="dr-value">{dr["stage"]}</div></div>
            <div class="dr-item"><div class="dr-label">vs</div><div class="dr-value">{dr["competitor"]}</div></div>
        </div>''', unsafe_allow_html=True)

        # Handle pending prompt first (inject into messages before rendering)
        if st.session_state.pending_prompt:
            prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None
            st.session_state.messages.append({"role": "user", "content": prompt})

        # Render completed messages (all messages that have already been answered)
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-msg user"><div class="msg-bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)
            elif msg["role"] == "assistant":
                tcs, lat, cnt = msg.get("tool_calls",[]), msg.get("latency",0), msg.get("content","")
                if tcs:
                    render_xray(tcs, lat, st.session_state.thread_id)
                if cnt:
                    st.markdown(f'<div class="chat-msg agent"><div class="msg-bubble">{cnt}</div><div class="msg-meta">Agent · {lat:.1f}s · {len(tcs)} tools</div></div>', unsafe_allow_html=True)

        # If last message is user (unprocessed), call agent NOW and render inline
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            # Show loading indicator
            status_ph = st.empty()
            status_ph.markdown('<div style="font-size:11px;color:var(--sn);font-family:var(--mono);padding:8px 0">⏳ Agent processing — calling tools...</div>', unsafe_allow_html=True)

            # Build messages for API
            msgs = []
            uc = 0
            for m in st.session_state.messages:
                r, c = m["role"], m.get("content", "")
                if r == "user":
                    uc += 1
                    if uc == 1 and ae_id:
                        c = f"[AE: {ae_id}] {c}"
                if r in ("user", "assistant") and c:
                    msgs.append({"role": r, "content": c})

            t0 = time.time()
            try:
                resp = query_agent(msgs, thread_id=st.session_state.thread_id, ae_id=ae_id)
                lat = time.time() - t0
                tcs = extract_tool_calls(resp)
                text = extract_text(resp)

                # Clear loading
                status_ph.empty()

                # Reveal tool cards one by one with small delays
                if tcs:
                    for i, tc in enumerate(tcs):
                        cat = classify_tool(tc["name"])
                        clr = tool_color(tc["name"])
                        lbl = tool_type_label(tc["name"])
                        args_raw = tc.get("arguments", "")
                        try:
                            ap = json.loads(args_raw) if isinstance(args_raw, str) and args_raw else {}
                            args_d = ", ".join(f'{k}="{v}"' for k, v in ap.items())
                        except Exception:
                            args_d = str(args_raw)[:100]
                        out_raw = str(tc.get("output","") or "")
                        out_d = out_raw[:200] + ("..." if len(out_raw)>200 else "")
                        st.markdown(f'''<div class="xr-tool {cat}" style="animation:toolAppear 0.4s ease-out forwards;margin-bottom:6px">
                            <div class="xr-tool-hdr"><span class="rflag {clr}">{lbl}</span><span class="xr-tool-name">{tc["name"]}</span><span class="xr-tool-ms">{lat/max(len(tcs),1)*1000:.0f}ms</span></div>
                            <div class="xr-io"><span class="xr-io-label in">IN</span><span>{args_d}</span></div>
                            <div class="xr-io"><span class="xr-io-label out">OUT</span><span>{out_d}</span></div>
                        </div>''', unsafe_allow_html=True)
                        time.sleep(0.3)  # Visual delay between cards

                # Show agent response text
                if text:
                    st.markdown(f'<div class="chat-msg agent"><div class="msg-bubble">{text}</div><div class="msg-meta">Agent · {lat:.1f}s · {len(tcs)} tools</div></div>', unsafe_allow_html=True)

                # Store in session state
                st.session_state.messages.append({"role": "assistant", "content": text, "tool_calls": tcs, "latency": lat})
                st.session_state.total_latency += lat
                st.session_state.tool_call_history.extend(tcs)

            except Exception as e:
                status_ph.empty()
                err_msg = f"Error: `{type(e).__name__}: {e}`"
                st.markdown(f'<div class="chat-msg agent"><div class="msg-bubble">{err_msg}</div></div>', unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": err_msg, "tool_calls": [], "latency": 0})

        # Chat input (always at the bottom)
        user_msg = st.chat_input("Ask about this deal, refine the draft, explore risks...", key="dc")
        if user_msg:
            st.session_state.messages.append({"role": "user", "content": user_msg})
            st.rerun()

    with cr2:
        st.markdown('<div style="font-family:var(--display);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#fff;margin-bottom:8px">Memory + Context</div>', unsafe_allow_html=True)
        for ml,mv in [("Email length","Under 120 words"),("CTA",'"15-min call"'),("Avoid","Do not mention Salesforce")]:
            st.markdown(f'<div class="mem-entry"><strong>{ml}</strong><br>{mv}</div>', unsafe_allow_html=True)
        st.markdown('<div class="rail-section">Risk flags</div>', unsafe_allow_html=True)
        for r in dr["risks"]:
            st.markdown(f'<div class="rflag red" style="display:block;margin-bottom:4px">⚠ {r}</div>', unsafe_allow_html=True)
        if st.session_state.tool_call_history:
            st.markdown('<div class="rail-section">Tool usage</div>', unsafe_allow_html=True)
            tc_c = {}
            for tc in st.session_state.tool_call_history:
                tc_c[tc["name"]] = tc_c.get(tc["name"],0)+1
            for nm,ct in tc_c.items():
                st.markdown(f'<div class="uc-strip"><div class="uc-dot" style="background:var(--{tool_color(nm)})"></div>{tool_type_label(nm)} · {ct}x</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════
# PAGE 2: ARCHITECTURE (CSS animation DAG)
# ══════════════════════════════════════════
elif page == 2:
    arch_l, arch_r = st.columns([2.5, 1])

    with arch_l:
        st.markdown('<div style="font-family:var(--display);font-size:18px;font-weight:800;color:#fff;margin-bottom:4px">Agent Architecture · Powertrain View</div><div style="font-size:12px;color:var(--txt2);margin-bottom:16px">Watch the query flow through every component — nodes light up in sequence.</div>', unsafe_allow_html=True)

        # Show animated or static DAG
        dag_res = st.session_state.dag_result
        is_animating = st.session_state.dag_animating

        if is_animating:
            # Inject a CSS-only animation that plays a smooth node-by-node sequence
            # Each node gets animation-delay staggered by 0.5s
            # The animation runs once in the browser, purely client-side
            st.markdown("""
            <style>
            .dag-anim .dag-node{opacity:0.3;transition:none}
            .dag-anim .dag-connector-line{opacity:0.3;transition:none}
            .dag-anim .dag-node.a0{animation:nodeLit 0.6s ease 0.2s forwards}
            .dag-anim .dag-connector-line.c0{animation:edgeLit 0.3s ease 0.6s forwards}
            .dag-anim .dag-node.a1{animation:nodeLit 0.6s ease 0.8s forwards}
            .dag-anim .dag-connector-line.c1{animation:edgeLit 0.3s ease 1.2s forwards}
            .dag-anim .dag-node.a2{animation:nodeLit 0.6s ease 1.4s forwards}
            .dag-anim .dag-connector-line.c2{animation:edgeLit 0.3s ease 1.8s forwards}
            .dag-anim .dag-node.a3{animation:nodeLit 0.6s ease 2.0s forwards}
            .dag-anim .dag-connector-line.c3{animation:edgeLit 0.3s ease 2.4s forwards}
            .dag-anim .dag-node.a4{animation:nodeLit 0.6s ease 2.6s forwards}
            .dag-anim .dag-node.a4b{animation:nodeLit 0.6s ease 2.8s forwards}
            .dag-anim .dag-node.a4c{animation:nodeLit 0.6s ease 3.0s forwards}
            .dag-anim .dag-node.a4d{animation:nodeLit 0.6s ease 3.2s forwards}
            .dag-anim .dag-node.a4e{animation:nodeLit 0.6s ease 3.4s forwards}
            .dag-anim .dag-connector-line.c4{animation:edgeLit 0.3s ease 3.6s forwards}
            .dag-anim .dag-node.a5{animation:nodeLit 0.6s ease 3.8s forwards}
            .dag-anim .dag-connector-line.c5{animation:edgeLit 0.3s ease 4.2s forwards}
            .dag-anim .dag-node.a6{animation:nodeLit 0.6s ease 4.4s forwards}
            .dag-anim .dag-connector-line.c6{animation:edgeLit 0.3s ease 4.8s forwards}
            .dag-anim .dag-node.a7{animation:nodeLit 0.6s ease 5.0s forwards}
            @keyframes nodeLit{from{opacity:0.3;box-shadow:none}to{opacity:1;box-shadow:0 0 20px rgba(98,216,78,0.4)}}
            @keyframes edgeLit{from{opacity:0.3;background:var(--b3)}to{opacity:1;background:var(--sn);box-shadow:0 0 8px rgba(98,216,78,0.5)}}
            </style>
            <div class="dag-container dag-anim">
              <div class="dag-row"><div class="dag-node neutral a0"><div class="dag-node-icon">💬</div><div class="dag-node-title">Streamlit App</div><div class="dag-node-desc">User query + AE context</div><div class="dag-node-badge">Databricks Apps</div></div></div>
              <div class="dag-connector"><div class="dag-connector-line c0"></div></div>
              <div class="dag-row"><div class="dag-node sn a1"><div class="dag-node-icon">⚡</div><div class="dag-node-title">Model Serving</div><div class="dag-node-desc">ResponsesAgent · MLflow</div><div class="dag-node-badge">Endpoint</div></div></div>
              <div class="dag-connector"><div class="dag-connector-line c1"></div></div>
              <div class="dag-row"><div class="dag-node teal a2"><div class="dag-node-icon">🛡️</div><div class="dag-node-title">Pre-Guardrail</div><div class="dag-node-desc">Injection scan · 12 patterns</div><div class="dag-node-badge">Inline</div></div></div>
              <div class="dag-connector"><div class="dag-connector-line c2"></div></div>
              <div class="dag-row"><div class="dag-node violet a3"><div class="dag-node-icon">🧠</div><div class="dag-node-title">Lakebase Memory</div><div class="dag-node-desc">recall → 3 Delta tables</div><div class="dag-node-badge">SQL Warehouse</div></div></div>
              <div class="dag-connector"><div class="dag-connector-line c3"></div></div>
              <div class="dag-row" style="gap:12px">
                <div class="dag-node amber a4"><div class="dag-node-icon">⚙️</div><div class="dag-node-title">UC: Deal Health</div><div class="dag-node-desc">calculate_deal_health</div><div class="dag-node-badge">UC Function</div></div>
                <div class="dag-node amber a4b"><div class="dag-node-icon">📊</div><div class="dag-node-title">UC: Signals</div><div class="dag-node-desc">get_account_signals</div><div class="dag-node-badge">UC Function</div></div>
                <div class="dag-node cyan a4c"><div class="dag-node-icon">🔍</div><div class="dag-node-title">VS: Transcripts</div><div class="dag-node-desc">gtm_transcripts_idx</div><div class="dag-node-badge">Vector Search</div></div>
                <div class="dag-node cyan a4d"><div class="dag-node-icon">⚔️</div><div class="dag-node-title">VS: Battlecards</div><div class="dag-node-desc">gtm_battlecards_idx</div><div class="dag-node-badge">Vector Search</div></div>
                <div class="dag-node cyan a4e"><div class="dag-node-icon">📖</div><div class="dag-node-title">VS: Stories</div><div class="dag-node-desc">gtm_stories_idx</div><div class="dag-node-badge">Vector Search</div></div>
              </div>
              <div class="dag-connector"><div class="dag-connector-line c4"></div></div>
              <div class="dag-row"><div class="dag-node teal a5"><div class="dag-node-icon">🤖</div><div class="dag-node-title">Claude Sonnet 4.6</div><div class="dag-node-desc">Reasoning + generation</div><div class="dag-node-badge">LLM Gateway</div></div></div>
              <div class="dag-connector"><div class="dag-connector-line c5"></div></div>
              <div class="dag-row"><div class="dag-node teal a6"><div class="dag-node-icon">🛡️</div><div class="dag-node-title">Post-Guardrail</div><div class="dag-node-desc">PII scan</div><div class="dag-node-badge">Inline</div></div></div>
              <div class="dag-connector"><div class="dag-connector-line c6"></div></div>
              <div class="dag-row"><div class="dag-node sn a7"><div class="dag-node-icon">✅</div><div class="dag-node-title">Response</div><div class="dag-node-desc">Text + tool cards</div><div class="dag-node-badge">Streamlit</div></div></div>
            </div>
            """, unsafe_allow_html=True)

            # Meanwhile, run the actual query in the background
            st.markdown('<div style="font-size:11px;color:var(--sn);font-family:var(--mono);margin:8px 0">⏳ Running real query through pipeline...</div>', unsafe_allow_html=True)
            test_prompt = "What's the deal health on OPP-3001 (Meridian Health)? Score, risk flags, contacts, and draft a follow-up email."
            api_msgs = [{"role": "user", "content": f"[AE: {ae_id}] {test_prompt}" if ae_id else test_prompt}]
            t0 = time.time()
            try:
                resp = query_agent(api_msgs, thread_id=str(uuid.uuid4()), ae_id=ae_id)
                lat = time.time() - t0
                tcs = extract_tool_calls(resp)
                txt = extract_text(resp)
                st.session_state.dag_result = {"tool_calls": tcs, "latency": lat, "text": txt, "tool_names": [tc["name"] for tc in tcs]}
            except Exception as e:
                st.session_state.dag_result = {"tool_calls": [], "latency": 0, "text": f"Error: {e}", "tool_names": []}
            st.session_state.dag_animating = False
            st.rerun()

        elif dag_res and dag_res.get("tool_names"):
            # Show final lit state with real data
            st.markdown(f'<div style="font-size:11px;color:var(--teal);font-family:var(--mono);margin-bottom:8px">✓ Completed in {dag_res["latency"]:.1f}s — {len(dag_res["tool_calls"])} tools fired — active nodes lit</div>', unsafe_allow_html=True)
            render_dag(active_tools=dag_res["tool_names"])
            render_xray(dag_res["tool_calls"], dag_res["latency"], "test")
            with st.expander("Agent response text", expanded=False):
                st.markdown(dag_res.get("text", "No text"))
        else:
            # Static dim DAG
            render_dag()

        # Button to trigger animation + query
        if st.button("🔬 Run Test Query Through Pipeline", key="dag_test", use_container_width=True):
            st.session_state.dag_animating = True
            st.session_state.dag_result = None
            st.rerun()

        # Lifecycle + assets
        st.markdown('<div style="font-family:var(--display);font-size:14px;font-weight:700;color:#fff;margin:24px 0 12px">Request Lifecycle</div>', unsafe_allow_html=True)
        for num,lbl,desc in [("01","[APP]","User query in Streamlit"),("02","[SERVING]","Endpoint with ae_id + thread_id"),("03","[GUARD]","Injection scan (12 patterns)"),("04","[LAKEBASE]","Load memory from 3 Delta tables"),("05","[LANGGRAPH]","Agent tool-calling loop"),("06","[UC FUNC]","deal_health + account_signals"),("07","[VEC SEARCH]","transcripts + battlecards + stories"),("08","[CLAUDE]","Grounded response generation"),("09","[GUARD]","PII scan"),("10","[APP]","Response with X-Ray")]:
            st.markdown(f'<div class="flow-step"><span class="flow-num">{num}</span><span class="flow-label">{lbl}</span><span class="flow-desc">{desc}</span></div><div class="flow-arrow">↓</div>', unsafe_allow_html=True)

        st.markdown('<div style="font-family:var(--display);font-size:14px;font-weight:700;color:#fff;margin:24px 0 12px">Asset Directory</div>', unsafe_allow_html=True)
        assets = [("gtm_deal_intelligence_agent","Model","Agent v2","model"),(ENDPOINT_NAME,"Endpoint","Serving","endpoint"),("calculate_deal_health","UC Function","Score","calculate_deal_health"),("get_account_signals","UC Function","Signals","get_account_signals"),("gtm_transcripts_idx","VS Index","Transcripts","gtm_transcripts_idx"),("gtm_battlecards_idx","VS Index","Battlecards","gtm_battlecards_idx"),("gtm_stories_idx","VS Index","Stories","gtm_stories_idx"),("memory_ae_profiles","Lakebase","AE prefs","memory_ae_profiles"),("memory_account_context","Lakebase","Account facts","memory_account_context"),("memory_deal_decisions","Lakebase","Decisions","memory_deal_decisions")]
        rows = ''.join(f'<tr><td>{n}</td><td><span class="rflag {"violet" if "Lakebase" in t else "amber" if "UC" in t else "cyan" if "VS" in t else "teal"}">{t}</span></td><td style="color:var(--txt2)">{r}</td><td><a href="{AL.get(lk,"#")}" target="_blank">&rarr;</a></td></tr>' for n,t,r,lk in assets)
        st.markdown(f'<table class="asset-table"><thead><tr><th>Asset</th><th>Type</th><th>Role</th><th>Open</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)

    with arch_r:
        st.markdown('<div style="font-family:var(--display);font-size:12px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:.04em;margin-bottom:12px">Node Value Guide</div>', unsafe_allow_html=True)
        for title, color, desc in [
            ("Streamlit App", "sn", "User-facing interface on Databricks Apps. Captures AE identity and routes queries."),
            ("Model Serving", "sn", "Hosts ResponsesAgent as scalable REST endpoint with SSE streaming support."),
            ("Pre-Guardrail", "teal", "Regex injection scan (12 patterns). Blocks adversarial inputs before LLM."),
            ("Lakebase Memory", "violet", "Loads AE preferences + account context from 3 Delta tables via SQL API."),
            ("UC Functions", "amber", "Serverless SQL: deal health scoring (0-100) + account 360 signals."),
            ("Vector Search", "cyan", "Semantic retrieval: Gong transcripts, battlecards, deal stories."),
            ("Claude Sonnet 4.6", "teal", "LLM reasoning via Databricks LLM Gateway. Grounded generation."),
            ("Post-Guardrail", "teal", "PII leakage scan (email/phone/SSN). Logs to audit table."),
        ]:
            st.markdown(f'<div class="arch-value-panel"><div class="arch-value-title" style="color:var(--{color})">{title}</div><div class="arch-value-desc">{desc}</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════
# PAGE 3: OUTREACH STUDIO (unchanged)
# ══════════════════════════════════════════
elif page == 3:
    ce, cli, cca = st.columns(3)
    with ce:
        st.markdown(f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px"><div style="font-family:var(--display);font-size:12px;font-weight:700;text-transform:uppercase;color:#fff">✉️ Email</div><span class="rflag teal">0.91</span></div><div class="draft-card"><div class="draft-subject">Subject: <strong>{d["emailSubject"]}</strong></div><div class="draft-body">{d["emailBody"].replace(chr(10),"<br>")}</div><div class="draft-footer"><span class="qpill hi">Grounded 0.94</span><span class="qpill hi">{d["emailWC"]}</span><span class="qpill hi">Pref ✓</span></div></div>', unsafe_allow_html=True)
        st.button("Approve → Salesforce", key="ae_b", use_container_width=True)
        st.markdown('<div class="rail-section">Memory applied</div><div><span class="pref-tag">email_max_words: 120</span><span class="pref-tag">avoid: Salesforce</span><span class="pref-tag">CTA: 15-min call</span></div>', unsafe_allow_html=True)
    with cli:
        st.markdown(f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px"><div style="font-family:var(--display);font-size:12px;font-weight:700;text-transform:uppercase;color:#fff">💼 LinkedIn</div><span class="rflag cyan">0.87</span></div><div class="draft-card"><div class="draft-body">{d["linkedIn"]}</div><div class="draft-footer"><span class="qpill hi">Grounded 0.89</span><span class="qpill mid">Retrieval x2</span></div></div>', unsafe_allow_html=True)
        st.button("Copy to LinkedIn", key="cl_b", use_container_width=True)
        st.markdown(f'<div class="rail-section">Retrieved intel</div><div class="intel-card"><div class="intel-source"><div class="intel-dot" style="background:var(--cyan)"></div>Gong</div><div class="intel-text">{d["intel1"]}</div></div><div class="intel-card"><div class="intel-source"><div class="intel-dot" style="background:var(--teal)"></div>Win story</div><div class="intel-text">{d["intel2"]}</div></div>', unsafe_allow_html=True)
    with cca:
        qh = ''.join(f'<div style="background:var(--ink2);border:1px solid var(--b);border-radius:6px;padding:8px 10px;font-size:12px;color:#fff;margin-bottom:6px">&rarr; {q}</div>' for q in d["callQuestions"])
        st.markdown(f'<div style="font-family:var(--display);font-size:12px;font-weight:700;text-transform:uppercase;color:#fff;margin-bottom:12px">📞 Call Talk Track</div><div class="rail-section">Opening</div><div style="font-size:13px;color:#fff;line-height:1.65;background:var(--ink2);border:1px solid var(--b);border-radius:8px;padding:12px;margin-bottom:12px">{d["callOpening"]}</div><div class="rail-section">Key questions</div>{qh}<div class="rail-section">Battlecard</div><div style="background:var(--ink2);border:1px solid rgba(0,212,255,0.15);border-radius:8px;padding:12px;font-size:12px;color:#fff;line-height:1.6">{d["battlecard"]}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════
# PAGE 4: PIPELINE (unchanged)
# ══════════════════════════════════════════
elif page == 4:
    st.markdown('<div style="font-family:var(--display);font-size:15px;font-weight:800;color:#fff;margin-bottom:16px">Pipeline Intelligence</div>', unsafe_allow_html=True)
    fo = {"All":"all","At Risk":"risk","High Health":"high","Proposal":"proposal"}
    sf = st.radio("F", list(fo.keys()), index=list(fo.values()).index(st.session_state.pipe_filter) if st.session_state.pipe_filter in fo.values() else 0, horizontal=True, label_visibility="collapsed", key="pfr")
    nf = fo[sf]
    if nf != st.session_state.pipe_filter:
        st.session_state.pipe_filter = nf; st.rerun()
    deals = d["deals"]
    if nf=="risk": deals=[x for x in deals if x["health"]<65]
    elif nf=="high": deals=[x for x in deals if x["health"]>=80]
    elif nf=="proposal": deals=[x for x in deals if x["stage"]=="Proposal"]
    rows = ''
    for dl in deals:
        bc = gauge_color(dl["health"])
        rh = ' '.join('<span class="rflag '+risk_flag_class(r)+'">'+r+'</span>' for r in dl["risks"])
        rows += f'<tr><td><div class="company-cell"><div class="comp-icon">{dl["icon"]}</div><div><div class="comp-name">{dl["company"]}</div><div class="comp-vertical">{dl["vertical"]}</div></div></div></td><td><div style="display:flex;align-items:center;gap:8px"><div class="bar-track"><div class="bar-fill" style="width:{dl["health"]}%;background:{bc}"></div></div><span class="bar-val" style="color:{bc}">{dl["health"]}</span></div></td><td style="font-family:var(--mono);font-weight:600">{dl["arr"]}</td><td><span class="stage-pill {dl["stageClass"]}">{dl["stage"]}</span></td><td>{rh}</td></tr>'
    st.markdown(f'<table class="pipe-table"><thead><tr><th>Account</th><th>Health</th><th>ARR</th><th>Stage</th><th>Risk flags</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)


# ══════════════════════════════════════════
# PAGE 5: OBSERVATORY (real data + deep links)
# ══════════════════════════════════════════
elif page == 5:
    o1, o2 = st.columns(2)
    with o1:
        mlflow_stats = fetch_mlflow_experiment_stats()
        run_count = mlflow_stats.get("run_count", 0)
        recent = mlflow_stats.get("recent_runs", [])
        exp_link = AL.get("experiment", "#")
        if recent:
            import datetime
            th = ""
            for r in recent:
                ts = datetime.datetime.fromtimestamp(r["start_time"]/1000).strftime("%H:%M") if r["start_time"] else "--:--"
                dur = r.get("duration_ms", 0)
                sc = "teal" if r["status"] == "FINISHED" else "amber" if r["status"] == "RUNNING" else "rose"
                th += f'<div class="trace-row"><div class="tr-time">{ts}</div><div class="tr-agent" style="color:var(--{sc})">{r["status"][:7]}</div><div style="font-size:10px;font-family:var(--mono);color:var(--txt2)">run_{r["run_id"]}</div><div class="tr-ms">{dur}ms</div><div style="font-size:10px;color:var(--teal)">-</div></div>'
        else:
            th = '<div style="font-size:11px;color:var(--txt3);font-family:var(--mono)">No runs found. Query the agent to generate traces.</div>'
        st.markdown(f'<div class="obs-panel"><div class="obs-header"><div class="obs-title">MLflow Traces</div><div style="display:flex;gap:8px;align-items:center"><a href="{exp_link}" target="_blank" style="font-size:10px;font-family:var(--mono);color:var(--sn);text-decoration:none">Open Experiment &rarr;</a><span style="font-size:10px;font-family:var(--mono);color:var(--teal)">{run_count} runs</span></div></div><div class="obs-body">{th}</div></div>', unsafe_allow_html=True)

    with o2:
        if st.session_state.tool_call_history:
            tc_c = {}
            for tc in st.session_state.tool_call_history:
                tc_c[tc["name"]] = tc_c.get(tc["name"],0)+1
            bars = ""
            mx = max(tc_c.values()) if tc_c else 1
            for nm,ct in sorted(tc_c.items(), key=lambda x:-x[1]):
                w = int(ct/mx*100)
                c = tool_color(nm)
                bars += f'<div style="display:flex;align-items:center;margin:6px 0"><span style="font-size:10px;font-family:var(--mono);color:var(--txt2);min-width:180px">{nm}</span><div style="flex:1;height:8px;background:var(--b2);border-radius:4px;margin:0 8px"><div style="width:{w}%;height:100%;background:var(--{c});border-radius:4px"></div></div><span style="font-size:10px;font-family:var(--mono);color:var(--txt3)">{ct}</span></div>'
            ep_link = AL.get("endpoint", "#")
            st.markdown(f'<div class="obs-panel"><div class="obs-header"><div class="obs-title">Tool Usage · Session</div><div><a href="{ep_link}" target="_blank" style="font-size:10px;font-family:var(--mono);color:var(--sn);text-decoration:none">Endpoint &rarr;</a></div></div><div class="obs-body"><div style="font-size:11px;color:var(--txt2);font-family:var(--mono);margin-bottom:8px">{st.session_state.total_latency:.1f}s total · {len(st.session_state.tool_call_history)} calls</div>{bars}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="obs-panel"><div class="obs-header"><div class="obs-title">Tool Usage · Session</div></div><div class="obs-body"><div style="font-size:11px;color:var(--txt3)">No tool calls yet. Query the agent to see live data.</div></div></div>', unsafe_allow_html=True)

    o3, o4 = st.columns(2)
    with o3:
        eh2, ec = "", 0
        if ae_id:
            prefs = run_app_sql(f"SELECT email_style FROM {CATALOG}.{SCHEMA}.memory_ae_profiles WHERE ae_id = '{ae_id}'")
            if prefs:
                es = prefs[0].get("email_style","{}")
                try: es = json.loads(es) if isinstance(es,str) else es
                except: es = {}
                if es.get("max_words"):
                    eh2 += f'<div class="mb-entry"><div class="mb-type pref">PREF</div><div><div class="mb-content"><strong>max_words</strong> · {es["max_words"]}</div></div></div>'; ec+=1
            ctx = run_app_sql(f"SELECT a.company_name, c.content FROM {CATALOG}.{SCHEMA}.memory_account_context c LEFT JOIN {CATALOG}.{SCHEMA}.gtm_accounts a ON c.account_id=a.account_id WHERE c.ae_id='{ae_id}' AND c.confidence>0.80 ORDER BY c.extracted_at DESC LIMIT 5")
            for r in (ctx or []):
                eh2 += f'<div class="mb-entry"><div class="mb-type account">ACCT</div><div><div class="mb-content"><strong>{r.get("company_name","")}</strong> · {r.get("content","")}</div></div></div>'; ec+=1
        if ec==0:
            eh2 = '<div style="font-size:11px;color:var(--txt3)">Select an AE to load memory.</div>'
        mem_link = AL.get("memory_ae_profiles","#")
        st.markdown(f'<div class="obs-panel"><div class="obs-header"><div class="obs-title">Memory · Lakebase</div><div style="display:flex;gap:8px;align-items:center"><a href="{mem_link}" target="_blank" style="font-size:10px;font-family:var(--mono);color:var(--sn);text-decoration:none">Tables &rarr;</a><span style="font-size:10px;font-family:var(--mono);color:var(--violet)">{ec} entries</span></div></div><div class="obs-body">{eh2}</div></div>', unsafe_allow_html=True)

    with o4:
        ad = run_app_sql(f"SELECT event_type, detail, created_at FROM {CATALOG}.{SCHEMA}.audit_agent_access ORDER BY created_at DESC LIMIT 8")
        audit_link = AL.get("audit_agent_access","#")
        if ad:
            lh = ''.join(f'<div class="lw-entry"><div class="lw-sev {"crit" if "injection" in r.get("event_type","") else "ok"}">{("ALERT" if "injection" in r.get("event_type","") else "CLEAR")}</div><div class="lw-msg"><strong>{r.get("event_type","")}</strong> · {str(r.get("detail",""))[:60]}</div><div class="lw-time">{str(r.get("created_at",""))[:16]}</div></div>' for r in ad)
        else:
            lh = '<div style="font-size:11px;color:var(--txt3)">No audit events yet.</div>'
        st.markdown(f'<div class="obs-panel"><div class="obs-header"><div class="obs-title">Lakewatch</div><div style="display:flex;gap:8px;align-items:center"><a href="{audit_link}" target="_blank" style="font-size:10px;font-family:var(--mono);color:var(--sn);text-decoration:none">Audit Log &rarr;</a><span style="font-size:10px;font-family:var(--mono);color:var(--teal)"><span class="pulse"></span> 0 alerts</span></div></div><div class="obs-body">{lh}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">Workspace Deep Links</div>', unsafe_allow_html=True)
    links = [("MLflow Experiment",AL["experiment"]),("Serving Endpoint",AL["endpoint"]),("SQL Warehouse",AL["warehouse"]),("Model Registry",AL["model"]),("Vector Search",AL["vs_endpoint"]),("CRM Tables",AL["gtm_accounts"]),("Audit Table",AL["audit_agent_access"])]
    lh = ''.join(f'<a href="{url}" target="_blank" class="deep-link">{name} &rarr;</a>' for name,url in links)
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:4px">{lh}</div>', unsafe_allow_html=True)
