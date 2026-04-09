"""GTM Deal Intelligence Agent — MLflow model wrapper for Databricks Model Serving.

This is the main entrypoint that Databricks Model Serving loads. It wraps
the LangGraph pipeline as a LangGraphResponsesAgent with:
  - Short-term memory via Lakebase CheckpointSaver
  - Long-term memory loaded at session start
  - Time travel support via checkpoint_id in custom_inputs
  - Streaming support for real-time token delivery

Databricks tech: Model Serving + Lakebase + LangGraph + MLflow 3.x
"""

import uuid
from typing import Generator

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)
from databricks.agents.lakebase import CheckpointSaver

from servicenow_gtm_agent.config import AgentConfig, load_config
from servicenow_gtm_agent.graph import build_graph
from servicenow_gtm_agent.state import DealState

# Load config at module level (set by environment or default)
CONFIG = load_config("configs/default.yaml")


class GTMDealAgent(ResponsesAgent):
    """Stateful GTM Deal Intelligence Agent.

    Short-term: LangGraph checkpoints persisted to Lakebase per thread_id.
    Long-term: AE preferences + account context injected at session start.
    Time travel: pass checkpoint_id in custom_inputs to branch from a prior state.
    """

    def _build(self, checkpointer=None, memory_prefix=""):
        """Build the LangGraph pipeline, optionally with checkpointer and memory."""
        graph, tools = build_graph(
            checkpointer=checkpointer, memory_prefix=memory_prefix
        )
        return graph

    # ── Non-streaming prediction ─────────────────────────────────────────

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(output=outputs)

    # ── Streaming prediction ─────────────────────────────────────────────

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        custom_inputs = getattr(request, "custom_inputs", None) or {}
        thread_id = custom_inputs.get("thread_id", str(uuid.uuid4()))
        checkpoint_id = custom_inputs.get("checkpoint_id")  # For time-travel branching

        checkpoint_config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            checkpoint_config["configurable"]["checkpoint_id"] = checkpoint_id

        messages = to_chat_completions_input([m.model_dump() for m in request.input])

        with CheckpointSaver(
            instance_name=CONFIG.lakebase.instance_name,
            schema_name=CONFIG.lakebase.memory_schema,
        ) as checkpointer:
            graph = self._build(checkpointer=checkpointer)

            for event in graph.stream(
                {"messages": messages},
                config=checkpoint_config,
                stream_mode=["updates"],
            ):
                if event[0] == "updates":
                    for node_data in event[1].values():
                        if node_data.get("messages"):
                            yield from output_to_responses_items_stream(
                                node_data["messages"]
                            )

    # ── Checkpoint history (for time travel UI) ──────────────────────────

    def get_checkpoint_history(self, thread_id: str, limit: int = 10) -> list[dict]:
        """Retrieve checkpoint history for a thread — powers the time travel UI."""
        config = {"configurable": {"thread_id": thread_id}}
        with CheckpointSaver(
            instance_name=CONFIG.lakebase.instance_name,
            schema_name=CONFIG.lakebase.memory_schema,
        ) as cp:
            graph = self._build(checkpointer=cp)
            history = []
            for state in graph.get_state_history(config):
                if len(history) >= limit:
                    break
                history.append(
                    {
                        "checkpoint_id": state.config["configurable"]["checkpoint_id"],
                        "thread_id": thread_id,
                        "timestamp": state.created_at,
                        "next_nodes": state.next,
                        "message_count": len(state.values.get("messages", [])),
                        "last_message": (state.values.get("messages") or [""])[-1],
                    }
                )
        return history


# ── Register with MLflow ─────────────────────────────────────────────────

AGENT = GTMDealAgent()
mlflow.models.set_model(AGENT)
