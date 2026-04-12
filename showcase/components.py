"""Rendering components — X-Ray, DAG, streaming tool cards."""

import json
import streamlit as st
from backend import classify_tool, tool_type_label, tool_color


def render_xray(tool_calls, total_latency, thread_id):
    """Agent X-Ray powertrain display."""
    if not tool_calls and total_latency == 0:
        return
    n = len(tool_calls)
    guard_t, llm_t = 0.05, max(total_latency * 0.30, 0.3)
    tool_t = max(total_latency - guard_t - llm_t, 0.1)
    per_tool_t = tool_t / max(n, 1)
    has = {cat: any(classify_tool(tc["name"]) == cat for tc in tool_calls) for cat in ("memory", "scoring", "research")}

    nodes = [("INPUT", "txt3", "→", "query"), ("GUARD", "teal", f"{guard_t:.1f}s", "✓ pass")]
    if has["memory"]:
        nodes.append(("MEMORY", "violet", f"{per_tool_t:.1f}s", "loaded"))
    if has["scoring"]:
        nodes.append(("SCORING", "amber", f"{per_tool_t:.1f}s", f"{sum(1 for tc in tool_calls if classify_tool(tc['name'])=='scoring')} calls"))
    if has["research"]:
        nodes.append(("SEARCH", "cyan", f"{per_tool_t:.1f}s", f"{sum(1 for tc in tool_calls if classify_tool(tc['name'])=='research')} idx"))
    nodes += [("LLM", "teal", f"{llm_t:.1f}s", "Claude"), ("OUTPUT", "sn", f"{total_latency:.1f}s", "total")]

    flow_html = ""
    for i, (label, color, metric, sub) in enumerate(nodes):
        if i > 0:
            flow_html += '<div class="xr-arrow">&rarr;</div>'
        bg = f"var(--{color}2)" if color not in ("txt3",) else "var(--b)"
        bt = f"2px solid var(--{color})" if color not in ("txt3",) else "2px solid var(--b2)"
        flow_html += f'<div class="xr-node" style="background:{bg};border-top:{bt}"><div class="xr-node-label">{label}</div><div class="xr-node-metric" style="color:var(--{color})">{metric}</div><div class="xr-node-sub">{sub}</div></div>'

    tool_html = ""
    for tc in tool_calls:
        cat = classify_tool(tc["name"])
        color = tool_color(tc["name"])
        try:
            ap = json.loads(tc.get("arguments", "")) if isinstance(tc.get("arguments"), str) and tc.get("arguments") else {}
            args_d = ", ".join(f'{k}="{v}"' for k, v in ap.items())
        except Exception:
            args_d = str(tc.get("arguments", ""))[:120]
        out_raw = str(tc.get("output", "") or "")
        out_d = out_raw[:250] + ("..." if len(out_raw) > 250 else "")
        tool_html += f'<div class="xr-tool {cat}"><div class="xr-tool-hdr"><span class="rflag {color}">{tool_type_label(tc["name"])}</span><span class="xr-tool-name">{tc["name"]}</span><span class="xr-tool-ms">{per_tool_t*1000:.0f}ms</span></div><div class="xr-io"><span class="xr-io-label in">IN</span><span>{args_d}</span></div><div class="xr-io"><span class="xr-io-label out">OUT</span><span>{out_d}</span></div></div>'

    st.markdown(f'<div class="xr-panel"><div class="xr-header"><span class="xr-title">AGENT X-RAY</span><span class="xr-meta">thread · {thread_id[:6]} | {total_latency:.1f}s | {n} tools</span></div><div class="xr-flow">{flow_html}</div><div class="xr-tools">{tool_html}</div><div class="xr-footer"><span class="xr-stat"><span class="uc-dot" style="background:var(--teal)"></span>GUARDRAIL ✓</span><span class="xr-stat"><span class="uc-dot" style="background:var(--violet)"></span>MEMORY {"loaded" if has["memory"] else "skip"}</span><span class="xr-stat"><span class="uc-dot" style="background:var(--cyan)"></span>TOOLS {n}</span><span class="xr-stat"><span class="uc-dot" style="background:var(--amber)"></span>LATENCY {total_latency:.1f}s</span></div></div>', unsafe_allow_html=True)


