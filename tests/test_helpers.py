"""
Common test helpers for Orchestrator and other Agent tests.
"""
import pytest

def make_state(items=None):
    """Helper to create a test state dict."""
    if items is None:
        items = {}
    return {
        "last_heartbeat": None,
        "items": items,
    }

def make_item(title="Test", stage="INTAKE", priority="Medium", review_status="PENDING", confidence=None):
    """Helper to create a test item dict."""
    return {
        "title": title,
        "priority": priority,
        "stage": stage,
        "created_at": "2026-05-14T00:00:00Z",
        "updated_at": "2026-05-14T00:00:00Z",
        "assigned_agent": None,
        "confidence_score": confidence,
        "blocked_reason": None,
        "review_status": review_status,
        "history": [{"stage": "INTAKE", "at": "2026-05-14T00:00:00Z"}],
    }

def make_items(items_dict):
    """Helper to create a state dict with items."""
    return {"last_heartbeat": None, "items": items_dict}
