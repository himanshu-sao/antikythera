import os
import unittest
from api.integration_hub import IntegrationHub

class TestCredentialResolution(unittest.TestCase):
    def setUp(self):
        # Ensure env vars are set for the test
        os.environ["JIRA_BASE_URL"] = "https://example.atlassian.net"
        os.environ["JIRA_PAT"] = "dummy_pat"
        self.test_dir = "tests/hub_test_dir_credentials"
        os.makedirs(self.test_dir, exist_ok=True)
        # No vault needed – pass None
        self.hub = IntegrationHub(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)

    def test_jira_credentials_resolved_from_placeholders(self):
        # Add integration with placeholders
        config = {
            "adapter_module": "api.adapters.jira",
            "jira_url": "${env:JIRA_BASE_URL}",
            "token": "${env:JIRA_PAT}"
        }
        self.hub.add_integration("jira_test", "native", config)
        # Validate credentials – should set status to connected
        self.hub._validate_credentials_and_update_status("jira_test")
        integration = self.hub.get_integration("jira_test")
        self.assertEqual(integration.get("status"), "connected")
