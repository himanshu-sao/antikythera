"""Tests for workflow_router.py save_template endpoint (B1 hardening)."""

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    """Test client with isolated template storage."""
    # The app already mounts workflow_router. We use the real app.state
    # but the template manager is file-backed; each test uses a unique template_id
    # and cleans up after itself.
    return TestClient(app)


def _cleanup_template(client: TestClient, template_id: str):
    """Helper to delete a template after a test."""
    client.delete(f"/api/workflows/templates/{template_id}")


class TestSaveTemplateAllowlist:
    """Tests for server-side adapter allowlist on POST /api/workflows/templates."""

    def test_save_template_happy_path_internal_adapter(self, client):
        """Template with allowed 'internal' adapter saves successfully."""
        template_id = "test_happy_internal"
        payload = {
            "template_id": template_id,
            "name": "Test Internal",
            "description": "Test template with internal adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "list_items",
                    "config": {"stage": "INTAKE"},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 200, response.json()
            body = response.json()
            assert body["status"] == "success"
            assert template_id in body["message"]
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_happy_path_github_adapter(self, client):
        """Template with allowed 'github' adapter saves successfully."""
        template_id = "test_happy_github"
        payload = {
            "template_id": template_id,
            "name": "Test GitHub",
            "description": "Test template with github adapter",
            "trigger": {"type": "webhook", "provider": "github", "config": {}},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_repos",
                    "config": {"org": "test-org"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 200, response.json()
            body = response.json()
            assert body["status"] == "success"
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_happy_path_jira_adapter(self, client):
        """Template with allowed 'jira' adapter saves successfully."""
        template_id = "test_happy_jira"
        payload = {
            "template_id": template_id,
            "name": "Test Jira",
            "description": "Test template with jira adapter",
            "trigger": {"type": "poll", "provider": "jira", "config": {}},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "jira",
                    "action": "list_tickets",
                    "config": {"jql": "project=TEST"},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 200, response.json()
            body = response.json()
            assert body["status"] == "success"
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_happy_path_ai_adapter(self, client):
        """Template with allowed 'ai' adapter saves successfully."""
        template_id = "test_happy_ai"
        payload = {
            "template_id": template_id,
            "name": "Test AI",
            "description": "Test template with ai adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "ai",
                    "action": "analyze",
                    "config": {},
                    "board_stage": "REVIEW_SPEC",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 200, response.json()
            body = response.json()
            assert body["status"] == "success"
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_rejects_shell_adapter(self, client):
        """Template with disallowed 'shell' adapter returns 422."""
        template_id = "test_reject_shell"
        payload = {
            "template_id": template_id,
            "name": "Test Shell",
            "description": "Template with shell adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "shell",
                    "action": "run_build",
                    "config": {"script": "build.sh"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template contains disallowed adapters"
            assert any("shell" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_rejects_bob_shell_adapter(self, client):
        """Template with disallowed 'bob_shell' adapter returns 422."""
        template_id = "test_reject_bob_shell"
        payload = {
            "template_id": template_id,
            "name": "Test BobShell",
            "description": "Template with bob_shell adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "bob_shell",
                    "action": "execute",
                    "config": {"command": "echo hello"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template contains disallowed adapters"
            assert any("bob_shell" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_rejects_unknown_adapter(self, client):
        """Template with unknown adapter returns 422."""
        template_id = "test_reject_unknown"
        payload = {
            "template_id": template_id,
            "name": "Test Unknown",
            "description": "Template with unknown adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "unknown_adapter",
                    "action": "do_something",
                    "config": {},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template contains disallowed adapters"
            assert any("unknown_adapter" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_rejects_multiple_disallowed_adapters(self, client):
        """Template with multiple disallowed adapters returns all violations."""
        template_id = "test_reject_multi"
        payload = {
            "template_id": template_id,
            "name": "Test Multi Reject",
            "description": "Template with multiple bad adapters",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "shell",
                    "action": "run",
                    "config": {},
                    "board_stage": "EXECUTING",
                },
                {
                    "id": 2,
                    "type": "action",
                    "adapter": "bob_shell",
                    "action": "exec",
                    "config": {},
                    "board_stage": "EXECUTING",
                },
                {
                    "id": 3,
                    "type": "action",
                    "adapter": "internal",
                    "action": "list_items",
                    "config": {},
                    "board_stage": "INTAKE",
                },
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template contains disallowed adapters"
            violations = body["detail"]["violations"]
            # Should report both shell and bob_shell, but not internal
            # Note: violation messages include the full allowlist, so "internal" appears in the message
            # but as part of the allowlist, not as a rejected adapter
            assert any("shell" in v and "bob" not in v for v in violations)
            assert any("bob_shell" in v for v in violations)
            # The internal adapter should NOT be rejected - it appears in allowlist but not as rejected
            assert not any("adapter 'internal'" in v for v in violations)
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_case_insensitive_adapter_check(self, client):
        """Adapter validation is case-insensitive (SHELL -> shell)."""
        template_id = "test_case_insensitive"
        payload = {
            "template_id": template_id,
            "name": "Test Case",
            "description": "Template with uppercase adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "SHELL",
                    "action": "run",
                    "config": {},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template contains disallowed adapters"
            assert any("shell" in v.lower() for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_empty_adapter_field(self, client):
        """Step with empty adapter field is not validated (allows legacy/compat)."""
        template_id = "test_empty_adapter"
        payload = {
            "template_id": template_id,
            "name": "Test Empty",
            "description": "Template with empty adapter",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "",
                    "action": "list_items",
                    "config": {},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            # Empty adapter should not trigger validation (may fail later in engine, but not here)
            assert response.status_code == 200, response.json()
        finally:
            _cleanup_template(client, template_id)

    def test_save_template_missing_template_id_returns_400(self, client):
        """Missing template_id returns 400."""
        payload = {
            "name": "No ID",
            "description": "Missing template_id",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "list_items",
                    "config": {},
                    "board_stage": "INTAKE",
                }
            ],
        }
        response = client.post("/api/workflows/templates", json=payload)
        assert response.status_code == 400
        assert "template_id is required" in response.json()["detail"]