def render_dag(active_tools=None, scanning=False):
    """Architecture DAG. active_tools: list of tool names whose nodes glow. scanning: all nodes pulse."""
    active = set()
    if active_tools:
        active.update(["app", "endpoint", "guard_pre", "guard_post", "llm", "response"])
        for t in active_tools:
            cat = classify_tool(t)
            if cat == "memory": active.add("memory")
            elif cat == "scoring":
                active.add("uc_health" if "deal_health" in t else "uc_signals")
            elif cat == "research":
                if "transcripts" in t: active.add("vs_trans")
                elif "battlecards" in t: active.add("vs_battle")
                elif "stories" in t: active.add("vs_stories")

    def n(nid, color, icon, title, desc, badge):
        extra = ""
        if scanning:
            extra = " scanning"
        elif nid in active:
            extra = f" lit-{color}" if color in ("sn", "violet", "amber", "cyan") else " lit"
        return f'<div class="dag-node {color}{extra}"><div class="dag-node-icon">{icon}</div><div class="dag-node-title">{title}</div><div class="dag-node-desc">{desc}</div><div class="dag-node-badge">{badge}</div></div>'

    def conn(lit=False):
        cls = " lit" if lit else ""
        return f'<div class="dag-connector"><div class="dag-connector-line{cls}"></div></div>'

    has_active = bool(active_tools)
    st.markdown(f'''<div class="dag-container">
      <div class="dag-row">{n("app","neutral","💬","Streamlit App","User query + AE context","Databricks Apps")}</div>
      {conn(has_active)}
      <div class="dag-row">{n("endpoint","sn","⚡","Model Serving","ResponsesAgent · MLflow 3.0","Endpoint")}</div>
      {conn(has_active)}
      <div class="dag-row">{n("guard_pre","teal","🛡️","Pre-Guardrail","Injection scan · 12 patterns","Inline")}</div>
      {conn(has_active)}
      <div class="dag-row">{n("memory","violet","🧠","Lakebase Memory","recall → 3 Delta tables","SQL Warehouse")}</div>
      {conn("memory" in active)}
      <div class="dag-row" style="gap:12px">
        {n("uc_health","amber","⚙️","UC: Deal Health","calculate_deal_health","UC Function")}
        {n("uc_signals","amber","📊","UC: Signals","get_account_signals","UC Function")}
        {n("vs_trans","cyan","🔍","VS: Transcripts","gtm_transcripts_idx","Vector Search")}
        {n("vs_battle","cyan","⚔️","VS: Battlecards","gtm_battlecards_idx","Vector Search")}
        {n("vs_stories","cyan","📖","VS: Stories","gtm_stories_idx","Vector Search")}
      </div>
      {conn(has_active)}
      <div class="dag-row">{n("llm","teal","🤖","Claude Sonnet 4.6","Reasoning + generation","LLM Gateway")}</div>
      {conn(has_active)}
      <div class="dag-row">{n("guard_post","teal","🛡️","Post-Guardrail","PII scan · email/phone/SSN","Inline")}</div>
      {conn(has_active)}
      <div class="dag-row">{n("response","sn","✅","Response","Text + tool cards + memory","Streamlit")}</div>
    </div>''', unsafe_allow_html=True)


def render_streaming_tool_card(tc, status="done"):
    """Render a single tool card during streaming. status: 'calling' or 'done'."""
    cat = classify_tool(tc["name"])
    color = tool_color(tc["name"])
    badge = '<span class="rflag teal">done</span>' if status == "done" else '<span class="rflag amber">calling...</span>'
    anim = " tool-card-stream" if status == "calling" else ""
    out = ""
    if status == "done" and tc.get("output"):
        raw = str(tc["output"])
        out = f'<div class="xr-io"><span class="xr-io-label out">OUT</span><span>{raw[:150]}{"..." if len(raw)>150 else ""}</span></div>'
    st.markdown(f'<div class="xr-tool {cat}{anim}"><div class="xr-tool-hdr"><span class="rflag {color}">{tool_type_label(tc["name"])}</span><span class="xr-tool-name">{tc["name"]}</span>{badge}</div>{out}</div>', unsafe_allow_html=True)
