"""D5: POST /api/item/{id}/review (owner review decision).

The board router is mounted on a throwaway app and pointed at a
WorkflowStateManager and a requirements directory in tmp_path, so no real
automation-ideas data is touched.
"""
import os
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import board_router
from api.workflow_state_manager import WorkflowStateManager

TS_LINE = re.compile(r"^- \[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\] (APPROVED|NEEDS_REVISION) at \w+: .+$")


@pytest.fixture
def req_dir(tmp_path, monkeypatch):
    d = tmp_path / "requirements"
    d.mkdir()
    monkeypatch.setattr(board_router, "REQUIREMENTS_DIR", str(d))
    return d


@pytest.fixture
def sm(tmp_path, monkeypatch):
    manager = WorkflowStateManager(str(tmp_path))
    monkeypatch.setattr(board_router, "get_state_manager", lambda: manager)
    manager.kanban.create_item("ID-001", "Test item", complexity="complex")
    manager.kanban.update_item("ID-001", {"stage": "REVIEW_SPEC"})
    return manager


@pytest.fixture
def client(sm, req_dir):
    app = FastAPI()
    app.include_router(board_router.router)
    return TestClient(app)


def _review_path(req_dir, item_id="ID-001"):
    return os.path.join(str(req_dir), item_id, "review.md")


class TestReviewDecision:
    def test_approve_sets_review_status_and_returns_fields(self, client, sm, req_dir):
        r = client.post("/api/item/ID-001/review", json={"status": "APPROVED"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "success"
        assert body["item_id"] == "ID-001"
        assert body["stage"] == "REVIEW_SPEC"
        assert body["review_status"] == "APPROVED"
        assert body["updated_at"]
        assert sm.kanban.get_item_details("ID-001")["review_status"] == "APPROVED"

    def test_needs_revision_sets_review_status(self, client, sm):
        r = client.post("/api/item/ID-001/review", json={"status": "NEEDS_REVISION"})
        assert r.status_code == 200, r.text
        assert r.json()["review_status"] == "NEEDS_REVISION"
        assert sm.kanban.get_item_details("ID-001")["review_status"] == "NEEDS_REVISION"

    def test_comment_is_appended_to_review_md_with_timestamp(self, client, req_dir):
        r = client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "Looks good"})
        assert r.status_code == 200, r.text
        with open(_review_path(req_dir), encoding="utf-8") as f:
            lines = f.read().splitlines()
        assert len(lines) == 1
        assert TS_LINE.match(lines[0]), lines[0]
        assert lines[0].endswith("APPROVED at REVIEW_SPEC: Looks good")

    def test_comment_is_optional_and_no_review_md_is_written(self, client, sm, req_dir):
        r = client.post("/api/item/ID-001/review", json={"status": "APPROVED"})
        assert r.status_code == 200, r.text
        assert not os.path.exists(_review_path(req_dir))
        assert sm.kanban.get_item_details("ID-001")["review_status"] == "APPROVED"

    def test_whitespace_only_comment_is_treated_as_absent(self, client, req_dir):
        r = client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "   "})
        assert r.status_code == 200, r.text
        assert not os.path.exists(_review_path(req_dir))

    def test_existing_review_md_is_appended_never_overwritten(self, client, req_dir):
        os.makedirs(req_dir / "ID-001")
        with open(_review_path(req_dir), "w", encoding="utf-8") as f:
            f.write("# Owner notes\nKeep this line.\n")
        r = client.post("/api/item/ID-001/review", json={"status": "NEEDS_REVISION", "comment": "Tighten AC"})
        assert r.status_code == 200, r.text
        with open(_review_path(req_dir), encoding="utf-8") as f:
            text = f.read()
        assert text.startswith("# Owner notes\nKeep this line.\n")
        assert text.count("Keep this line.") == 1
        assert "NEEDS_REVISION at REVIEW_SPEC: Tighten AC" in text

    def test_missing_trailing_newline_gets_separator(self, client, req_dir):
        os.makedirs(req_dir / "ID-001")
        with open(_review_path(req_dir), "w", encoding="utf-8") as f:
            f.write("previous line without newline")
        client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "second"})
        with open(_review_path(req_dir), encoding="utf-8") as f:
            lines = f.read().splitlines()
        assert lines[0] == "previous line without newline"
        assert TS_LINE.match(lines[1]), lines[1]

    def test_each_review_appends_a_new_line(self, client, req_dir):
        client.post("/api/item/ID-001/review", json={"status": "NEEDS_REVISION", "comment": "one"})
        client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "two"})
        with open(_review_path(req_dir), encoding="utf-8") as f:
            lines = f.read().splitlines()
        assert len(lines) == 2
        assert lines[0].endswith(": one")
        assert lines[1].endswith(": two")

    def test_multiline_comment_stays_inside_one_entry(self, client, req_dir):
        client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "a\nb"})
        with open(_review_path(req_dir), encoding="utf-8") as f:
            lines = f.read().splitlines()
        assert len(lines) == 2
        assert lines[1] == "  b"

    def test_comment_is_stripped(self, client, req_dir):
        client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "  padded  "})
        with open(_review_path(req_dir), encoding="utf-8") as f:
            assert f.read().rstrip().endswith("APPROVED at REVIEW_SPEC: padded")

    def test_history_entry_is_appended_per_review(self, client, sm):
        client.post("/api/item/ID-001/review", json={"status": "NEEDS_REVISION", "comment": "fix"})
        client.post("/api/item/ID-001/review", json={"status": "APPROVED"})
        history = sm.kanban.get_item_details("ID-001")["history"]
        assert len(history) == 2
        assert history[0]["review_status"] == "NEEDS_REVISION"
        assert history[0]["comment"] == "fix"
        assert history[0]["event"] == "review"
        assert history[0]["stage"] == "REVIEW_SPEC"
        assert history[1]["review_status"] == "APPROVED"
        assert "comment" not in history[1]

    def test_lowercase_item_id_is_normalized(self, client, sm):
        r = client.post("/api/item/id-001/review", json={"status": "APPROVED"})
        assert r.status_code == 200, r.text
        assert sm.kanban.get_item_details("ID-001")["review_status"] == "APPROVED"

    def test_lowercase_status_is_accepted_and_stored_uppercase(self, client, sm):
        r = client.post("/api/item/ID-001/review", json={"status": "approved"})
        assert r.status_code == 200, r.text
        assert r.json()["review_status"] == "APPROVED"


