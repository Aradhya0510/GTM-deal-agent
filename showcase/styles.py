"""All CSS — ServiceNow branding with Databricks co-brand."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
:root{
--ink:#05080f;--ink2:#0c1220;--ink3:#141e30;--ink4:#1c2840;
--b:rgba(255,255,255,0.06);--b2:rgba(255,255,255,0.11);--b3:rgba(255,255,255,0.18);
--txt:#e8edf5;--txt2:#8da2bd;--txt3:#4d6480;
/* ServiceNow green as primary accent */
--sn:#62D84E;--sn2:rgba(98,216,78,0.15);--sn3:rgba(98,216,78,0.08);
/* Databricks orange for co-brand */
--db:#FF3621;
/* Semantic colors */
--cyan:#00d4ff;--cyan2:rgba(0,212,255,0.12);
--teal:#00e5b4;--teal2:rgba(0,229,180,0.1);
--amber:#ffb830;--amber2:rgba(255,184,48,0.1);
--violet:#a78bfa;--violet2:rgba(167,139,250,0.1);
--rose:#fb7185;
--sans:'DM Sans',system-ui,sans-serif;--display:'Syne',system-ui,sans-serif;--mono:'DM Mono',monospace
}

/* ── Global ── */
*{box-sizing:border-box}
.stApp{background:var(--ink)!important}
.stMainBlockContainer{padding-top:1rem!important}
section[data-testid="stSidebar"]{background:var(--ink2)!important;border-right:1px solid var(--b2)!important}
header[data-testid="stHeader"]{display:none}#MainMenu{visibility:hidden}footer{visibility:hidden}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--b2);border-radius:2px}

/* ── Buttons ── */
.stButton>button{background:var(--ink3)!important;color:#fff!important;border:1px solid var(--b2)!important;font-family:var(--mono)!important;font-size:12px!important;font-weight:500!important;border-radius:6px!important}
.stButton>button:hover{background:var(--ink4)!important;border-color:var(--b3)!important}
.stButton>button[kind="primary"]{background:var(--sn)!important;border-color:var(--sn)!important;color:#000!important;font-weight:700!important}
.stButton>button[kind="primary"]:hover{opacity:.85!important}

/* ── Nav radio ── */
.stRadio label span{color:#fff!important}
.stRadio label{color:#fff!important;font-family:var(--display)!important;font-size:12px!important;font-weight:600!important;letter-spacing:.02em}
.stRadio div[role="radiogroup"]{gap:0!important}

/* ── Selectbox (only trigger, not dropdown) ── */
div[data-baseweb="select"]>div{background:var(--ink3)!important;border-color:var(--b2)!important}
div[data-baseweb="select"]>div>div{color:#fff!important}

/* ── Chat input ── */
.stChatInput textarea{background:var(--ink3)!important;border-color:var(--b2)!important;color:#fff!important;font-family:var(--sans)!important}
.stChatInput textarea:focus{border-color:var(--sn)!important}

/* ── Pulse ── */
.pulse{width:6px;height:6px;border-radius:50%;background:var(--teal);animation:pulse 2s infinite;display:inline-block}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(0,229,180,0.4)}70%{box-shadow:0 0 0 6px rgba(0,229,180,0)}100%{box-shadow:0 0 0 0 rgba(0,229,180,0)}}

/* ── Topbar ── */
.topbar{display:flex;align-items:center;height:48px;border-bottom:1px solid var(--b2);background:rgba(5,8,15,0.95);backdrop-filter:blur(12px);margin:-1rem -1rem 1rem;padding:0}
.tb-logo{display:flex;align-items:center;gap:10px;padding:0 20px;border-right:1px solid var(--b);height:100%}
.tb-logo-mark{width:22px;height:22px;background:var(--sn);border-radius:4px;display:flex;align-items:center;justify-content:center}
.tb-logo-text{font-family:var(--display);font-size:13px;font-weight:700;color:#fff}
.tb-cobrand{display:flex;align-items:center;gap:4px;padding:0 16px;border-right:1px solid var(--b);height:100%}
.tb-right{margin-left:auto;display:flex;align-items:center;height:100%}
.tb-status{display:flex;align-items:center;gap:6px;padding:0 16px;font-size:11px;color:var(--txt2);font-family:var(--mono);border-left:1px solid var(--b);height:100%}

/* ── KPI ── */
.kpi-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kpi{background:var(--ink2);border:1px solid var(--b);border-radius:8px;padding:14px 16px;position:relative;overflow:hidden}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.kpi.sn::before{background:var(--sn)}.kpi.cyan::before{background:var(--cyan)}.kpi.teal::before{background:var(--teal)}.kpi.amber::before{background:var(--amber)}
.kpi-val{font-family:var(--display);font-size:24px;font-weight:800;line-height:1;margin-bottom:4px}
.kpi.sn .kpi-val{color:var(--sn)}.kpi.cyan .kpi-val{color:var(--cyan)}.kpi.teal .kpi-val{color:var(--teal)}.kpi.amber .kpi-val{color:var(--amber)}
.kpi-label{font-size:11px;color:var(--txt3);font-family:var(--mono)}.kpi-sub{font-size:10px;color:var(--txt2);margin-top:3px}

/* ── Tags ── */
.section-label{font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--txt3);font-family:var(--mono);margin:16px 0 10px;display:flex;align-items:center;gap:8px}
.section-label::after{content:'';flex:1;height:1px;background:var(--b)}
.rflag{font-size:10px;padding:3px 7px;border-radius:3px;font-family:var(--mono);font-weight:500;display:inline-block}
.rflag.red{background:rgba(255,54,33,0.12);color:#FF3621;border:1px solid rgba(255,54,33,0.2)}
.rflag.amber{background:var(--amber2);color:var(--amber);border:1px solid rgba(255,184,48,0.2)}
.rflag.cyan{background:var(--cyan2);color:var(--cyan);border:1px solid rgba(0,212,255,0.2)}
.rflag.teal{background:var(--teal2);color:var(--teal);border:1px solid rgba(0,229,180,0.2)}
.rflag.violet{background:var(--violet2);color:var(--violet);border:1px solid rgba(167,139,250,0.2)}
.rflag.sn{background:var(--sn3);color:var(--sn);border:1px solid rgba(98,216,78,0.3)}

/* ── Priority cards ── */
.pcard{background:var(--ink2);border:1px solid var(--b);border-radius:10px;padding:16px;margin-bottom:4px}
.pcard-top{display:flex;align-items:flex-start;gap:12px;margin-bottom:10px}
.pcard-company{font-family:var(--display);font-size:14px;font-weight:700;color:#fff}
.pcard-deal{font-size:11px;color:var(--txt2);font-family:var(--mono)}
.score-ring{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--display);font-size:13px;font-weight:800;border:2px solid}
.score-high{border-color:var(--teal);color:var(--teal);background:var(--teal2)}.score-mid{border-color:var(--amber);color:var(--amber);background:var(--amber2)}.score-low{border-color:var(--rose);color:var(--rose);background:rgba(251,113,133,0.1)}
.overnight-banner{background:linear-gradient(90deg,rgba(98,216,78,0.08),transparent);border:1px solid rgba(98,216,78,0.15);border-radius:8px;padding:12px 16px;display:flex;align-items:center;gap:12px;margin-bottom:4px}
.ob-text{font-size:12px;color:var(--txt2);flex:1}.ob-text strong{color:var(--sn)}
.ob-badge{font-size:10px;font-family:var(--mono);background:var(--sn3);color:var(--sn);padding:3px 8px;border-radius:3px;border:1px solid rgba(98,216,78,0.2)}

/* ── Deal Room ── */
.dr-compact-header{display:flex;align-items:center;gap:16px;padding:10px 14px;background:var(--ink2);border:1px solid var(--b);border-radius:8px;margin-bottom:12px;flex-wrap:wrap}
.dr-compact-header .dr-item{display:flex;flex-direction:column;gap:1px}
.dr-compact-header .dr-label{font-size:9px;color:var(--txt3);font-family:var(--mono);text-transform:uppercase;letter-spacing:.05em}
.dr-compact-header .dr-value{font-size:12px;color:#fff;font-family:var(--display);font-weight:700}
.chat-msg{max-width:92%;display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
.chat-msg.user{align-self:flex-end;margin-left:auto;text-align:right}
.chat-msg.user .msg-bubble{background:var(--sn);color:#000;border-radius:10px 10px 2px 10px;font-weight:500}
.chat-msg.agent .msg-bubble{background:var(--ink3);color:#fff;border:1px solid var(--b2);border-radius:10px 10px 10px 2px}
.msg-bubble{padding:10px 13px;border-radius:10px;font-size:13px;line-height:1.55}
.msg-meta{font-size:10px;color:var(--txt3);font-family:var(--mono)}
.mem-entry{background:var(--ink3);border:1px solid rgba(167,139,250,0.15);border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:11px;color:var(--txt2);line-height:1.5}
.mem-entry strong{color:var(--violet)}
.rail-section{font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--txt3);font-family:var(--mono);margin:14px 0 6px}
.uc-strip{background:var(--ink3);border:1px solid var(--b);border-radius:6px;padding:8px 10px;display:flex;align-items:center;gap:6px;font-size:10px;color:var(--txt2);font-family:var(--mono);margin-bottom:5px}
.uc-dot{width:5px;height:5px;border-radius:50%;background:var(--teal);flex-shrink:0;display:inline-block}
.mem-chip{background:var(--violet2);border:1px solid rgba(167,139,250,0.2);border-radius:5px;padding:7px 10px;font-size:11px;color:var(--violet);font-family:var(--mono);margin-bottom:5px}
.mem-chip span{color:var(--txt2)}

/* ── Streaming ── */
.stream-cursor{display:inline-block;width:2px;height:14px;background:var(--sn);animation:cursorBlink 0.8s infinite;vertical-align:text-bottom;margin-left:2px}
@keyframes cursorBlink{0%,100%{opacity:1}50%{opacity:0}}
.tool-card-stream{animation:toolAppear 0.4s ease-out forwards;opacity:0}
@keyframes toolAppear{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── Outreach ── */
.draft-card{background:var(--ink2);border:1px solid var(--b);border-radius:10px;overflow:hidden}
.draft-subject{padding:12px 16px;border-bottom:1px solid var(--b);font-size:12px;font-family:var(--mono);color:var(--txt2)}.draft-subject strong{color:#fff}
.draft-body{padding:16px;font-size:13px;color:#fff;line-height:1.7}
.draft-footer{padding:12px 16px;border-top:1px solid var(--b);display:flex;gap:5px;flex-wrap:wrap}
.qpill{font-size:10px;font-family:var(--mono);padding:3px 7px;border-radius:3px}
.qpill.hi{background:var(--teal2);color:var(--teal);border:1px solid rgba(0,229,180,0.2)}
.qpill.mid{background:var(--amber2);color:var(--amber);border:1px solid rgba(255,184,48,0.2)}
.intel-card{background:var(--ink2);border:1px solid var(--b);border-radius:8px;padding:14px;margin-bottom:10px}
.intel-source{font-size:10px;font-family:var(--mono);color:var(--txt3);margin-bottom:4px;display:flex;align-items:center;gap:5px}
.intel-dot{width:5px;height:5px;border-radius:50%;display:inline-block}.intel-text{font-size:12px;color:var(--txt2);line-height:1.5}
.pref-tag{display:inline-flex;background:var(--violet2);border:1px solid rgba(167,139,250,0.2);color:var(--violet);font-size:10px;font-family:var(--mono);padding:3px 7px;border-radius:3px;margin:2px}

/* ── Pipeline ── */
.pipe-table{width:100%;border-collapse:collapse}
.pipe-table th{font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--txt3);font-family:var(--mono);padding:8px 12px;text-align:left;border-bottom:1px solid var(--b2)}
.pipe-table td{padding:12px;border-bottom:1px solid var(--b);font-size:12px;vertical-align:middle;color:#fff}
.pipe-table tr:hover td{background:rgba(255,255,255,.02)}
.company-cell{display:flex;align-items:center;gap:10px}
.comp-icon{width:28px;height:28px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;background:rgba(255,255,255,0.05)}
.comp-name{font-family:var(--display);font-size:13px;font-weight:700;color:#fff}.comp-vertical{font-size:10px;color:var(--txt3);font-family:var(--mono)}
.bar-track{flex:1;height:4px;background:var(--b2);border-radius:2px;overflow:hidden;min-width:60px}.bar-fill{height:100%;border-radius:2px}
.bar-val{font-size:11px;font-family:var(--mono);font-weight:600;min-width:24px}
.stage-pill{font-size:10px;font-family:var(--mono);padding:3px 8px;border-radius:3px;display:inline-block}
.stage-proposal{background:var(--cyan2);color:var(--cyan);border:1px solid rgba(0,212,255,0.2)}
.stage-disco{background:var(--amber2);color:var(--amber);border:1px solid rgba(255,184,48,0.2)}
.stage-negot{background:var(--teal2);color:var(--teal);border:1px solid rgba(0,229,180,0.2)}
.stage-eval{background:var(--violet2);color:var(--violet);border:1px solid rgba(167,139,250,0.2)}

/* ── Observatory ── */
.obs-panel{border:1px solid var(--b2);border-radius:8px;overflow:hidden;margin-bottom:8px}
.obs-header{padding:12px 16px;border-bottom:1px solid var(--b2);display:flex;align-items:center;justify-content:space-between;background:var(--ink2)}
.obs-title{font-family:var(--display);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--txt2)}
.obs-body{padding:14px;max-height:280px;overflow-y:auto}
.eval-metric-row{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.eval-label{font-size:11px;color:var(--txt2);font-family:var(--mono);min-width:130px}
.eval-track{flex:1;height:8px;background:var(--b2);border-radius:4px;overflow:hidden}.eval-fill{height:100%;border-radius:4px}
.eval-val{font-size:11px;font-family:var(--mono);font-weight:700;min-width:30px;text-align:right}
.mb-entry{background:var(--ink3);border:1px solid var(--b);border-radius:6px;padding:10px;display:flex;gap:10px;align-items:flex-start;margin-bottom:8px}
.mb-type{font-size:9px;font-family:var(--mono);padding:2px 6px;border-radius:3px;flex-shrink:0;margin-top:2px}
.mb-type.pref{background:var(--violet2);color:var(--violet);border:1px solid rgba(167,139,250,0.2)}
.mb-type.account{background:var(--cyan2);color:var(--cyan);border:1px solid rgba(0,212,255,0.2)}
.mb-type.decision{background:var(--teal2);color:var(--teal);border:1px solid rgba(0,229,180,0.2)}
.mb-content{font-size:11px;color:var(--txt2);line-height:1.5;flex:1}.mb-content strong{color:#fff}
.lw-entry{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--b)}.lw-entry:last-child{border-bottom:none}
.lw-sev{font-size:9px;font-family:var(--mono);padding:2px 6px;border-radius:3px;flex-shrink:0;margin-top:2px}
.lw-sev.ok{background:var(--teal2);color:var(--teal);border:1px solid rgba(0,229,180,0.2)}
.lw-sev.warn{background:var(--amber2);color:var(--amber);border:1px solid rgba(255,184,48,0.2)}
.lw-sev.crit{background:rgba(255,54,33,0.12);color:#FF3621;border:1px solid rgba(255,54,33,0.2)}
.lw-msg{font-size:11px;color:var(--txt2);line-height:1.5;flex:1}.lw-msg strong{color:#fff}
.lw-time{font-size:10px;color:var(--txt3);font-family:var(--mono);flex-shrink:0}
.sparkline{display:flex;align-items:flex-end;gap:2px;height:32px}
.spark-bar{width:6px;border-radius:1px;background:var(--teal)}
.trace-row{display:grid;grid-template-columns:48px 90px 1fr 42px 36px;gap:4px;align-items:center;padding:6px 0;border-bottom:1px solid var(--b)}
.tr-time{font-size:10px;font-family:var(--mono);color:var(--txt3)}.tr-agent{font-size:10px;font-family:var(--mono)}
.tr-agent.research{color:var(--cyan)}.tr-agent.scoring{color:var(--amber)}.tr-agent.memory{color:var(--violet)}

/* ═══════ AGENT X-RAY ═══════ */
.xr-panel{background:var(--ink);border:1px solid var(--b2);border-radius:10px;overflow:hidden;margin:12px 0}
.xr-header{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--b);background:linear-gradient(90deg,rgba(98,216,78,0.06),transparent)}
.xr-title{font-family:var(--display);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--sn)}
.xr-meta{font-size:10px;font-family:var(--mono);color:var(--txt3)}
.xr-flow{display:flex;gap:2px;padding:14px 16px 10px;align-items:stretch}
.xr-node{flex:1;min-width:0;text-align:center;padding:10px 4px 8px;border-radius:6px;display:flex;flex-direction:column;align-items:center;gap:2px}
.xr-node-label{font-size:8px;font-family:var(--mono);font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#fff}
.xr-node-metric{font-size:11px;font-family:var(--mono);font-weight:700}
.xr-node-sub{font-size:8px;font-family:var(--mono);color:var(--txt3)}
.xr-arrow{display:flex;align-items:center;color:var(--txt3);font-size:12px;padding:0 2px;flex-shrink:0}
.xr-tools{padding:0 16px 12px;display:flex;flex-direction:column;gap:6px}
.xr-tool{background:var(--ink2);border:1px solid var(--b);border-radius:6px;padding:10px 12px;position:relative;overflow:hidden}
.xr-tool::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px}
.xr-tool.memory::before{background:var(--violet)}.xr-tool.scoring::before{background:var(--amber)}.xr-tool.research::before{background:var(--cyan)}
.xr-tool-hdr{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.xr-tool-name{font-family:var(--mono);font-size:11px;color:#fff;flex:1}
.xr-tool-ms{font-family:var(--display);font-size:11px;font-weight:700;color:var(--txt2)}
.xr-io{font-size:10px;font-family:var(--mono);color:var(--txt3);display:flex;gap:6px;margin-top:2px}
.xr-io-label{font-weight:700;min-width:24px;flex-shrink:0}
.xr-io-label.in{color:var(--amber)}.xr-io-label.out{color:var(--teal)}
.xr-footer{display:flex;align-items:center;gap:16px;padding:10px 16px;border-top:1px solid var(--b);flex-wrap:wrap}
.xr-stat{font-size:10px;font-family:var(--mono);color:var(--txt2);display:flex;align-items:center;gap:5px}

/* ═══════ ARCHITECTURE DAG ═══════ */
.dag-container{padding:24px;background:var(--ink);border:1px solid var(--b2);border-radius:10px}
.dag-row{display:flex;justify-content:center;gap:8px;margin-bottom:4px;flex-wrap:wrap}
.dag-connector{display:flex;justify-content:center;padding:4px 0}
.dag-connector-line{width:2px;height:16px;background:var(--b3);transition:all .3s}
.dag-node{display:flex;flex-direction:column;align-items:center;gap:2px;padding:12px 16px;border-radius:8px;border:1px solid var(--b2);min-width:110px;text-align:center;transition:all .4s}
.dag-node:hover{transform:translateY(-1px)}
.dag-node-icon{font-size:16px;margin-bottom:2px}
.dag-node-title{font-family:var(--display);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#fff}
.dag-node-desc{font-size:9px;font-family:var(--mono);color:var(--txt3)}
.dag-node-badge{font-size:8px;font-family:var(--mono);padding:2px 6px;border-radius:3px;margin-top:2px}
.dag-node.sn{background:var(--sn3);border-color:rgba(98,216,78,0.3)}.dag-node.sn .dag-node-badge{background:var(--sn2);color:var(--sn)}
.dag-node.violet{background:rgba(167,139,250,0.06);border-color:rgba(167,139,250,0.2)}.dag-node.violet .dag-node-badge{background:var(--violet2);color:var(--violet)}
.dag-node.amber{background:rgba(255,184,48,0.04);border-color:rgba(255,184,48,0.2)}.dag-node.amber .dag-node-badge{background:var(--amber2);color:var(--amber)}
.dag-node.cyan{background:rgba(0,212,255,0.04);border-color:rgba(0,212,255,0.2)}.dag-node.cyan .dag-node-badge{background:var(--cyan2);color:var(--cyan)}
.dag-node.teal{background:rgba(0,229,180,0.04);border-color:rgba(0,229,180,0.2)}.dag-node.teal .dag-node-badge{background:var(--teal2);color:var(--teal)}
.dag-node.neutral{background:var(--ink2);border-color:var(--b2)}.dag-node.neutral .dag-node-badge{background:var(--b);color:var(--txt3)}

/* DAG lit states */
.dag-node.lit{box-shadow:0 0 16px rgba(0,229,180,0.35);border-color:var(--teal)!important;transition:all .3s}
.dag-node.lit-sn{box-shadow:0 0 16px rgba(98,216,78,0.35);border-color:var(--sn)!important}
.dag-node.lit-violet{box-shadow:0 0 16px rgba(167,139,250,0.35);border-color:var(--violet)!important}
.dag-node.lit-amber{box-shadow:0 0 16px rgba(255,184,48,0.35);border-color:var(--amber)!important}
.dag-node.lit-cyan{box-shadow:0 0 16px rgba(0,212,255,0.35);border-color:var(--cyan)!important}
.dag-connector-line.lit{background:var(--sn)!important;box-shadow:0 0 6px rgba(98,216,78,0.4)}
.dag-node.scanning{animation:dagScan 1.5s ease-in-out infinite}
@keyframes dagScan{0%,100%{opacity:.4}50%{opacity:1}}

/* Architecture value panel */
.arch-value-panel{background:var(--ink2);border:1px solid var(--b);border-radius:8px;padding:12px;margin-bottom:8px}
.arch-value-title{font-family:var(--display);font-size:11px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.arch-value-desc{font-size:11px;color:var(--txt2);line-height:1.5}

/* ── Flow step ── */
.flow-step{display:flex;align-items:flex-start;padding:8px 12px;background:var(--ink2);border:1px solid var(--b);border-radius:6px;margin-bottom:2px}
.flow-num{font-family:var(--display);font-size:14px;font-weight:800;color:var(--sn);margin-right:16px;min-width:24px}
.flow-label{font-family:var(--mono);font-size:10px;font-weight:600;color:var(--txt3);min-width:110px;text-transform:uppercase;letter-spacing:.04em}
.flow-desc{font-size:13px;color:#fff}
.flow-arrow{text-align:center;color:var(--txt3);font-size:12px;line-height:1.2}

/* ── Asset table ── */
.asset-table{width:100%;border-collapse:collapse;margin-top:8px}
.asset-table th{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--txt3);font-family:var(--mono);padding:8px 10px;text-align:left;border-bottom:1px solid var(--b2)}
.asset-table td{padding:8px 10px;border-bottom:1px solid var(--b);font-size:12px;color:#fff;font-family:var(--mono)}
.asset-table tr:hover td{background:rgba(255,255,255,.02)}
.asset-table a{color:var(--sn);text-decoration:none;font-weight:600}

/* ── Error card ── */
.err-card{background:rgba(255,54,33,0.06);border:1px solid rgba(255,54,33,0.2);border-radius:8px;padding:14px 16px;margin:8px 0}
.err-card .err-msg{font-size:13px;color:var(--rose);font-family:var(--sans);margin-bottom:4px;line-height:1.5}
.err-card .err-detail{font-size:10px;color:var(--txt3);font-family:var(--mono);word-break:break-all}

/* ── Demo data badge ── */
.demo-badge{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-family:var(--mono);color:var(--txt3);background:var(--ink2);border:1px solid var(--b2);border-radius:3px;padding:3px 8px;margin-left:8px;vertical-align:middle}

/* ── Deep link pills ── */
.deep-link{display:inline-flex;align-items:center;gap:4px;padding:6px 12px;background:var(--ink2);border:1px solid var(--b2);border-radius:6px;font-size:11px;font-family:var(--mono);color:var(--sn);text-decoration:none;margin:3px;transition:all .15s}
.deep-link:hover{border-color:var(--sn);background:var(--sn3)}
</style>
"""
