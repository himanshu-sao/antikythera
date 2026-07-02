import unittest
import os
import shutil
from fastapi.testclient import TestClient
from api.main import app
from api.integration_hub import IntegrationHub
from api.secret_vault import SecretVault

class TestIntegrationsAPI(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for integrations config to avoid polluting real data
        self.test_dir = "tests/hub_test_dir_api"
        os.makedirs(self.test_dir, exist_ok=True)
        # Create fresh vault and hub using the test directory
        self.vault = SecretVault(self.test_dir)
        self.hub = IntegrationHub(self.test_dir, self.vault)
        # Override the app's hub for the duration of the test
        app.state.hub = self.hub
        self.client = TestClient(app)

    def tearDown(self):
        # Cleanup test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_add_and_patch_integration(self):
        # Add a new native integration
        add_resp = self.client.post(
            "/api/integrations",
            json={"name": "jira_test", "type": "native", "config": {"adapter_module": "api.adapters.jira"}}
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertEqual(add_resp.json()["status"], "success")

        # Patch the integration's config
        patch_resp = self.client.patch(
            "/api/integrations/jira_test",
            json={"config": {"url": "http://example.com", "token": "secret"}}
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["status"], "success")

        # Verify the updated config via GET list
        list_resp = self.client.get("/api/integrations")
        self.assertEqual(list_resp.status_code, 200)
        integrations = list_resp.json()
        jira_int = next((i for i in integrations if i["name"] == "jira_test"), None)
        self.assertIsNotNone(jira_int)
        # The config should include the original adapter_module plus the patched values
        self.assertEqual(jira_int["config"].get("adapter_module"), "api.adapters.jira")
        self.assertEqual(jira_int["config"].get("url"), "http://example.com")
        self.assertEqual(jira_int["config"].get("token"), "secret")

    def test_patch_nonexistent_integration(self):
        # Attempt to patch an integration that does not exist
        resp = self.client.patch(
            "/api/integrations/nonexistent",
            json={"config": {"test": True}}
        )
        # Expect 404 Not Found
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"])
