-- ============================================================================
-- 00 · Unity Catalog — Create catalog, schemas, and Vector Search endpoint
-- ============================================================================
-- Run this in a Databricks SQL notebook or via dbsql CLI.
-- Requires: CREATE CATALOG / CREATE SCHEMA privileges.
-- ============================================================================

-- Top-level catalog for the GTM demo
CREATE CATALOG IF NOT EXISTS gtm;
USE CATALOG gtm;

-- Schema for CRM operational data (Lakebase-backed)
CREATE SCHEMA IF NOT EXISTS gtm.crm;

-- Schema for agent tools (UC Functions)
CREATE SCHEMA IF NOT EXISTS gtm.tools;

-- Schema for long-term memory tables (Lakebase-backed)
CREATE SCHEMA IF NOT EXISTS gtm.memory;

-- Schema for Vector Search source tables (Delta)
CREATE SCHEMA IF NOT EXISTS gtm.vectors;

-- Schema for sales enablement content (Delta)
CREATE SCHEMA IF NOT EXISTS gtm.enablement;

-- Schema for evaluation datasets
CREATE SCHEMA IF NOT EXISTS gtm.eval;

-- Schema for governance objects (row filters, column masks)
CREATE SCHEMA IF NOT EXISTS gtm.security;

-- Schema for audit logging
CREATE SCHEMA IF NOT EXISTS gtm.audit;
