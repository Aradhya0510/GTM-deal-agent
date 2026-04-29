# Databricks notebook source
# MAGIC %md
# MAGIC # AI Gateway Configuration (optional)
# MAGIC
# MAGIC Enables AI Gateway features on the LLM endpoint:
# MAGIC - **Usage tracking** → `system.serving.endpoint_usage` + `system.serving.served_entities`
# MAGIC - **Inference tables** (payload logging) → Delta table in `{UC_CATALOG}.{UC_SCHEMA}`
# MAGIC - **Rate limits** → per-user QPM (default 60, demo-safe; tune for your workload)
# MAGIC - **AI Guardrails** → Safety filter + PII detection (BLOCK mode) on input and output
# MAGIC
# MAGIC Optional, post-bootstrap step. Requires `CAN_MANAGE` on the endpoint.
# MAGIC
# MAGIC Run interactively by setting the widget values in the notebook UI, or
# MAGIC submit as a serverless job with `notebook_task.base_parameters`
# MAGIC populated from `.env` (same pattern as the other setup notebooks).

# COMMAND ----------

# ── Configuration via notebook widgets ──
dbutils.widgets.text("LLM_ENDPOINT", "databricks-claude-sonnet-4-6")
dbutils.widgets.text("UC_CATALOG", "")
dbutils.widgets.text("UC_SCHEMA", "")
dbutils.widgets.text("RATE_LIMIT_QPM", "60", "Per-user rate limit (queries per minute)")

LLM_ENDPOINT = dbutils.widgets.get("LLM_ENDPOINT")
UC_CATALOG = dbutils.widgets.get("UC_CATALOG")
UC_SCHEMA = dbutils.widgets.get("UC_SCHEMA")
RATE_LIMIT_QPM = int(dbutils.widgets.get("RATE_LIMIT_QPM"))

assert LLM_ENDPOINT, "LLM_ENDPOINT widget must be set"
assert UC_CATALOG and UC_SCHEMA, (
    "UC_CATALOG and UC_SCHEMA widgets must be set (used for the inference "
    "table location)"
)

print(f"Configuring AI Gateway on endpoint: {LLM_ENDPOINT}")
print(f"Inference table location:           {UC_CATALOG}.{UC_SCHEMA}")
print(f"Rate limit:                         {RATE_LIMIT_QPM} QPM per user")

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

config = {
    "usage_tracking_config": {"enabled": True},
    "inference_table_config": {
        "enabled": True,
        "catalog_name": UC_CATALOG,
        "schema_name": UC_SCHEMA,
    },
    "rate_limits": [
        {"key": "user", "renewal_period": "minute", "calls": RATE_LIMIT_QPM}
    ],
    "guardrails": {
        "input": {
            "safety": True,
            "pii": {"behavior": "BLOCK"},
        },
        "output": {
            "safety": True,
            "pii": {"behavior": "BLOCK"},
        },
    },
}

print(f"Config: {config}")

resp = w.api_client.do(
    "PUT",
    f"/api/2.0/serving-endpoints/{LLM_ENDPOINT}/ai-gateway",
    body=config,
)

print(f"\nResponse: {resp}")
print("\nAI Gateway configured successfully.")
print(
    f"Features enabled: usage tracking, inference tables, "
    f"rate limits ({RATE_LIMIT_QPM} QPM), guardrails (safety + PII block)"
)
print("Usage data will appear in system.serving.endpoint_usage within ~1 hour of first query.")

# COMMAND ----------

# Verify the configuration
import json

gw = w.api_client.do("GET", f"/api/2.0/serving-endpoints/{LLM_ENDPOINT}/ai-gateway")
print("Current AI Gateway config:")
print(json.dumps(gw, indent=2))