class TestReviewRejections:
    def test_unknown_item_is_404_and_writes_nothing(self, client, req_dir):
        r = client.post("/api/item/ID-999/review", json={"status": "APPROVED", "comment": "x"})
        assert r.status_code == 404
        assert r.json()["detail"] == "Item not found"
        assert not os.path.exists(os.path.join(str(req_dir), "ID-999"))

    @pytest.mark.parametrize("status", ["MAYBE", "PENDING", "", "REJECTED"])
    def test_invalid_status_is_422(self, client, sm, status):
        r = client.post("/api/item/ID-001/review", json={"status": status})
        assert r.status_code == 422
        assert "review_status" not in sm.kanban.get_item_details("ID-001")

    def test_missing_status_is_422(self, client):
        r = client.post("/api/item/ID-001/review", json={"comment": "no status"})
        assert r.status_code == 422

    def test_overlong_comment_is_422(self, client):
        r = client.post("/api/item/ID-001/review", json={"status": "APPROVED", "comment": "x" * 5001})
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_id", ["ID.001", "ID%20001", "ID$1"])
    def test_invalid_item_id_is_400(self, client, bad_id):
        r = client.post(f"/api/item/{bad_id}/review", json={"status": "APPROVED"})
        assert r.status_code == 400
        assert r.json()["detail"] == "Invalid item ID"

    def test_review_does_not_change_stage(self, client, sm):
        client.post("/api/item/ID-001/review", json={"status": "APPROVED"})
        assert sm.kanban.get_item_details("ID-001")["stage"] == "REVIEW_SPEC"
