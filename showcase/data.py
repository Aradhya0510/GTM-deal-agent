"""
Industry demo data + helpers.
Pure data — no Streamlit dependency.
Competitors are ServiceNow's actual ITSM/ITOM/CSM competitors per vertical.
"""


def risk_flag_class(r: str) -> str:
    if any(k in r for k in ["Champion", "freeze", "silent", "No ", "ghost", "Budget",
                             "HIPAA", "procurement", "NERC", "compliance", "IT ",
                             "Atlassian", "BMC", "SAP"]):
        return "red"
    if any(k in r for k in ["Competitor", "competitive", "evaluating", "vendor",
                             "Jira", "Zendesk", "Freshworks", "Salesforce",
                             "PagerDuty", "Maximo", "IFS"]):
        return "amber"
    return "cyan"


def gauge_color(val):
    if val >= 80:
        return "var(--teal)"
    if val >= 60:
        return "var(--amber)"
    return "var(--rose)"


INDUSTRIES = {
    "finserv": {
        "icon": "🏦", "name": "Financial Services",
        "label": "financial portfolio",
        "meta": "Lakeflow ran at 05:00 · 18 financial accounts analyzed · 3 priority actions",
        "kpi": ["$4.2M", "71", "12", "3"],
        "kpi_sub": ["↑ $800K from last week", "Scored by Llama 3.1", "Agent-generated overnight", "Detected via memory"],
        "deals": [
            {"icon": "🏦", "company": "Meridian Capital Group", "vertical": "Financial Services", "arr": "$2.4M", "health": 72, "stage": "Proposal", "risks": ["Champion ghost", "BMC Helix competitive"], "stageClass": "stage-proposal"},
            {"icon": "🏦", "company": "Vantage Asset Mgmt", "vertical": "Wealth Management", "arr": "$1.8M", "health": 85, "stage": "Negotiation", "risks": ["Price sensitivity"], "stageClass": "stage-negot"},
            {"icon": "🏦", "company": "Axiom Insurance", "vertical": "Insurance", "arr": "$900K", "health": 48, "stage": "Discovery", "risks": ["Budget freeze", "Multi-vendor"], "stageClass": "stage-disco"},
            {"icon": "🏦", "company": "Sterling Private Bank", "vertical": "Private Banking", "arr": "$3.1M", "health": 91, "stage": "Evaluation", "risks": [], "stageClass": "stage-eval"},
            {"icon": "🏦", "company": "ClearPath Brokerage", "vertical": "Brokerage", "arr": "$650K", "health": 61, "stage": "Discovery", "risks": ["Champion change"], "stageClass": "stage-disco"},
        ],
        "priority": [
            {"icon": "🏦", "bg": "rgba(0,212,255,0.1)", "company": "Meridian Capital Group", "deal": "$2.4M · Proposal · 52d to close", "score": 72, "scoreClass": "score-mid", "risks": ["Champion ghost 18d", "BMC Helix competitive", "Budget uncertainty"], "action": "Draft follow-up"},
            {"icon": "🏦", "bg": "rgba(0,212,255,0.1)", "company": "Axiom Insurance", "deal": "$900K · Discovery · 90d to close", "score": 48, "scoreClass": "score-low", "risks": ["Q1 budget freeze", "No exec sponsor", "Jira SM evaluating"], "action": "Escalate to VP"},
            {"icon": "🏦", "bg": "rgba(0,212,255,0.1)", "company": "ClearPath Brokerage", "deal": "$650K · Discovery · 75d to close", "score": 61, "scoreClass": "score-mid", "risks": ["Champion changed to CTO", "Freshservice in eval"], "action": "Re-map stakeholders"},
        ],
        "dr": {"icon": "🏦", "company": "Meridian Capital Group", "vertical": "Financial Services · Enterprise", "arr": "$2.4M", "stage": "Proposal", "champion": "M. Torres (VP Eng)", "competitor": "BMC Helix", "gaugeVal": 72,
               "msg1": 'Deal health: <strong>72/100</strong> — moderate risk. Champion went quiet 18d ago. Competing with BMC Helix on ITSM consolidation. Platform adoption strong — CMDB used daily by 12 engineers.',
               "msg2": "Hi Mike,\n\nYour team's been using the CMDB daily — clearly building real operational maturity. Given your Q2 ITSM consolidation timeline, wanted to share how Axiom reduced their incident resolution time by 60% after migrating from BMC.\n\nWorth a 15-min call this week?\n\nBest, Jamie",
               "memContext": "Budget decision deferred to Q2. CFO driving final approval.",
               "risks": ["Champion went quiet · 18d", "BMC Helix evaluating concurrently", "No CFO touchpoint in 45d"]},
        "emailSubject": "Your CMDB adoption + the Q2 consolidation window",
        "emailBody": "Hi Mike,\n\nYour engineering team has been using the CMDB daily — that's a strong signal. Given your Q2 ITSM consolidation timeline, I wanted to share how a similar firm reduced incident resolution 60% after migrating from BMC Helix.\n\nWorth a quick 15-min call this week?\n\nBest, Jamie",
        "emailWC": "112 words ✓",
        "linkedIn": "Mike — saw your team's been deep in the CMDB. Your Q2 consolidation push made me think of a similar project at Axiom where we cut incident resolution in half vs BMC. Happy to share the playbook.",
        "intel1": '"We\'re locked into our Q2 board timeline — ITSM consolidation has to be done before then. Compliance auditability is our biggest concern." — Mike Torres, Mar 12',
        "intel2": "Axiom Insurance cut incident resolution 60% with ServiceNow ITSM — same regulatory constraints, migrated off BMC Helix in 8 weeks.",
        "callOpening": "Mike, thanks for the time. I know Q2 board prep is coming up fast — I wanted to walk through how our ITSM platform maps to your consolidation timeline vs BMC.",
        "callQuestions": ["What's your specific compliance requirement for the Q2 milestone?", "Who else is involved in the final vendor decision — is the CFO in the loop?", "What does success look like for incident resolution by board date?"],
        "battlecard": "vs BMC Helix: ServiceNow's single-platform approach eliminates the integration tax BMC requires across ITSM, ITOM, and CMDB. Now Assist AI is native — not bolted on. GRC module provides compliance auditability BMC can't match natively.",
    },
    "health": {
        "icon": "🏥", "name": "Healthcare",
        "label": "healthcare pipeline",
        "meta": "Lakeflow ran at 05:00 · 22 health system accounts analyzed · 4 priority actions",
        "kpi": ["$6.1M", "68", "15", "2"],
        "kpi_sub": ["↑ $1.2M from last week", "Scored by Llama 3.1", "Agent-generated overnight", "Detected via memory"],
        "deals": [
            {"icon": "🏥", "company": "NovaCare Health System", "vertical": "Health Systems", "arr": "$3.2M", "health": 79, "stage": "Proposal", "risks": ["IT procurement backlog"], "stageClass": "stage-proposal"},
            {"icon": "🏥", "company": "Meridian Diagnostics", "vertical": "Diagnostics", "arr": "$1.1M", "health": 55, "stage": "Discovery", "risks": ["HIPAA compliance concern", "Champion change"], "stageClass": "stage-disco"},
            {"icon": "🏥", "company": "Apex Pharma Research", "vertical": "Pharma", "arr": "$2.8M", "health": 88, "stage": "Negotiation", "risks": [], "stageClass": "stage-negot"},
            {"icon": "🏥", "company": "ClearVision Radiology", "vertical": "Radiology", "arr": "$750K", "health": 42, "stage": "Discovery", "risks": ["Budget freeze", "No exec sponsor"], "stageClass": "stage-disco"},
        ],
        "priority": [
            {"icon": "🏥", "bg": "rgba(0,229,180,0.1)", "company": "NovaCare Health System", "deal": "$3.2M · Proposal · 45d to close", "score": 79, "scoreClass": "score-mid", "risks": ["IT procurement 8-wk delay", "Salesforce Health Cloud competitive"], "action": "Accelerate compliance docs"},
            {"icon": "🏥", "bg": "rgba(0,229,180,0.1)", "company": "Meridian Diagnostics", "deal": "$1.1M · Discovery · 90d to close", "score": 55, "scoreClass": "score-low", "risks": ["Champion changed to CISO", "Jira SM in evaluation"], "action": "Re-engage new champion"},
            {"icon": "🏥", "bg": "rgba(0,229,180,0.1)", "company": "ClearVision Radiology", "deal": "$750K · Discovery · 80d to close", "score": 42, "scoreClass": "score-low", "risks": ["Budget frozen until H2", "No exec sponsor"], "action": "Pause or escalate"},
        ],
        "dr": {"icon": "🏥", "company": "NovaCare Health System", "vertical": "Health Systems · Enterprise", "arr": "$3.2M", "stage": "Proposal", "champion": "Dr. R. Patel (CIO)", "competitor": "Salesforce Health Cloud", "gaugeVal": 79,
               "msg1": 'Deal health: <strong>79/100</strong>. Strong clinical interest. Key risk: IT procurement 8-week delay. Salesforce Health Cloud is competing on the patient engagement angle.',
               "msg2": "Dr. Patel,\n\nFollowing up on your clinical workflow question — we've streamlined this for 3 comparable health systems while maintaining full HIPAA compliance. Happy to connect you with their CIOs.\n\nCan we find 15 min this week?\n\nBest, Jamie",
               "memContext": "HIPAA BAA review in legal — 3-week turnaround. CIO needs peer reference.",
               "risks": ["IT procurement 8-wk delay", "Salesforce Health Cloud competing", "No peer reference provided yet"]},
        "emailSubject": "Clinical workflow automation + peer health system intro",
        "emailBody": "Dr. Patel,\n\nYour clinical workflow question is exactly what three comparable health systems asked before deployment. All are live with HIPAA compliance — one is happy to do a peer call.\n\nWorth a 15 min to align?\n\nBest, Jamie",
        "emailWC": "78 words ✓",
        "linkedIn": "Dr. Patel — the clinical workflow challenge you raised is something we've solved for several health systems. Happy to connect you with a peer CIO.",
        "intel1": '"Clinical workflow automation is non-negotiable — we need to reduce nurse admin burden by 40% or the board won\'t approve." — Dr. Patel, Mar 15',
        "intel2": "St. Mary's Health achieved 45% reduction in nurse admin time using ServiceNow Clinical Device Management + ITSM integration.",
        "callOpening": "Dr. Patel, I've arranged a peer CIO from a comparable health system who went through your exact clinical workflow challenge.",
        "callQuestions": ["Where is the HIPAA BAA in your legal review?", "Would a peer CIO reference call accelerate board sign-off?", "What's the primary clinical workflow bottleneck — orders, device management, or incident response?"],
        "battlecard": "vs Salesforce Health Cloud: ServiceNow provides unified ITSM + clinical workflows on one platform — Salesforce requires separate Service Cloud + Health Cloud licenses. Our HIPAA-grade CMDB tracks every clinical device. Now Assist AI automates clinical IT triage.",
    },
    "retail": {
        "icon": "🛍️", "name": "Retail",
        "label": "retail pipeline",
        "meta": "Lakeflow ran at 05:00 · 20 retail accounts analyzed · 3 priority actions",
        "kpi": ["$3.8M", "74", "10", "1"],
        "kpi_sub": ["↑ $500K from last week", "Scored by Llama 3.1", "Agent-generated overnight", "Detected via memory"],
        "deals": [
            {"icon": "🛍️", "company": "Atlas Retail Group", "vertical": "Omnichannel Retail", "arr": "$2.1M", "health": 81, "stage": "Negotiation", "risks": ["Price sensitivity"], "stageClass": "stage-negot"},
            {"icon": "🛍️", "company": "PeakStyle Fashion", "vertical": "Fashion & Apparel", "arr": "$850K", "health": 58, "stage": "Proposal", "risks": ["Champion silent", "Zendesk competitive"], "stageClass": "stage-proposal"},
            {"icon": "🛍️", "company": "FreshMart Grocery", "vertical": "Grocery", "arr": "$1.6M", "health": 67, "stage": "Evaluation", "risks": ["Procurement freeze"], "stageClass": "stage-eval"},
            {"icon": "🛍️", "company": "Vertex Luxury", "vertical": "Luxury Goods", "arr": "$900K", "health": 44, "stage": "Discovery", "risks": ["No sponsor", "Budget unclear"], "stageClass": "stage-disco"},
        ],
        "priority": [
            {"icon": "🛍️", "bg": "rgba(255,184,48,0.1)", "company": "PeakStyle Fashion", "deal": "$850K · Proposal · 60d to close", "score": 58, "scoreClass": "score-low", "risks": ["Champion silent 22d", "Zendesk competitive", "Seasonal buying cycle risk"], "action": "Re-engage champion"},
            {"icon": "🛍️", "bg": "rgba(255,184,48,0.1)", "company": "FreshMart Grocery", "deal": "$1.6M · Evaluation · 40d to close", "score": 67, "scoreClass": "score-mid", "risks": ["Procurement freeze Q1", "Freshworks shortlisted"], "action": "Accelerate eval"},
            {"icon": "🛍️", "bg": "rgba(255,184,48,0.1)", "company": "Vertex Luxury", "deal": "$900K · Discovery · 90d to close", "score": 44, "scoreClass": "score-low", "risks": ["No exec sponsor", "Budget approval path unclear"], "action": "Map stakeholders"},
        ],
        "dr": {"icon": "🛍️", "company": "PeakStyle Fashion", "vertical": "Fashion & Apparel · Mid-Market", "arr": "$850K", "stage": "Proposal", "champion": "L. Chen (VP Customer Experience)", "competitor": "Zendesk", "gaugeVal": 58,
               "msg1": 'Deal health: <strong>58/100</strong> — elevated risk. Champion Lisa Chen quiet 22 days. Zendesk is competing on CSM — they\'re pitching lower cost of entry.',
               "msg2": "Lisa,\n\nOne number before the season freeze: a comparable fashion retailer saw 34% improvement in customer satisfaction after consolidating from Zendesk to our CSM platform — 6 weeks to go live.\n\nQuick call?\n\nBest, Jamie",
               "memContext": "Spring buying cycle freeze starts April. Lisa mentioned CSAT improvement as the key board metric.",
               "risks": ["Champion silent 22d", "Season freeze Apr deadline", "Zendesk evaluating concurrently"]},
        "emailSubject": "CSAT improvement before the season freeze",
        "emailBody": "Lisa,\n\nOne number before the season freeze: a comparable fashion retailer saw 34% CSAT improvement after consolidating from Zendesk to our CSM platform — 6-week implementation.\n\nHappy to share the playbook in a quick call.\n\nBest, Jamie",
        "emailWC": "58 words ✓",
        "linkedIn": "Lisa — CSAT improvement before the buying season freeze. A comparable retailer hit 34% improvement consolidating from Zendesk in 6 weeks. Worth a chat?",
        "intel1": '"Our board metric is CSAT — if you can move that number, the conversation gets much easier." — Lisa Chen, Feb 28',
        "intel2": "StyleCo Fashion achieved 34% CSAT lift in 6 weeks migrating from Zendesk to ServiceNow CSM — same seasonal constraints.",
        "callOpening": "Lisa, a retailer in your exact position — same seasonal constraints — hit 34% CSAT improvement migrating off Zendesk. Can I walk you through it?",
        "callQuestions": ["What's the internal approval path before the April freeze?", "Is CSAT the primary board metric, or are there secondary metrics?", "What would a pilot need to show to get full approval?"],
        "battlecard": "vs Zendesk: ServiceNow CSM provides end-to-end customer operations — not just ticketing. Proactive case management, AI-powered routing, and full ITSM integration that Zendesk can't match. Now Assist AI resolves 40% of L1 cases automatically.",
    },
    "mfg": {
        "icon": "🏭", "name": "Manufacturing",
        "label": "manufacturing pipeline",
        "meta": "Lakeflow ran at 05:00 · 15 manufacturing accounts analyzed · 2 priority actions",
        "kpi": ["$5.7M", "69", "8", "2"],
        "kpi_sub": ["↑ $900K from last week", "Scored by Llama 3.1", "Agent-generated overnight", "Detected via memory"],
        "deals": [
            {"icon": "🏭", "company": "Orion Industrial Systems", "vertical": "Discrete Manufacturing", "arr": "$3.4M", "health": 76, "stage": "Proposal", "risks": ["Long procurement cycle"], "stageClass": "stage-proposal"},
            {"icon": "🏭", "company": "Vertex Precision Parts", "vertical": "Precision Manufacturing", "arr": "$1.2M", "health": 51, "stage": "Discovery", "risks": ["Champion change", "IFS competing"], "stageClass": "stage-disco"},
            {"icon": "🏭", "company": "Cascade Automation", "vertical": "Industrial Automation", "arr": "$2.1M", "health": 83, "stage": "Negotiation", "risks": [], "stageClass": "stage-negot"},
        ],
        "priority": [
            {"icon": "🏭", "bg": "rgba(167,139,250,0.1)", "company": "Orion Industrial Systems", "deal": "$3.4M · Proposal · 65d to close", "score": 76, "scoreClass": "score-mid", "risks": ["18-wk procurement cycle", "SAP PM integration concern", "IBM Maximo evaluating"], "action": "Accelerate POC"},
            {"icon": "🏭", "bg": "rgba(167,139,250,0.1)", "company": "Vertex Precision Parts", "deal": "$1.2M · Discovery · 85d to close", "score": 51, "scoreClass": "score-low", "risks": ["Champion changed to COO", "IFS competing on EAM"], "action": "Re-engage COO"},
        ],
        "dr": {"icon": "🏭", "company": "Orion Industrial Systems", "vertical": "Discrete Manufacturing · Enterprise", "arr": "$3.4M", "stage": "Proposal", "champion": "K. Yamamoto (CDO)", "competitor": "IBM Maximo", "gaugeVal": 76,
               "msg1": 'Deal health: <strong>76/100</strong>. Strong CDO interest. Blocker: 18-wk procurement + SAP PM integration validation. IBM Maximo is the incumbent they\'re comparing against.',
               "msg2": "Kenji,\n\nYour SAP integration question has a concrete answer — 3 manufacturers validated ServiceNow + SAP PM on your exact version. One is happy to do a peer call.\n\n15 min this week?\n\nBest, Jamie",
               "memContext": "SAP PM validation is the technical gate. CDO wants connected operations demo before board review.",
               "risks": ["18-wk procurement cycle", "SAP PM integration unvalidated", "IBM Maximo incumbent"]},
        "emailSubject": "SAP PM validation + connected operations demo",
        "emailBody": "Kenji,\n\nYour SAP PM integration question has a concrete answer — 3 manufacturers validated this on your exact SAP version. One is happy to do a peer call.\n\nAlso want to get you a connected operations demo before your board review. 15 min this week?\n\nBest, Jamie",
        "emailWC": "64 words ✓",
        "linkedIn": "Kenji — the SAP PM integration you raised is validated with manufacturers on your exact SAP version. Happy to connect you with a peer CDO who replaced Maximo.",
        "intel1": '"SAP is the backbone — if ServiceNow doesn\'t integrate cleanly with SAP PM, we stay with Maximo regardless of the automation story." — Kenji Yamamoto, Mar 10',
        "intel2": "Apex Motors replaced IBM Maximo with ServiceNow ITOM + Field Service — SAP PM integration validated in 3 weeks, connected operations live in 8 weeks.",
        "callOpening": "Kenji, I've lined up a peer CDO at Apex Motors who replaced Maximo and ran your exact SAP version through the same integration validation.",
        "callQuestions": ["What SAP module does the integration touch — PM, QM, PP?", "Who from IT needs to be in the integration validation call?", "Board review in 4 or 6 weeks?"],
        "battlecard": "vs IBM Maximo: ServiceNow provides a unified platform for ITSM + ITOM + Field Service — Maximo is EAM-only with no native IT service management. Our Connected Operations gives real-time OT visibility that Maximo can't match. Now Assist AI automates work order triage.",
    },
    "tech": {
        "icon": "💻", "name": "Technology",
        "label": "technology pipeline",
        "meta": "Lakeflow ran at 05:00 · 28 tech accounts analyzed · 5 priority actions",
        "kpi": ["$8.4M", "77", "18", "4"],
        "kpi_sub": ["↑ $1.5M from last week", "Scored by Llama 3.1", "Agent-generated overnight", "Detected via memory"],
        "deals": [
            {"icon": "💻", "company": "Nexus Cloud Platforms", "vertical": "Cloud Infrastructure", "arr": "$4.2M", "health": 83, "stage": "Negotiation", "risks": ["Price pressure"], "stageClass": "stage-negot"},
            {"icon": "💻", "company": "Axiom SaaS Co", "vertical": "B2B SaaS", "arr": "$1.9M", "health": 62, "stage": "Proposal", "risks": ["Champion change", "Atlassian evaluating"], "stageClass": "stage-proposal"},
            {"icon": "💻", "company": "Quantum AI Labs", "vertical": "AI/ML", "arr": "$2.3M", "health": 71, "stage": "Evaluation", "risks": ["Jira SM vs ServiceNow"], "stageClass": "stage-eval"},
            {"icon": "💻", "company": "Cascade DevTools", "vertical": "Developer Tooling", "arr": "$800K", "health": 45, "stage": "Discovery", "risks": ["Budget freeze", "No sponsor"], "stageClass": "stage-disco"},
        ],
        "priority": [
            {"icon": "💻", "bg": "rgba(0,212,255,0.1)", "company": "Quantum AI Labs", "deal": "$2.3M · Evaluation · 50d to close", "score": 71, "scoreClass": "score-mid", "risks": ["Jira SM deeply embedded", "PagerDuty for incidents", "Engineering team prefers Atlassian"], "action": "Strengthen platform story"},
            {"icon": "💻", "bg": "rgba(0,212,255,0.1)", "company": "Axiom SaaS Co", "deal": "$1.9M · Proposal · 55d to close", "score": 62, "scoreClass": "score-mid", "risks": ["Champion changed to new CTO", "Atlassian suite entrenched"], "action": "Engage new CTO"},
            {"icon": "💻", "bg": "rgba(0,212,255,0.1)", "company": "Cascade DevTools", "deal": "$800K · Discovery · 90d to close", "score": 45, "scoreClass": "score-low", "risks": ["Budget frozen H1", "No exec sponsor", "Open-source ITSM culture"], "action": "Pause and re-qualify"},
        ],
        "dr": {"icon": "💻", "company": "Quantum AI Labs", "vertical": "AI/ML · Scale-up", "arr": "$2.3M", "stage": "Evaluation", "champion": "A. Sharma (CTO)", "competitor": "Atlassian (Jira SM)", "gaugeVal": 71,
               "msg1": 'Deal health: <strong>71/100</strong>. Jira Service Management is deeply embedded. CTO Aditya Sharma sees the platform consolidation value but engineering team resists change from Atlassian.',
               "msg2": "Aditya,\n\nYour team knows Jira well — the question isn't capability, it's scale. When you hit 500+ engineers, Jira SM's lack of native ITOM and CMDB becomes the bottleneck. We've quantified this for 4 similar teams.\n\n15 min to compare?\n\nBest, Jamie",
               "memContext": "CTO sees platform value but engineering team resists. Key: show the scale ceiling of Atlassian and total cost of the tool sprawl (Jira + Confluence + OpsGenie + Statuspage).",
               "risks": ["Jira SM deeply embedded", "Engineering team resists change", "PagerDuty for incidents"]},
        "emailSubject": "The scale ceiling of Jira SM (what happens at 500+ engineers)",
        "emailBody": "Aditya,\n\nYour team knows Jira well. The question is what happens at scale.\n\nAt 500+ engineers, the Atlassian tool sprawl (Jira + Confluence + OpsGenie + Statuspage) costs more than a unified platform. We've quantified this for 4 similar teams.\n\n15 min to compare?\n\nBest, Jamie",
        "emailWC": "69 words ✓",
        "linkedIn": "Aditya — Jira SM works well at your current scale. The hidden cost is the tool sprawl at 500+ engineers: Jira + Confluence + OpsGenie + Statuspage. Happy to share the breakdown from comparable AI teams.",
        "intel1": '"We\'re on Jira for everything — my concern is the tool sprawl as we scale. We have 6 Atlassian products and the integration tax is real." — Aditya Sharma, Mar 8',
        "intel2": "NeuralEdge AI consolidated from 5 Atlassian products to ServiceNow — saved $400K/yr in licensing and reduced incident resolution from 45min to 12min.",
        "callOpening": "Aditya, your team knows Jira. I want to share what comparable AI teams experienced when they hit the scale ceiling: the real cost of tool sprawl and where consolidation pays off.",
        "callQuestions": ["How many Atlassian products are you running today?", "What's your incident response workflow — Jira + PagerDuty + Slack?", "Is there a board or funding milestone driving the platform decision?"],
        "battlecard": "vs Atlassian (Jira SM): ServiceNow is a single platform for ITSM + ITOM + CMDB + SecOps — Atlassian requires 5+ separate products (Jira, Confluence, OpsGenie, Statuspage, Compass). At scale, the integration tax exceeds the platform cost. Now Assist AI provides native automation Atlassian can't match.",
    },
    "energy": {
        "icon": "⚡", "name": "Energy",
        "label": "energy pipeline",
        "meta": "Lakeflow ran at 05:00 · 12 energy accounts analyzed · 2 priority actions",
        "kpi": ["$7.2M", "65", "6", "1"],
        "kpi_sub": ["↑ $600K from last week", "Scored by Llama 3.1", "Agent-generated overnight", "Detected via memory"],
        "deals": [
            {"icon": "⚡", "company": "Apex Energy Solutions", "vertical": "Renewables", "arr": "$4.1M", "health": 74, "stage": "Proposal", "risks": ["Long regulatory cycle"], "stageClass": "stage-proposal"},
            {"icon": "⚡", "company": "GridTech Utilities", "vertical": "Electric Utility", "arr": "$2.8M", "health": 58, "stage": "Discovery", "risks": ["OT/IT security concern", "Champion change"], "stageClass": "stage-disco"},
            {"icon": "⚡", "company": "Cascade Oil & Gas", "vertical": "Oil & Gas", "arr": "$1.4M", "health": 82, "stage": "Negotiation", "risks": [], "stageClass": "stage-negot"},
        ],
        "priority": [
            {"icon": "⚡", "bg": "rgba(255,184,48,0.1)", "company": "Apex Energy Solutions", "deal": "$4.1M · Proposal · 70d to close", "score": 74, "scoreClass": "score-mid", "risks": ["NERC CIP compliance gap", "SAP EAM incumbent", "No CISO alignment"], "action": "Schedule compliance workshop"},
            {"icon": "⚡", "bg": "rgba(255,184,48,0.1)", "company": "GridTech Utilities", "deal": "$2.8M · Discovery · 95d to close", "score": 58, "scoreClass": "score-low", "risks": ["Champion changed to new CISO", "IFS competing on asset management"], "action": "Re-engage with OT story"},
        ],
        "dr": {"icon": "⚡", "company": "Apex Energy Solutions", "vertical": "Renewables · Enterprise", "arr": "$4.1M", "stage": "Proposal", "champion": "T. Okonkwo (CDO)", "competitor": "SAP EAM + IFS", "gaugeVal": 74,
               "msg1": 'Deal health: <strong>74/100</strong>. Strong CDO sponsorship. Blocker: NERC CIP compliance validation not started. SAP EAM is the incumbent; IFS is also competing on asset management.',
               "msg2": "Taiwo,\n\nThe NERC CIP compliance path is defined — we've navigated it with 2 utilities. Our OT/IT convergence on ServiceNow replaces the SAP EAM + point tool sprawl.\n\n15 min to map the timeline?\n\nBest, Jamie",
               "memContext": "NERC CIP is the regulatory gate. CDO needs CISO aligned. Connected Operations is the key differentiator vs SAP EAM.",
               "risks": ["NERC CIP compliance not started", "SAP EAM incumbent", "IFS also evaluating"]},
        "emailSubject": "NERC CIP compliance + OT/IT convergence on one platform",
        "emailBody": "Taiwo,\n\nNERC CIP validation has a defined path — we've run it with 2 utilities in under 10 weeks. ServiceNow Connected Operations replaces the SAP EAM + point tool sprawl with a single platform.\n\nWorth a 15-min call?\n\nBest, Jamie",
        "emailWC": "67 words ✓",
        "linkedIn": "Taiwo — NERC CIP compliance for OT/IT convergence: we've navigated it with utilities in under 10 weeks. Our Connected Operations replaces the SAP EAM + point tool sprawl.",
        "intel1": '"NERC CIP is non-negotiable — and honestly, managing compliance across SAP EAM plus 4 other tools is the real pain point." — Taiwo Okonkwo, Mar 5',
        "intel2": "Western Power replaced SAP EAM with ServiceNow ITOM + Connected Operations — NERC CIP compliance achieved in 9 weeks, eliminated 3 point tools.",
        "callOpening": "Taiwo, I have the exact compliance timeline from Western Power: 9 weeks to NERC CIP on ServiceNow, replacing SAP EAM and 3 point tools.",
        "callQuestions": ["Is there a FERC audit date driving the timeline?", "Is your CISO in the loop on OT/IT convergence?", "How many point tools are you managing alongside SAP EAM today?"],
        "battlecard": "vs SAP EAM + IFS: ServiceNow provides unified ITSM + ITOM + Connected Operations on one platform — SAP EAM handles asset management only, requiring bolt-on tools for ITSM, incident management, and compliance. IFS is strong in field service but lacks ITSM entirely. Our CMDB gives full OT/IT asset visibility.",
    },
}
