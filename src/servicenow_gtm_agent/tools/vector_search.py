"""Vector Search retriever tools for semantic search over GTM content.

Each retriever wraps a Databricks Vector Search delta-sync index via
databricks_langchain.VectorSearchRetrieverTool.

IMPORTANT:
- Delta-sync indexes on NEWLY CREATED endpoints can take 20+ minutes.
  Use an existing warmed endpoint (e.g., dbdemos_vs_endpoint) for faster setup.
- Source tables MUST have delta.enableChangeDataFeed = true for delta-sync.
- VectorSearchRetrieverTool auto-provides .resources for mlflow log_model().

Databricks tech: Vector Search + databricks-gte-large-en embeddings
"""

from databricks_langchain import VectorSearchRetrieverTool


def get_vs_tools(catalog: str = "users", schema: str = "aradhya_chouhan") -> list:
    """Create Vector Search retriever tools.

    Returns a list of VectorSearchRetrieverTool instances.
    Each provides .resources for MLflow auth passthrough when logging.
    """
    transcript_retriever = VectorSearchRetrieverTool(
        index_name=f"{catalog}.{schema}.gtm_transcripts_idx",
        num_results=4,
        columns=["transcript_id", "transcript_text", "call_date", "participants", "summary", "sentiment", "account_id"],
    )

    battlecard_retriever = VectorSearchRetrieverTool(
        index_name=f"{catalog}.{schema}.gtm_battlecards_idx",
        num_results=2,
        columns=["card_id", "content", "competitor", "use_case", "win_themes", "objection_handlers"],
    )

    deal_stories_retriever = VectorSearchRetrieverTool(
        index_name=f"{catalog}.{schema}.gtm_stories_idx",
        num_results=2,
        columns=["story_id", "narrative", "industry", "outcome", "key_moments", "competitor"],
    )

    return [transcript_retriever, battlecard_retriever, deal_stories_retriever]
