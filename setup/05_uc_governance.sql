-- ============================================================================
-- 05 · Unity Catalog Governance — Row-level security + column masking
-- ============================================================================
-- Run in a Databricks SQL notebook. Requires: UC admin or MANAGE privilege.
-- ============================================================================

USE CATALOG gtm;

-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  ROW-LEVEL SECURITY — Territory-based access                            ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- AEs only see opportunities in their territory (or leadership sees all)
CREATE OR REPLACE FUNCTION gtm.security.territory_filter(territory STRING)
RETURN
    EXISTS (
        SELECT 1 FROM gtm.crm.accounts a
        WHERE a.territory = territory_filter.territory
          AND a.ae_owner = current_user()
    )
    OR is_account_group_member('sales-leadership')
    OR is_account_group_member('revenue-operations');

ALTER TABLE gtm.crm.opportunities SET ROW FILTER gtm.security.territory_filter ON (territory);

-- Memory: AE profiles — strictly personal (only the AE and leadership)
CREATE OR REPLACE FUNCTION gtm.security.ae_profile_filter(ae_id STRING)
RETURN
    ae_id = current_user()
    OR is_account_group_member('sales-leadership');

ALTER TABLE gtm.crm.contacts SET ROW FILTER gtm.security.ae_profile_filter ON (ae_id)
-- Note: Apply to memory tables when using Lakebase-backed UC tables

-- Memory: Account context — shared within account team
CREATE OR REPLACE FUNCTION gtm.security.account_context_filter(ae_id STRING)
RETURN
    EXISTS (
        SELECT 1 FROM gtm.crm.accounts a
        WHERE a.ae_owner = current_user()
    )
    OR is_account_group_member('sales-leadership')
    OR is_account_group_member('revenue-operations');

-- Memory: Deal decisions — visible to AE + leadership + RevOps
CREATE OR REPLACE FUNCTION gtm.security.decision_filter(ae_id STRING)
RETURN
    ae_id = current_user()
    OR is_account_group_member('sales-leadership')
    OR is_account_group_member('revenue-operations');


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  COLUMN MASKING — PII protection                                        ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- Mask personal email for non-managers
CREATE OR REPLACE FUNCTION gtm.security.mask_personal_email(personal_email STRING)
RETURN
    CASE
        WHEN is_account_group_member('sales-leadership') THEN personal_email
        ELSE CONCAT(LEFT(personal_email, 2), '***@***.***')
    END;

ALTER TABLE gtm.crm.contacts
    ALTER COLUMN personal_email SET MASK gtm.security.mask_personal_email;

-- Mask phone for non-account-owners
CREATE OR REPLACE FUNCTION gtm.security.mask_phone(phone STRING)
RETURN
    CASE
        WHEN is_account_group_member('sales-leadership') THEN phone
        ELSE CONCAT('***-***-', RIGHT(phone, 4))
    END;

ALTER TABLE gtm.crm.contacts
    ALTER COLUMN phone SET MASK gtm.security.mask_phone;
