"""Tests for workflow_router.py save_template endpoint (B1 hardening + B2 config validation)."""

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
                    "config": {"action": "list_items", "stage": "INTAKE"},
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


class TestSaveTemplateConfigValidation:
    """Tests for B2: Per-adapter step.config schema validation."""

    def test_internal_adapter_valid_move_item_config(self, client):
        """Valid move_item config for internal adapter passes."""
        template_id = "test_internal_move"
        payload = {
            "template_id": template_id,
            "name": "Test Internal Move",
            "description": "Valid move_item config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": {"action": "move_item", "item_id": "ITEM-123", "new_stage": "DONE"},
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

    def test_internal_adapter_valid_add_comment_config(self, client):
        """Valid add_comment config for internal adapter passes."""
        template_id = "test_internal_comment"
        payload = {
            "template_id": template_id,
            "name": "Test Internal Comment",
            "description": "Valid add_comment config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "add_comment",
                    "config": {"action": "add_comment", "item_id": "ITEM-123", "author": "Bot", "body": "Done!"},
                    "board_stage": "DONE",
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

    def test_internal_adapter_valid_list_items_config(self, client):
        """Valid list_items config for internal adapter passes."""
        template_id = "test_internal_list"
        payload = {
            "template_id": template_id,
            "name": "Test Internal List",
            "description": "Valid list_items config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "list_items",
                    "config": {"action": "list_items", "stage": "INTAKE"},
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

    def test_internal_adapter_rejects_invalid_action(self, client):
        """Invalid action for internal adapter returns 422."""
        template_id = "test_internal_bad_action"
        payload = {
            "template_id": template_id,
            "name": "Test Bad Action",
            "description": "Invalid action",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": {"action": "invalid_action", "item_id": "ITEM-123"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("invalid_action" in v or "action" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_internal_adapter_rejects_invalid_stage(self, client):
        """Invalid stage enum for internal adapter returns 422."""
        template_id = "test_internal_bad_stage"
        payload = {
            "template_id": template_id,
            "name": "Test Bad Stage",
            "description": "Invalid stage",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": {"action": "move_item", "item_id": "ITEM-123", "new_stage": "INVALID_STAGE"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("INVALID_STAGE" in v or "new_stage" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_internal_adapter_rejects_unknown_field(self, client):
        """Unknown field in internal adapter config returns 422 (additionalProperties: false)."""
        template_id = "test_internal_unknown_field"
        payload = {
            "template_id": template_id,
            "name": "Test Unknown Field",
            "description": "Unknown field in config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": {"action": "move_item", "item_id": "ITEM-123", "new_stage": "DONE", "unknown_field": "bad"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("unknown_field" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_internal_adapter_rejects_missing_required_action(self, client):
        """Missing required 'action' field returns 422."""
        template_id = "test_internal_missing_action"
        payload = {
            "template_id": template_id,
            "name": "Test Missing Action",
            "description": "Missing action",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "config": {"item_id": "ITEM-123", "new_stage": "DONE"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("action" in v and "required" in v.lower() for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_github_adapter_valid_list_repos_config(self, client):
        """Valid list_repos config for github adapter passes."""
        template_id = "test_github_list_repos"
        payload = {
            "template_id": template_id,
            "name": "Test GitHub List Repos",
            "description": "Valid list_repos config",
            "trigger": {"type": "webhook", "provider": "github", "config": {}},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_repos",
                    "config": {"org": "myorg", "type": "all", "per_page": 50},
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

    def test_github_adapter_valid_list_pull_requests_config(self, client):
        """Valid list_pull_requests config for github adapter passes."""
        template_id = "test_github_list_prs"
        payload = {
            "template_id": template_id,
            "name": "Test GitHub List PRs",
            "description": "Valid list_pull_requests config",
            "trigger": {"type": "webhook", "provider": "github", "config": {}},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_pull_requests",
                    "config": {"owner": "myorg", "repo": "myrepo", "state": "open", "per_page": 30},
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

    def test_github_adapter_valid_create_repo_config(self, client):
        """Valid create repo config for github adapter passes."""
        template_id = "test_github_create"
        payload = {
            "template_id": template_id,
            "name": "Test GitHub Create",
            "description": "Valid create repo config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "github",
                    "action": "create",
                    "config": {"name": "new-repo", "description": "Created by Antikythera", "private": True},
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

    def test_github_adapter_rejects_unknown_field(self, client):
        """Unknown field in github adapter config returns 422."""
        template_id = "test_github_unknown"
        payload = {
            "template_id": template_id,
            "name": "Test GitHub Unknown",
            "description": "Unknown field",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_repos",
                    "config": {"org": "myorg", "unknown_field": "bad"},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("unknown_field" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_github_adapter_rejects_invalid_enum(self, client):
        """Invalid enum value in github adapter config returns 422."""
        template_id = "test_github_bad_enum"
        payload = {
            "template_id": template_id,
            "name": "Test GitHub Bad Enum",
            "description": "Invalid type enum",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_repos",
                    "config": {"org": "myorg", "type": "invalid_type"},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("type" in v and "invalid_type" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_jira_adapter_valid_list_tickets_config(self, client):
        """Valid list_tickets config for jira adapter passes."""
        template_id = "test_jira_list_tickets"
        payload = {
            "template_id": template_id,
            "name": "Test Jira List Tickets",
            "description": "Valid list_tickets config",
            "trigger": {"type": "poll", "provider": "jira", "config": {}},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "jira",
                    "action": "list_tickets",
                    "config": {"jql": "project = TEST", "max_results": 25},
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

    def test_jira_adapter_valid_create_issue_config(self, client):
        """Valid create issue config for jira adapter passes."""
        template_id = "test_jira_create"
        payload = {
            "template_id": template_id,
            "name": "Test Jira Create",
            "description": "Valid create config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "jira",
                    "action": "create",
                    "config": {
                        "project_key": "TEST",
                        "issue_type": "Task",
                        "summary": "New issue",
                        "description": "Created by Antikythera",
                    },
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

    def test_jira_adapter_rejects_unknown_field(self, client):
        """Unknown field in jira adapter config returns 422."""
        template_id = "test_jira_unknown"
        payload = {
            "template_id": template_id,
            "name": "Test Jira Unknown",
            "description": "Unknown field",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "jira",
                    "action": "list_tickets",
                    "config": {"jql": "project = TEST", "unknown_field": "bad"},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("unknown_field" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_jira_adapter_rejects_invalid_max_results(self, client):
        """Invalid max_results (out of range) returns 422."""
        template_id = "test_jira_bad_max"
        payload = {
            "template_id": template_id,
            "name": "Test Jira Bad Max",
            "description": "max_results out of range",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "jira",
                    "action": "list_tickets",
                    "config": {"jql": "project = TEST", "max_results": 200},
                    "board_stage": "INTAKE",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("max_results" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_ai_adapter_valid_analyze_config(self, client):
        """Valid analyze config for ai adapter passes."""
        template_id = "test_ai_analyze"
        payload = {
            "template_id": template_id,
            "name": "Test AI Analyze",
            "description": "Valid analyze config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "ai",
                    "action": "analyze",
                    "config": {
                        "prompt": "Analyze this data",
                        "context": {"key": "value"},
                        "patterns": [{"pattern": "test"}],
                    },
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

    def test_ai_adapter_rejects_unknown_field(self, client):
        """Unknown field in ai adapter config returns 422."""
        template_id = "test_ai_unknown"
        payload = {
            "template_id": template_id,
            "name": "Test AI Unknown",
            "description": "Unknown field",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "ai",
                    "action": "analyze",
                    "config": {"prompt": "test", "unknown_field": "bad"},
                    "board_stage": "REVIEW_SPEC",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("unknown_field" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_multiple_steps_all_validated(self, client):
        """All steps in a multi-step template are validated."""
        template_id = "test_multi_step"
        payload = {
            "template_id": template_id,
            "name": "Test Multi Step",
            "description": "Multiple steps validation",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "list_items",
                    "config": {"action": "list_items", "stage": "INTAKE"},
                    "board_stage": "INTAKE",
                },
                {
                    "id": 2,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_repos",
                    "config": {"org": "myorg"},
                    "board_stage": "REFINEMENT",
                },
                {
                    "id": 3,
                    "type": "action",
                    "adapter": "jira",
                    "action": "list_tickets",
                    "config": {"jql": "project = TEST"},
                    "board_stage": "ARCHITECTURE",
                },
                {
                    "id": 4,
                    "type": "action",
                    "adapter": "ai",
                    "action": "analyze",
                    "config": {"prompt": "Analyze"},
                    "board_stage": "REVIEW_SPEC",
                },
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 200, response.json()
            body = response.json()
            assert body["status"] == "success"
        finally:
            _cleanup_template(client, template_id)

    def test_multiple_steps_one_invalid_config(self, client):
        """One invalid step config in multi-step template returns 422 with all violations."""
        template_id = "test_multi_one_bad"
        payload = {
            "template_id": template_id,
            "name": "Test Multi One Bad",
            "description": "One invalid config",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": {"action": "move_item", "item_id": "ITEM-1", "new_stage": "DONE"},
                    "board_stage": "EXECUTING",
                },
                {
                    "id": 2,
                    "type": "action",
                    "adapter": "github",
                    "action": "list_repos",
                    "config": {"org": "myorg", "invalid_field": "bad"},
                    "board_stage": "REFINEMENT",
                },
                {
                    "id": 3,
                    "type": "action",
                    "adapter": "jira",
                    "action": "list_tickets",
                    "config": {"jql": "project = TEST", "another_invalid": "bad"},
                    "board_stage": "ARCHITECTURE",
                },
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            violations = body["detail"]["violations"]
            # Should report violations for steps 2 and 3
            assert any("step 2" in v and "invalid_field" in v for v in violations)
            assert any("step 3" in v and "another_invalid" in v for v in violations)
            # Step 1 should not have violations
            assert not any("step 1" in v for v in violations)
        finally:
            _cleanup_template(client, template_id)

    def test_adapter_without_schema_skips_config_validation(self, client):
        """Adapter without a defined schema skips config validation (no error)."""
        # The 'ai' adapter has a schema, but we can test with empty config which is valid
        template_id = "test_no_schema"
        payload = {
            "template_id": template_id,
            "name": "Test No Schema",
            "description": "Adapter without schema",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "ai",  # Has schema, but we can test empty config
                    "action": "analyze",
                    "config": {},  # Empty config is valid for ai (no required fields)
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

    def test_config_not_object_returns_422(self, client):
        """Non-object config (e.g., string, array) returns 422."""
        template_id = "test_bad_config_type"
        payload = {
            "template_id": template_id,
            "name": "Test Bad Config Type",
            "description": "Config is not an object",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": "not an object",
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            assert any("config must be an object" in v for v in body["detail"]["violations"])
        finally:
            _cleanup_template(client, template_id)

    def test_case_insensitive_adapter_config_validation(self, client):
        """Config validation is case-insensitive for adapter name."""
        template_id = "test_case_insensitive"
        payload = {
            "template_id": template_id,
            "name": "Test Case Insensitive",
            "description": "UPPERCASE adapter name",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "INTERNAL",  # Uppercase
                    "action": "move_item",
                    "config": {"action": "move_item", "item_id": "ITEM-1", "new_stage": "DONE"},
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

    def test_config_validation_error_includes_field_path(self, client):
        """Validation error includes the field path for nested errors."""
        template_id = "test_field_path"
        payload = {
            "template_id": template_id,
            "name": "Test Field Path",
            "description": "Error includes field path",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "id": 1,
                    "type": "action",
                    "adapter": "internal",
                    "action": "move_item",
                    "config": {"action": "move_item", "item_id": "ITEM-1", "new_stage": "NOT_A_STAGE"},
                    "board_stage": "EXECUTING",
                }
            ],
        }
        try:
            response = client.post("/api/workflows/templates", json=payload)
            assert response.status_code == 422, response.json()
            body = response.json()
            assert body["detail"]["message"] == "Template step config validation failed"
            violations = body["detail"]["violations"]
            assert any("new_stage" in v and "NOT_A_STAGE" in v for v in violations)
        finally:
            _cleanup_template(client, template_id)