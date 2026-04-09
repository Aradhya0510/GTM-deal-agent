"""Tests for agent configuration loading."""

from pathlib import Path

from servicenow_gtm_agent.config import AgentConfig, load_config


def test_default_config():
    config = AgentConfig()
    assert config.model.research_model == "databricks-claude-3-5-sonnet"
    assert config.model.memory_extraction_model == "databricks-claude-3-5-haiku"
    assert config.data.catalog == "gtm"
    assert config.lakebase.instance_name == "gtm-memory"
    assert config.mlflow.autolog is True
    assert config.serving.endpoint_name == "gtm-deal-intelligence"


def test_load_config_from_yaml():
    config = load_config(Path(__file__).parent.parent / "configs" / "default.yaml")
    assert config.data.call_transcripts_index == "gtm.vectors.call_transcripts"
    assert config.data.battlecards_index == "gtm.vectors.battlecards"
    assert config.data.deal_stories_index == "gtm.vectors.deal_stories"
    assert config.lakebase.memory_schema == "gtm.memory"


def test_config_override():
    config = AgentConfig(
        model={"research_model": "custom-model"},
        data={"catalog": "custom_catalog"},
    )
    assert config.model.research_model == "custom-model"
    assert config.data.catalog == "custom_catalog"
    # Defaults preserved for fields not overridden
    assert config.model.scoring_model == "databricks-claude-3-5-sonnet"
