import os
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from api.main import app

class TestIntegrationRouterCredentials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set environment variables used by the integration
        os.environ["JIRA_BASE_URL"] = "https://example.atlassian.net"
        os.environ["JIRA_PAT"] = "dummy_pat"
        cls.client = TestClient(app)

    def setUp(self):
        # Ensure a clean integration list before each test
        self.client.delete("/api/integrations/jira_test")  # ignore errors if not exist

    def test_jira_test_endpoint_resolves_placeholders(self):
        # Create a Jira integration with placeholders
        payload = {
            "name": "jira_test",
            "type": "native",
            "config": {
                "adapter_module": "api.adapters.jira",
                "jira_url": "${env:JIRA_BASE_URL}",
                "token": "${env:JIRA_PAT}"
            }
        }
        resp = self.client.post("/api/integrations", json=payload)
        self.assertEqual(resp.status_code, 200)

        # Mock httpx.AsyncClient.get to avoid real network call
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"self": "user", "key": "USER"}
        async_mock_client = AsyncMock()
        async_mock_client.__aenter__.return_value = async_mock_client
        async_mock_client.__aexit__.return_value = AsyncMock()
        async_mock_client.get.return_value = mock_response

        with patch('httpx.AsyncClient', return_value=async_mock_client):
            test_resp = self.client.post("/api/integrations/jira_test/test")
            self.assertEqual(test_resp.status_code, 200)
            data = test_resp.json()
            self.assertIn('data', data)
            self.assertIn('principal', data['data'])
            self.assertEqual(data['data']['principal']['self'], "user")
