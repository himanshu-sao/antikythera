import unittest
import os
import shutil
from fastapi.testclient import TestClient
from api.main import app
from api.integration_hub import IntegrationHub
from api.secret_vault import SecretVault

class TestIntegrationStatus(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/hub_test_dir_status"
        os.makedirs(self.test_dir, exist_ok=True)
        self.vault = SecretVault(self.test_dir)
        self.hub = IntegrationHub(self.test_dir, self.vault)
        # Override app hub for test isolation
        app.state.hub = self.hub
        self.client = TestClient(app)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_jira_status_flow(self):
        # Add Jira native integration (no credentials yet)
        add_resp = self.client.post(
            "/api/integrations",
            json={"name": "jira_test", "type": "native", "config": {"adapter_module": "api.adapters.jira"}}
        )
        self.assertEqual(add_resp.status_code, 200)

        # Test endpoint should fail with 401 (missing credentials)
        test_resp = self.client.post("/api/integrations/jira_test/test")
        self.assertEqual(test_resp.status_code, 404)

        # Patch config (still no credentials) – status should become error
        patch_resp = self.client.patch(
            "/api/integrations/jira_test",
            json={"config": {"some": "value"}}
        )
        self.assertEqual(patch_resp.status_code, 200)
        list_resp = self.client.get("/api/integrations")
        jira_int = next(i for i in list_resp.json() if i["name"] == "jira_test")
        self.assertEqual(jira_int["status"], "error")

        # Store required secrets
        self.vault.store_secret("jira", {"token": "dummy"})
        self.vault.store_secret("jira_url", "https://example.atlassian.net")

        # Patch again to trigger validation – now status should be connected
        patch_resp2 = self.client.patch(
            "/api/integrations/jira_test",
            json={"config": {"some": "new"}}
        )
        self.assertEqual(patch_resp2.status_code, 200)
        list_resp2 = self.client.get("/api/integrations")
        jira_int2 = next(i for i in list_resp2.json() if i["name"] == "jira_test")
        self.assertEqual(jira_int2["status"], "connected")
