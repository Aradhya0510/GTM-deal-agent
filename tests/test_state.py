"""Tests for DealState structure."""

from servicenow_gtm_agent.state import DealState


def test_deal_state_annotations():
    """Verify DealState has the expected fields."""
    annotations = DealState.__annotations__
    assert "messages" in annotations
    assert "thread_id" in annotations
    assert "ae_id" in annotations
    assert "deal_health" in annotations
    assert "memory_prefix" in annotations
    assert "tech_stack_used" in annotations
    assert "outreach_draft" in annotations
