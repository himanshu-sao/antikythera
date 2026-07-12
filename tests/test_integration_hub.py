import unittest
import os
import shutil
from api.secret_vault import SecretVault
from api.integration_hub import IntegrationHub

class TestIntegrationHub(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/hub_test_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.vault = SecretVault(self.test_dir)
        self.hub = IntegrationHub(self.test_dir, self.vault)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_add_and_get_integration(self):
        name = "github_prod"
        config = {"adapter_module": "api.adapters.github"}
        self.assertTrue(self.hub.add_integration(name, "native", config))
        
        integration = self.hub.get_integration(name)
        self.assertEqual(integration["type"], "native")
        self.assertEqual(integration["config"]["adapter_module"], "api.adapters.github")

    def test_list_integrations(self):
        self.hub.add_integration("i1", "native", {})
        self.hub.add_integration("i2", "mcp", {})
        integrations = self.hub.list_integrations()
        self.assertEqual(len(integrations), 2)

    def test_delete_integration(self):
        name = "delete_me"
        self.hub.add_integration(name, "native", {})
        self.assertTrue(self.hub.delete_integration(name))
        self.assertIsNone(self.hub.get_integration(name))

    def test_execute_native_mock(self):
        name = "native_test"
        self.hub.add_integration(name, "native", {"adapter_module": "mock_module"})
        # P1.1: _execute_native now does real adapter dispatch instead of
        # returning a fixed "Native … executed …" stub.  A non-importable
        # adapter_module is therefore a configuration error, surfaced as
        # status="error" with the load failure in the result.
        result = self.hub.execute_action(name, "test_action", {})
        self.assertEqual(result["status"], "error")
        self.assertIn("mock_module", result["result"])

if __name__ == "__main__":
    unittest.main()
