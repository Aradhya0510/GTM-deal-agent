"""Short-term memory — LangGraph checkpointing to Lakebase.

Every node execution in the LangGraph graph writes a durable checkpoint
to Lakebase Postgres. This gives us:
  - Multi-turn conversation within a session ("make it shorter")
  - Survival across agent restarts (state is in Postgres, not in-process)
  - Time travel: branch from any prior checkpoint to try a different angle
  - Full audit trail of every intermediate state

Databricks tech: Lakebase (managed Postgres) + LangGraph CheckpointSaver
"""

from databricks.agents.lakebase import CheckpointSaver

from servicenow_gtm_agent.config import LakebaseConfig


def get_checkpoint_saver(config: LakebaseConfig) -> CheckpointSaver:
    """Create a Lakebase-backed CheckpointSaver for LangGraph.

    The CheckpointSaver is a context manager — use it with `with`:

        with get_checkpoint_saver(config) as checkpointer:
            graph = workflow.compile(checkpointer=checkpointer)
            graph.invoke(state, config={"configurable": {"thread_id": "..."}})
    """
    return CheckpointSaver(
        instance_name=config.instance_name,
        schema_name=config.memory_schema,
    )
