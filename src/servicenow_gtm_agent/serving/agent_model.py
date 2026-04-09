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
from databricks.agents import LangGraphResponsesAgent, ResponsesAgentRequest, ResponsesAgentResponse
from databricks.agents import ResponsesAgentStreamEvent
from databricks.agents.lakebase import CheckpointSaver

from servicenow_gtm_agent.config import AgentConfig, load_config
from servicenow_gtm_agent.graph import build_graph
from servicenow_gtm_agent.state import DealState

# Load config at module level (set by environment or default)
CONFIG = load_config("configs/default.yaml")


class GTMDealAgent(LangGraphResponsesAgent):
    """Stateful GTM Deal Intelligence Agent.

    Short-term: LangGraph checkpoints persisted to Lakebase per thread_id.
    Long-term: AE preferences + account context injected at session start.
    Time travel: pass checkpoint_id in custom_inputs to branch from a prior state.
    """

    def _create_graph(self, checkpointer):
        """Build the LangGraph pipeline wired to the Lakebase checkpointer."""
        return build_graph(CONFIG, checkpointer=checkpointer)

    # ── Non-streaming prediction ─────────────────────────────────────────

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        custom_inputs = dict(request.custom_inputs or {})

        if "thread_id" not in custom_inputs:
            custom_inputs["thread_id"] = str(uuid.uuid4())
        request.custom_inputs = custom_inputs

        # Collect stream events into a response
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]

        # Surface thread_id and checkpoint_id for the App to persist
        custom_outputs = {"thread_id": custom_inputs["thread_id"]}
        try:
            history = self.get_checkpoint_history(custom_inputs["thread_id"], limit=1)
            if history:
                custom_outputs["checkpoint_id"] = history[0]["checkpoint_id"]
        except Exception:
            pass

        return ResponsesAgentResponse(output=outputs, custom_outputs=custom_outputs)

    # ── Streaming prediction ─────────────────────────────────────────────

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        custom_inputs = request.custom_inputs or {}
        thread_id = custom_inputs.get("thread_id", str(uuid.uuid4()))
        checkpoint_id = custom_inputs.get("checkpoint_id")  # For time-travel branching

        checkpoint_config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            checkpoint_config["configurable"]["checkpoint_id"] = checkpoint_id

        with CheckpointSaver(
            instance_name=CONFIG.lakebase.instance_name,
            schema_name=CONFIG.lakebase.memory_schema,
        ) as checkpointer:
            graph = self._create_graph(checkpointer)
            inputs = self.prep_msgs_for_cc_llm([i.model_dump() for i in request.input])

            for event in graph.stream(
                {
                    "messages": inputs,
                    "thread_id": thread_id,
                    "ae_id": custom_inputs.get("ae_id", ""),
                    "account_id": custom_inputs.get("account_id", ""),
                    "opp_id": custom_inputs.get("opp_id", ""),
                },
                config=checkpoint_config,
                stream_mode="values",
            ):
                yield from self._convert_to_stream_events(event)

    # ── Checkpoint history (for time travel UI) ──────────────────────────

    def get_checkpoint_history(self, thread_id: str, limit: int = 10) -> list[dict]:
        """Retrieve checkpoint history for a thread — powers the time travel UI."""
        config = {"configurable": {"thread_id": thread_id}}
        with CheckpointSaver(
            instance_name=CONFIG.lakebase.instance_name,
            schema_name=CONFIG.lakebase.memory_schema,
        ) as cp:
            graph = self._create_graph(cp)
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
