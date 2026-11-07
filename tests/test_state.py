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


def test_save_state_writes_json(tmp_path):
    """save_state should write valid JSON to the state file."""
    state_data = {"last_heartbeat": None, "items": {}}
    target = tmp_path / "pipeline-state.json"
    with patch("agents.state.STATE_FILE", str(target)):
        state.save_state(state_data)
    assert json.loads(target.read_text()) == state_data


def _dir_listing(path):
    return sorted(p.name for p in path.iterdir() if not p.name.endswith(".lock"))


def _own_dir(tmp_path):
    """A fresh dir so the autouse data-dir fixture's files don't pollute listings."""
    d = tmp_path / "atomic-save"
    d.mkdir()
    return d


def test_save_state_failure_mid_dump_keeps_previous_file(tmp_path):
    """2.10 / T-atomic: a crash during json.dump must not corrupt the old file
    and must not leave a temp file behind."""
    tmp_path = _own_dir(tmp_path)
    target = tmp_path / "pipeline-state.json"
    old = {"last_heartbeat": "old", "items": {"ID-001": {"title": "keep me"}}}
    target.write_text(json.dumps(old))

    def boom(obj, fp, **kw):
        fp.write('{"partial": ')  # half-written payload
        raise RuntimeError("disk exploded")

    with patch("agents.state.STATE_FILE", str(target)), \
         patch("agents.state.json.dump", side_effect=boom):
        with pytest.raises(RuntimeError, match="disk exploded"):
            state.save_state({"items": {"ID-002": {}}})

    assert json.loads(target.read_text()) == old
    assert _dir_listing(tmp_path) == ["pipeline-state.json"]


def test_save_state_failure_when_no_previous_file_leaves_nothing(tmp_path):
    tmp_path = _own_dir(tmp_path)
    target = tmp_path / "pipeline-state.json"
    with patch("agents.state.STATE_FILE", str(target)), \
         patch("agents.state.json.dump", side_effect=RuntimeError("nope")):
        with pytest.raises(RuntimeError):
            state.save_state({"items": {}})
    assert _dir_listing(tmp_path) == []


def test_save_state_success_leaves_no_temp_file_and_replaces(tmp_path):
    tmp_path = _own_dir(tmp_path)
    target = tmp_path / "pipeline-state.json"
    target.write_text(json.dumps({"items": {"ID-001": {}}}))
    new = {"last_heartbeat": None, "items": {"ID-002": {"title": "new"}}}
    with patch("agents.state.STATE_FILE", str(target)):
        state.save_state(new)
    assert json.loads(target.read_text()) == new
    assert _dir_listing(tmp_path) == ["pipeline-state.json"]


def test_save_state_uses_replace_and_fsync(tmp_path):
    """The write goes to a temp file in the same dir, is fsynced, then os.replace'd."""
    target = tmp_path / "pipeline-state.json"
    calls = []
    real_replace, real_fsync = os.replace, os.fsync

    def spy_replace(src, dst):
        calls.append(("replace", os.path.dirname(src), dst))
        return real_replace(src, dst)

    def spy_fsync(fd):
        calls.append(("fsync",))
        return real_fsync(fd)

    with patch("agents.state.STATE_FILE", str(target)), \
         patch("agents.state.os.replace", side_effect=spy_replace), \
         patch("agents.state.os.fsync", side_effect=spy_fsync):
        state.save_state({"items": {}})

    kinds = [c[0] for c in calls]
    assert kinds == ["fsync", "replace"]
    assert calls[1][1] == str(tmp_path)      # temp file lives beside the target
    assert calls[1][2] == str(target)


def test_save_state_creates_missing_parent_dir(tmp_path):
    target = tmp_path / "nested" / "dir" / "pipeline-state.json"
    with patch("agents.state.STATE_FILE", str(target)):
        state.save_state({"items": {}})
    assert json.loads(target.read_text()) == {"items": {}}


def test_save_state_holds_the_state_lock(tmp_path):
    """The write happens while the shared lock is held."""
    target = tmp_path / "pipeline-state.json"
    held = []
    real_replace = os.replace

    def check(src, dst):
        held.append(state._lock.is_locked)
        return real_replace(src, dst)

    with patch("agents.state.STATE_FILE", str(target)), \
         patch("agents.state.os.replace", side_effect=check):
        state.save_state({"items": {}})
    assert held == [True]


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


# --- ID Case-Sensitivity Normalization Tests (R5.3) ---

def test_get_item_case_insensitive():
    """get_item should normalize lowercase item_id to uppercase."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "stage": "INTAKE"},
        }
    }
    result = state.get_item(state_data, "id-001")
    assert result["title"] == "Test"


def test_get_item_case_insensitive_mixed_case():
    """get_item should normalize mixed-case item_id to uppercase."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "stage": "INTAKE"},
        }
    }
    result = state.get_item(state_data, "Id-001")
    assert result["title"] == "Test"


def test_update_item_case_insensitive():
    """update_item should normalize lowercase item_id to uppercase."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "stage": "INTAKE", "updated_at": "old"},
        }
    }
    state.update_item(state_data, "id-001", {"stage": "REFINEMENT"})
    assert state_data["items"]["ID-001"]["stage"] == "REFINEMENT"


def test_add_history_entry_case_insensitive():
    """add_history_entry should normalize lowercase item_id to uppercase."""
    state_data = {
        "items": {
            "ID-001": {"title": "Test", "history": []},
        }
    }
    state.add_history_entry(state_data, "id-001", "REFINEMENT", agent="refiner")
    assert len(state_data["items"]["ID-001"]["history"]) == 1
    assert state_data["items"]["ID-001"]["history"][0]["stage"] == "REFINEMENT"


def test_create_item_directory_case_insensitive():
    """create_item_directory should normalize lowercase item_id to uppercase."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("agents.state.REQUIREMENTS_DIR", tmpdir):
            result = state.create_item_directory("id-999")
            expected = os.path.join(tmpdir, "ID-999")
            assert os.path.isdir(expected)
            assert result == expected


def test_get_next_id_case_insensitive_keys():
    """get_next_id should handle lowercase keys in state."""
    state_data = {
        "items": {
            "id-001": {},
            "id-002": {},
        }
    }
    assert state.get_next_id(state_data) == "ID-003"