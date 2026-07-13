"""P3.6 regression tests: pipeline-state items must always carry an ISO-8601
``created_at`` (and ``updated_at``); the historical literal ``"now"`` must
self-heal on load and never leak to API/UI consumers.

Covers:
  * ``sanitize_state`` / ``normalize_created_at`` repair a ``"now"`` value.
  * A real ISO timestamp is left untouched (idempotent).
  * The live ``KanbanStateManager`` and legacy ``StateManager`` ``load_state``
    both repair a state file containing ``created_at: "now"``.
  * ``create_item`` on both managers emits a real ISO ``created_at``.
  * The committed ``automation-ideas/pipeline-state.json`` has no ``"now"``
    left in it (backfill guard).
"""
import json
import os
from datetime import datetime

import pytest

from api.managers._timestamps import (
    _is_iso,
    normalize_created_at,
    sanitize_state,
)
from api.managers.kanban_state_manager import KanbanStateManager
from api.state_manager import StateManager


def test_is_iso_recognizes_our_formats():
    assert _is_iso("2026-07-13T19:40:12.464956Z") is True
    assert _is_iso("2026-07-13T19:40:12Z") is True
    assert _is_iso("2026-07-13T19:40:12.464956") is True


def test_is_iso_rejects_bad_values():
    assert _is_iso("now") is False
    assert _is_iso("") is False
    assert _is_iso(None) is False
    assert _is_iso(123) is False
    assert _is_iso("2026/07/13 19:40") is False


def test_normalize_repairs_now_literal():
    item = {"name": "test", "created_at": "now"}
    out = normalize_created_at(item)
    assert _is_iso(out["created_at"]) is True
    assert _is_iso(out["updated_at"]) is True


def test_normalize_repairs_missing_created_at():
    item = {"name": "test"}  # no created_at at all
    out = normalize_created_at(item)
    assert _is_iso(out["created_at"]) is True
    assert _is_iso(out["updated_at"]) is True


def test_normalize_is_idempotent_on_real_iso():
    real = {"name": "test", "created_at": "2026-07-13T19:40:12.464956Z",
            "updated_at": "2026-07-13T19:40:12.465000Z"}
    out = normalize_created_at(dict(real))
    assert out["created_at"] == real["created_at"]
    assert out["updated_at"] == real["updated_at"]


def test_sanitize_state_repairs_all_items():
    state = {"last_heartbeat": None, "items": {
        "ID-001": {"name": "test", "created_at": "now"},
        "ID-002": {"title": "real", "created_at": "2026-07-13T19:40:12.464956Z",
                   "updated_at": "2026-07-13T19:40:12.464956Z"},
    }}
    sanitize_state(state)
    assert _is_iso(state["items"]["ID-001"]["created_at"]) is True
    # The already-good item is untouched.
    assert state["items"]["ID-002"]["created_at"] == "2026-07-13T19:40:12.464956Z"


def test_sanitize_state_tolerates_missing_items():
    assert sanitize_state({}) == {}
    assert sanitize_state({"items": {}}) == {"items": {}}
    assert sanitize_state(None) is None


def _write_state(base_dir, state):
    os.makedirs(base_dir, exist_ok=True)
    with open(os.path.join(base_dir, "pipeline-state.json"), "w") as f:
        json.dump(state, f)


def test_kanban_manager_load_repairs_now(tmp_path):
    _write_state(str(tmp_path), {"items": {
        "ID-X": {"name": "stale", "created_at": "now"},
    }})
    mgr = KanbanStateManager(str(tmp_path))
    state = mgr.load_state()
    assert _is_iso(state["items"]["ID-X"]["created_at"]) is True


def test_legacy_state_manager_load_repairs_now(tmp_path):
    _write_state(str(tmp_path), {"items": {
        "ID-Y": {"name": "stale", "created_at": "now"},
    }})
    mgr = StateManager(str(tmp_path))
    state = mgr.load_state()
    assert _is_iso(state["items"]["ID-Y"]["created_at"]) is True


def test_kanban_manager_create_item_emits_iso(tmp_path):
    mgr = KanbanStateManager(str(tmp_path))
    assert mgr.create_item("ID-NEW", title="t") is True
    state = mgr.load_state()
    assert _is_iso(state["items"]["ID-NEW"]["created_at"]) is True
    assert _is_iso(state["items"]["ID-NEW"]["updated_at"]) is True


def test_legacy_state_manager_create_item_emits_iso(tmp_path):
    mgr = StateManager(str(tmp_path))
    assert mgr.create_item("ID-NEW2", title="t") is True
    state = mgr.load_state()
    assert _is_iso(state["items"]["ID-NEW2"]["created_at"]) is True


def test_committed_state_file_has_no_now_literal():
    """Backfill guard: the live pipeline-state.json must not contain 'now'."""
    here = os.path.dirname(os.path.dirname(__file__))
    state_path = os.path.join(here, "automation-ideas", "pipeline-state.json")
    if not os.path.exists(state_path):
        pytest.skip("pipeline-state.json absent in this checkout")
    with open(state_path) as f:
        raw = f.read()
    assert '"now"' not in raw, (
        "pipeline-state.json still has a bare \"now\" literal — backfill missing"
    )
    state = json.loads(raw)
    for item_id, item in state.get("items", {}).items():
        if isinstance(item, dict):
            assert _is_iso(item.get("created_at")), (
                f"{item_id} has non-ISO created_at={item.get('created_at')!r}"
            )
