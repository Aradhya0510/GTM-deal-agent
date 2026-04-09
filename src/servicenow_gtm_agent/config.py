"""Agent configuration — Pydantic models loaded from YAML."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """LLM endpoints for each sub-agent."""

    research_model: str = "databricks-claude-3-5-sonnet"
    scoring_model: str = "databricks-claude-3-5-sonnet"
    outreach_model: str = "databricks-claude-3-5-sonnet"
    memory_extraction_model: str = "databricks-claude-3-5-haiku"


class DataConfig(BaseModel):
    """Databricks data layer configuration."""

    catalog: str = "gtm"
    crm_schema: str = "crm"
    vector_search_endpoint: str = "gtm_vs_endpoint"
    call_transcripts_index: str = "gtm.vectors.call_transcripts"
    battlecards_index: str = "gtm.vectors.battlecards"
    deal_stories_index: str = "gtm.vectors.deal_stories"


class LakebaseConfig(BaseModel):
    """Lakebase instance for checkpointing and long-term memory."""

    instance_name: str = "gtm-memory"
    memory_schema: str = "gtm.memory"


class MLflowConfig(BaseModel):
    """MLflow tracing and experiment tracking."""

    experiment_name: str = "/gtm/deal-intelligence-agent"
    autolog: bool = True


class ServingConfig(BaseModel):
    """Model Serving deployment settings."""

    endpoint_name: str = "gtm-deal-intelligence"
    scale_to_zero: bool = True


class AgentConfig(BaseModel):
    """Top-level agent configuration."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    lakebase: LakebaseConfig = Field(default_factory=LakebaseConfig)
    mlflow: MLflowConfig = Field(default_factory=MLflowConfig)
    serving: ServingConfig = Field(default_factory=ServingConfig)


def load_config(path: str | Path) -> AgentConfig:
    """Load agent config from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AgentConfig.model_validate(raw or {})
