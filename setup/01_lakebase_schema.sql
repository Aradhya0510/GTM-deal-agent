-- ============================================================================
-- 01 · Lakebase — CRM operational tables + long-term memory tables
-- ============================================================================
-- Run against your Lakebase Postgres instance (gtm-memory).
-- Requires: Lakebase instance provisioned in your workspace.
-- ============================================================================

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  CRM OPERATIONAL TABLES                                                 ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS gtm.accounts (
    account_id      VARCHAR PRIMARY KEY,
    company_name    VARCHAR NOT NULL,
    industry        VARCHAR,
    arr             NUMERIC(12,2),
    employee_count  INTEGER,
    territory       VARCHAR,
    csm_owner       VARCHAR,
    ae_owner        VARCHAR,
    health_score    NUMERIC(4,2),
    last_updated    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gtm.contacts (
    contact_id      VARCHAR PRIMARY KEY,
    account_id      VARCHAR REFERENCES gtm.accounts(account_id),
    full_name       VARCHAR NOT NULL,
    title           VARCHAR,
    email           VARCHAR,
    personal_email  VARCHAR,
    phone           VARCHAR,
    role_type       VARCHAR,       -- 'champion' | 'economic_buyer' | 'technical_evaluator' | 'blocker'
    engagement_score NUMERIC(4,2),
    last_contacted  TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gtm.opportunities (
    opp_id          VARCHAR PRIMARY KEY,
    account_id      VARCHAR REFERENCES gtm.accounts(account_id),
    opp_name        VARCHAR NOT NULL,
    stage           VARCHAR,       -- Discovery | Technical Validation | Proposal | Negotiation | Closed Won | Closed Lost
    amount          NUMERIC(12,2),
    close_date      DATE,
    next_step       TEXT,
    competing_with  VARCHAR[],
    champion_id     VARCHAR REFERENCES gtm.contacts(contact_id),
    territory       VARCHAR,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gtm.outreach_log (
    log_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opp_id          VARCHAR REFERENCES gtm.opportunities(opp_id),
    ae_id           VARCHAR,
    channel         VARCHAR,       -- email | linkedin | call
    subject         TEXT,
    draft_text      TEXT,
    approved        BOOLEAN DEFAULT FALSE,
    sent_at         TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  LONG-TERM MEMORY TABLES                                                ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- AE preference profile — persists across all sessions for this AE
CREATE TABLE IF NOT EXISTS gtm.memory_ae_profiles (
    ae_id               VARCHAR PRIMARY KEY,
    email_style         JSONB,          -- {"max_words": 150, "tone": "direct", ...}
    outreach_prefs      JSONB,          -- {"preferred_cta": "15-min call", ...}
    avoid_competitors   VARCHAR[],
    formatting_prefs    JSONB,          -- {"bullet_points": false, "sign_off": "Best, Jamie"}
    raw_preferences     TEXT[],         -- Verbatim extracted preference statements
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- Account-level cross-session context — shared across AEs on same account
CREATE TABLE IF NOT EXISTS gtm.memory_account_context (
    account_id          VARCHAR,
    context_type        VARCHAR,        -- 'champion_change' | 'budget_freeze' | 'competitor_mentioned' | ...
    content             TEXT,           -- Human-readable fact
    source_thread_id    VARCHAR,        -- Which conversation this came from
    ae_id               VARCHAR,        -- Who surfaced it
    confidence          FLOAT,          -- Extraction confidence 0-1
    extracted_at        TIMESTAMP DEFAULT NOW(),
    expires_at          TIMESTAMP,      -- Optional TTL for stale facts
    PRIMARY KEY (account_id, context_type, extracted_at)
);

-- Deal decision log — tracks agent recommendations vs AE actions
CREATE TABLE IF NOT EXISTS gtm.memory_deal_decisions (
    decision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opp_id              VARCHAR,
    ae_id               VARCHAR,
    session_thread_id   VARCHAR,
    recommendation      TEXT,
    ae_action           VARCHAR,        -- 'accepted' | 'modified' | 'rejected'
    ae_feedback         TEXT,
    outcome             VARCHAR,        -- Populated later: 'deal_won' | 'deal_lost' | 'stalled'
    decided_at          TIMESTAMP DEFAULT NOW()
);

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  AUDIT TABLE                                                            ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS gtm.audit_agent_access (
    trace_id        VARCHAR,
    ae_id           VARCHAR,
    opp_id          VARCHAR,
    tool_called     VARCHAR,
    data_accessed   VARCHAR[],
    accessed_at     TIMESTAMP DEFAULT NOW()
);

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  INDEXES                                                                ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

CREATE INDEX IF NOT EXISTS idx_contacts_account ON gtm.contacts (account_id);
CREATE INDEX IF NOT EXISTS idx_opps_account ON gtm.opportunities (account_id);
CREATE INDEX IF NOT EXISTS idx_outreach_opp ON gtm.outreach_log (opp_id);
CREATE INDEX IF NOT EXISTS idx_mem_account_ctx ON gtm.memory_account_context (account_id, extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_mem_ae ON gtm.memory_ae_profiles (ae_id);
CREATE INDEX IF NOT EXISTS idx_mem_decisions ON gtm.memory_deal_decisions (opp_id, decided_at DESC);
