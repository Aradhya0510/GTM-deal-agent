"""
02 · Vector Search — Create endpoint and delta-sync indexes.

Run as a Databricks notebook or Python script with workspace auth.
Requires:
  - Permission to create Vector Search endpoints
  - Delta tables in gtm.enablement.* already populated (see 04_seed_demo_data.py)
  - databricks-gte-large-en embedding endpoint available
"""

from databricks.vector_search.client import VectorSearchClient

VS_ENDPOINT = "gtm_vs_endpoint"
EMBEDDING_MODEL = "databricks-gte-large-en"

vsc = VectorSearchClient()

# ---------------------------------------------------------------------------
# 1. Create the Vector Search endpoint (if it doesn't exist)
# ---------------------------------------------------------------------------
try:
    vsc.get_endpoint(VS_ENDPOINT)
    print(f"Endpoint '{VS_ENDPOINT}' already exists.")
except Exception:
    vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")
    print(f"Created endpoint '{VS_ENDPOINT}'. Waiting for it to become ready...")

# ---------------------------------------------------------------------------
# 2. Index: Gong call transcripts — account context retrieval
# ---------------------------------------------------------------------------
vsc.create_delta_sync_index(
    endpoint_name=VS_ENDPOINT,
    index_name="gtm.vectors.call_transcripts",
    source_table_name="gtm.enablement.call_transcripts",
    pipeline_type="TRIGGERED",
    primary_key="transcript_id",
    embedding_source_column="transcript_text",
    embedding_model_endpoint_name=EMBEDDING_MODEL,
    columns_to_sync=[
        "account_id", "opp_id", "call_date", "participants", "summary", "sentiment"
    ],
)
print("Created index: gtm.vectors.call_transcripts")

# ---------------------------------------------------------------------------
# 3. Index: Sales battlecards + competitive intelligence
# ---------------------------------------------------------------------------
vsc.create_delta_sync_index(
    endpoint_name=VS_ENDPOINT,
    index_name="gtm.vectors.battlecards",
    source_table_name="gtm.enablement.battlecards",
    pipeline_type="TRIGGERED",
    primary_key="card_id",
    embedding_source_column="content",
    embedding_model_endpoint_name=EMBEDDING_MODEL,
    columns_to_sync=[
        "competitor", "use_case", "win_themes", "objection_handlers", "last_updated"
    ],
)
print("Created index: gtm.vectors.battlecards")

# ---------------------------------------------------------------------------
# 4. Index: Won/lost deal stories for personalization context
# ---------------------------------------------------------------------------
vsc.create_delta_sync_index(
    endpoint_name=VS_ENDPOINT,
    index_name="gtm.vectors.deal_stories",
    source_table_name="gtm.enablement.deal_stories",
    pipeline_type="TRIGGERED",
    primary_key="story_id",
    embedding_source_column="narrative",
    embedding_model_endpoint_name=EMBEDDING_MODEL,
    columns_to_sync=[
        "industry", "deal_size", "use_case", "outcome", "key_moments", "competitor"
    ],
)
print("Created index: gtm.vectors.deal_stories")

print("\nAll Vector Search indexes created. Run index sync after seeding data.")
