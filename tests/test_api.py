import unittest
import json
import os
import shutil
from fastapi.testclient import TestClient
from api.main import app
from api.state_manager import StateManager

class TestApi(unittest.TestCase):
    def setUp(self):
        self.test_state_path = "tests/test_state.json"
        self.client = TestClient(app)
        
        # Mock the state manager path in api.main
        import api.main
        api.main.STATE_PATH = self.test_state_path
        api.main.state_manager = StateManager(self.test_state_path)
        
        # Initial state
        self.initial_state = {
            "last_heartbeat": "2026-05-15T00:00:00Z",
            "items": {
                "ID-001": {
                    "title": "Test Item 1",
                    "priority": "High",
                    "stage": "INTAKE",
                    "updated_at": "2026-05-15T00:00:00Z"
                }
            }
        }
        with open(self.test_state_path, "w") as f:
            json.dump(self.initial_state, f)

    def tearDown(self):
        if os.path.exists(self.test_state_path):
            os.remove(self.test_state_path)

    def test_get_state(self):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.initial_state)

    def test_move_item_success(self):
        response = self.client.post("/api/move", json={"item_id": "ID-001", "new_stage": "REFINEMENT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        # Verify file update
        with open(self.test_state_path, "r") as f:
            state = json.load(f)
            self.assertEqual(state["items"]["ID-001"]["stage"], "REFINEMENT")

    def test_move_item_not_found(self):
        response = self.client.post("/api/move", json={"item_id": "ID-999", "new_stage": "REFINEMENT"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Item not found")

    def test_get_item_success(self):
        response = self.client.get("/api/item/ID-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Item 1")

    def test_get_item_not_found(self):
        response = self.client.get("/api/item/ID-999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Item not found")

if __name__ == "__main__":
    unittest.main()
