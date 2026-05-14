"""
Tests for the pipeline state management module (agents/state.py).
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, mock_open

from agents import state


def test_load_state_returns_dict():
    """load_state should return a dict with items key."""
    state_data = {"last_heartbeat": None, "items": {}}
    with patch("agents.state.STATE_FILE", new_callable=lambda: "/fake/path.json"):
        with patch("builtins.open", mock_open(read_data=json.dumps(state_data))):
            with patch("os.path.exists", return_value=True):
                result = state.load_state()
                assert isinstance(result, dict)
                assert "items" in result


def test_load_state_file_not_found():
    """load_state should return default state when file doesn't exist."""
    with patch("os.path.exists", return_value=False):
        result = state.load_state()
        assert isinstance(result, dict)
        assert result["items"] == {}


def test_save_state_writes_json():
    """save_state should write valid JSON to the state file."""
    state_data = {"last_heartbeat": None, "items": {}}
    with patch("agents.state.STATE_FILE", new_callable=lambda: "/fake/path.json"):
        with patch("builtins.open", mock_open()) as mock_file:
            with patch("os.makedirs"):
                state.save_state(state_data)
                handle = mock_file()
                written_content = "".join(call[0][0] for call in handle.write.call_args_list)
                parsed = json.loads(written_content)
                assert parsed == state_data


def test_get_item_returns_correct_item():
    """get_item should return the correct item dict."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "stage": "INTAKE"},
            "ID-002": {"title": "Test 2", "stage": "REFINEMENT"},
        }
    }
    result = state.get_item(state_data, "ID-001")
    assert result["title"] == "Test"
    assert result["stage"] == "INTAKE"


def test_get_item_raises_key_error():
    """get_item should raise KeyError for missing item."""
    state_data = {"items": {"ID-001": {"title": "Test"}}}
    with pytest.raises(KeyError):
        state.get_item(state_data, "ID-999")


def test_update_item_updates_fields():
    """update_item should update specified fields."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "stage": "INTAKE", "updated_at": "old"},
        }
    }
    state.update_item(state_data, "ID-001", {"stage": "REFINEMENT", "confidence_score": 85})
    assert state_data["items"]["ID-001"]["stage"] == "REFINEMENT"
    assert state_data["items"]["ID-001"]["confidence_score"] == 85


def test_update_item_sets_updated_at():
    """update_item should set updated_at to current timestamp."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "stage": "INTAKE"},
        }
    }
    state.update_item(state_data, "ID-001", {"stage": "REFINEMENT"})
    updated_at = state_data["items"]["ID-001"]["updated_at"]
    assert updated_at.endswith("Z")
    assert "T" in updated_at


def test_update_item_raises_key_error():
    """update_item should raise KeyError for missing item."""
    state_data = {"items": {}}
    with pytest.raises(KeyError):
        state.update_item(state_data, "ID-999", {"stage": "DONE"})


def test_add_history_entry_appends():
    """add_history_entry should append a history entry."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "history": []},
        }
    }
    state.add_history_entry(state_data, "ID-001", "REFINEMENT", agent="refiner")
    assert len(state_data["items"]["ID-001"]["history"]) == 1
    entry = state_data["items"]["ID-001"]["history"][0]
    assert entry["stage"] == "REFINEMENT"
    assert entry["agent"] == "refiner"
    assert "at" in entry


def test_add_history_entry_without_agent():
    """add_history_entry should work without an agent."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "history": []},
        }
    }
    state.add_history_entry(state_data, "ID-001", "REVIEW_SPEC")
    entry = state_data["items"]["ID-001"]["history"][0]
    assert entry["stage"] == "REVIEW_SPEC"
    assert "agent" not in entry


def test_get_next_id_increments():
    """get_next_id should return the next available ID."""
    state_data = {
        "items": {
            "ID-001": {},
            "ID-002": {},
            "ID-003": {},
        }
    }
    assert state.get_next_id(state_data) == "ID-004"


def test_get_next_id_empty():
    """get_next_id should return ID-001 for empty state."""
    state_data = {"items": {}}
    assert state.get_next_id(state_data) == "ID-001"


def test_get_next_id_skips_gaps():
    """get_next_id should find the max and increment."""
    state_data = {
        "items": {
            "ID-001": {},
            "ID-005": {},
        }
    }
    assert state.get_next_id(state_data) == "ID-006"


def test_create_item_directory_creates_dir():
    """create_item_directory should create the requirements directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("agents.state.REQUIREMENTS_DIR", tmpdir):
            result = state.create_item_directory("ID-999")
            expected = os.path.join(tmpdir, "ID-999")
            assert os.path.isdir(expected)
            assert result == expected