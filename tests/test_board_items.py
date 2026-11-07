"""POST/PATCH /api/items priority handling (2.5, T17).

The board router is mounted on a throwaway app and pointed at a
WorkflowStateManager living in tmp_path, so no real automation-ideas data is
touched.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import board_router
from api.workflow_state_manager import WorkflowStateManager


@pytest.fixture
def sm(tmp_path, monkeypatch):
    manager = WorkflowStateManager(str(tmp_path))
    monkeypatch.setattr(board_router, "get_state_manager", lambda: manager)
    return manager


@pytest.fixture
def client(sm):
    app = FastAPI()
    app.include_router(board_router.router)
    return TestClient(app)


class TestCreateItemPriority:
    @pytest.mark.parametrize("sent,stored", [
        ("high", "high"),
        ("low", "low"),
        ("critical", "critical"),
        ("HIGH", "high"),
        ("Critical", "critical"),
    ])
    def test_priority_is_stored_lowercase(self, client, sm, sent, stored):
        r = client.post("/api/items", json={"item_id": "p-1", "title": "T", "priority": sent})
        assert r.status_code == 200, r.text
        assert sm.kanban.get_item_details("P-1")["priority"] == stored

    def test_omitted_priority_defaults_to_medium(self, client, sm):
        r = client.post("/api/items", json={"item_id": "p-2", "title": "T"})
        assert r.status_code == 200
        assert sm.kanban.get_item_details("P-2")["priority"] == "medium"

    def test_null_priority_defaults_to_medium(self, client, sm):
        r = client.post("/api/items", json={"item_id": "p-3", "title": "T", "priority": None})
        assert r.status_code == 200
        assert sm.kanban.get_item_details("P-3")["priority"] == "medium"

    def test_invalid_priority_rejected(self, client, sm):
        r = client.post("/api/items", json={"item_id": "p-4", "title": "T", "priority": "urgent"})
        assert r.status_code == 422
        assert sm.kanban.get_item_details("P-4") is None

    def test_state_endpoint_reflects_priority(self, client):
        client.post("/api/items", json={"item_id": "p-5", "title": "T", "priority": "high"})
        assert client.get("/api/state").json()["items"]["P-5"]["priority"] == "high"

    def test_other_fields_still_passed_through(self, client, sm):
        client.post("/api/items", json={
            "item_id": "p-6", "title": "T", "goal": "g", "description": "d",
            "priority": "low", "complexity": "Simple", "due_date": "2026-12-31",
        })
        item = sm.kanban.get_item_details("P-6")
        assert (item["goal"], item["description"], item["due_date"]) == ("g", "d", "2026-12-31")
        assert item["priority"] == "low"

    def test_duplicate_still_rejected(self, client):
        assert client.post("/api/items", json={"item_id": "p-7", "title": "T"}).status_code == 200
        assert client.post("/api/items", json={"item_id": "p-7", "title": "T", "priority": "high"}).status_code == 400


class TestUpdateItemPriority:
    def test_update_priority_is_lowercased(self, client, sm):
        client.post("/api/items", json={"item_id": "u-1", "title": "T"})
        r = client.patch("/api/item/u-1", json={"priority": "HIGH"})
        assert r.status_code == 200, r.text
        assert sm.kanban.get_item_details("U-1")["priority"] == "high"

    def test_update_invalid_priority_rejected(self, client):
        client.post("/api/items", json={"item_id": "u-2", "title": "T"})
        assert client.patch("/api/item/u-2", json={"priority": "nope"}).status_code == 422

    def test_update_without_priority_leaves_it_alone(self, client, sm):
        client.post("/api/items", json={"item_id": "u-3", "title": "T", "priority": "high"})
        client.patch("/api/item/u-3", json={"title": "New"})
        assert sm.kanban.get_item_details("U-3")["priority"] == "high"


class TestKanbanManagerPriority:
    def test_manager_create_item_priority_kwarg(self, tmp_path):
        from api.managers.kanban_state_manager import KanbanStateManager
        m = KanbanStateManager(str(tmp_path))
        m.create_item("a-1", "T", priority="HIGH")
        m.create_item("a-2", "T")
        m.create_item("a-3", "T", priority="")
        assert m.get_item_details("A-1")["priority"] == "high"
        assert m.get_item_details("A-2")["priority"] == "medium"
        assert m.get_item_details("A-3")["priority"] == "medium"
