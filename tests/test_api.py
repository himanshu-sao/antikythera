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

# --- Path Traversal Tests (R5.2) ---

    def test_get_artifact_path_traversal_dotdot(self):
        """Attempt path traversal with ../ in item_id should return 400.
        
        FastAPI normalizes /../ in URL paths before routing, so /api/item/../artifact/spec.md
        becomes /api/artifact/spec.md which won't match the route at all (404).
        This test verifies the route doesn't accidentally serve files via path normalization.
        """
        response = self.client.get("/api/item/../artifact/spec.md")
        # FastAPI normalizes the path, so this becomes /api/artifact/spec.md — a 404
        self.assertIn(response.status_code, [400, 404])

    def test_get_artifact_valid_item_id_not_found(self):
        """Valid item ID format but no artifact file should return 204."""
        response = self.client.get("/api/item/ID-999/artifact/spec.md")
        self.assertEqual(response.status_code, 204)

    def test_get_artifact_invalid_artifact_name(self):
        """Invalid artifact name should return 400."""
        response = self.client.get("/api/item/ID-001/artifact/secret.txt")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid artifact name")

    def test_get_artifact_item_id_with_special_chars(self):
        """Item ID with special characters (not alphanumeric/hyphen) should return 400."""
        response = self.client.get("/api/item/ID_001/artifact/spec.md")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid item ID")

    def test_get_artifact_item_id_with_dots(self):
        """Item ID with dots should return 400."""
        response = self.client.get("/api/item/ID.001/artifact/spec.md")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid item ID")

    def test_get_artifact_item_id_with_spaces(self):
        """Item ID with spaces should return 400."""
        response = self.client.get("/api/item/ID%20001/artifact/spec.md")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid item ID")

    def test_get_artifact_item_id_empty_after_upper(self):
        """Item ID that becomes empty or invalid after .upper() should be rejected."""
        response = self.client.get("/api/item/%00/artifact/spec.md")
        self.assertIn(response.status_code, [400, 404, 422])

    def test_get_artifact_valid_item_id_success(self):
        """Valid item ID and artifact name should work (if file exists)."""
        # Create a test artifact file
        test_dir = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", "ID-001")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "spec.md")
        with open(test_file, "w") as f:
            f.write("# Test Spec")
        
        try:
            response = self.client.get("/api/item/ID-001/artifact/spec.md")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, "# Test Spec")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
            # Clean up empty dirs
            try:
                os.removedirs(test_dir)
            except OSError:
                pass

    def test_move_item_lowercase_item_id(self):
        """Move endpoint should normalize lowercase item_id to uppercase."""
        response = self.client.post("/api/move", json={"item_id": "id-001", "new_stage": "REFINEMENT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        # Verify file update used uppercase key
        with open(self.test_state_path, "r") as f:
            state = json.load(f)
            self.assertEqual(state["items"]["ID-001"]["stage"], "REFINEMENT")

    def test_get_item_lowercase_item_id(self):
        """Get item endpoint should normalize lowercase item_id to uppercase."""
        response = self.client.get("/api/item/id-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Item 1")

    def test_get_artifact_lowercase_item_id(self):
        """Lowercase item ID should be normalized to uppercase and work."""
        test_dir = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", "ID-001")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "spec.md")
        with open(test_file, "w") as f:
            f.write("# Test Spec")

        try:
            response = self.client.get("/api/item/id-001/artifact/spec.md")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, "# Test Spec")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
            try:
                os.removedirs(test_dir)
            except OSError:
                pass

    # --- Artifact Content Update Tests (T6.1 - T6.3) ---

    def test_update_artifact_content_success(self):
        """Successfully update review.md content."""
        test_dir = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", "ID-001")
        os.makedirs(test_dir, exist_ok=True)
        artifact_path = os.path.join(test_dir, "review.md")

        content = "Updated review content"
        response = self.client.post("/api/item/ID-001/artifact/review.md/content", json={"content": content})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        # Verify file content
        with open(artifact_path, "r") as f:
            self.assertEqual(f.read(), content)

        # Clean up
        if os.path.exists(artifact_path):
            os.remove(artifact_path)
        try:
            os.removedirs(test_dir)
        except OSError:
            pass

    def test_update_artifact_content_invalid_artifact(self):
        """Only review.md should be editable."""
        test_dir = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", "ID-001")
        os.makedirs(test_dir, exist_ok=True)
    
        response = self.client.post("/api/item/ID-001/artifact/spec.md/content", json={"content": "new content"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only review.md can be edited")
        
        try:
            os.removedirs(test_dir)
        except OSError:
            pass


    def test_update_artifact_content_path_traversal(self):
        """Path traversal in item_id should return 400."""
        response = self.client.post("/api/item/../artifact/review.md/content", json={"content": "hack"})
        self.assertIn(response.status_code, [400, 404])

    def test_update_artifact_content_missing_content(self):
        """Request without content field should return 400."""
        response = self.client.post("/api/item/ID-001/artifact/review.md/content", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Missing content field")

    def test_update_artifact_content_not_found_dir(self):
        """Writing to a non-existent item directory should handle error gracefully (usually 500 or 404)."""
        response = self.client.post("/api/item/ID-999/artifact/review.md/content", json={"content": "text"})
        self.assertEqual(response.status_code, 500)

    def test_update_item_due_date_success(self):
        """Successfully update the due date of an item."""
        due_date = "2026-12-31"
        response = self.client.patch("/api/item/ID-001", json={"due_date": due_date})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        # Verify file update
        with open(self.test_state_path, "r") as f:
            state = json.load(f)
            self.assertEqual(state["items"]["ID-001"]["due_date"], due_date)

    def test_update_item_invalid_due_date(self):
        """Updating with an invalid date format should return 422 (Pydantic validation error)."""
        response = self.client.patch("/api/item/ID-001", json={"due_date": "31-12-2026"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
