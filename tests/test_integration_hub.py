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


# --------------------------------------------------------------------------
# SEC-5: list responses mask secrets; update keeps stored secret on "*****".
# These use a pytest tmp_path hub so nothing touches the real automation-ideas/.
# --------------------------------------------------------------------------
import pytest

MASK = "*****"


@pytest.fixture
def tmp_hub(tmp_path):
    return IntegrationHub(str(tmp_path))


class TestListMasksSecrets:
    def test_token_and_password_masked_in_list(self, tmp_hub):
        tmp_hub.add_integration("svc", "native", {
            "adapter_module": "api.adapters.github",
            "token": "tok-literal-value",
            "password": "pw-literal-value",
            "api_key": "key-literal-value",
            "url": "https://example.invalid",
        })
        items = {i["name"]: i for i in tmp_hub.list_integrations()}
        cfg = items["svc"]["config"]
        assert cfg["token"] == MASK
        assert cfg["password"] == MASK
        assert cfg["api_key"] == MASK
        # non-secret fields are left readable
        assert cfg["adapter_module"] == "api.adapters.github"
        assert cfg["url"] == "https://example.invalid"

    def test_mcp_env_values_masked_in_list(self, tmp_hub):
        tmp_hub.add_integration("mcp1", "mcp", {
            "command": "echo",
            "args": [],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GH_TOKEN}", "LOG_LEVEL": "debug"},
        })
        cfg = {i["name"]: i for i in tmp_hub.list_integrations()}["mcp1"]["config"]
        assert cfg["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == MASK
        assert cfg["env"]["LOG_LEVEL"] == MASK

    def test_path_like_keys_not_masked(self, tmp_hub):
        # "path" contains "pat" as a substring but is not a secret field.
        tmp_hub.add_integration("p", "native", {"adapter_module": "x", "path": "/tmp/a"})
        cfg = tmp_hub.get_integration("p")["config"]
        listed = {i["name"]: i for i in tmp_hub.list_integrations()}["p"]["config"]
        assert listed["path"] == "/tmp/a"
        assert cfg["path"] == "/tmp/a"

    def test_masking_does_not_change_stored_secret(self, tmp_hub):
        tmp_hub.add_integration("svc", "native", {"adapter_module": "a", "token": "stored-tok"})
        tmp_hub.list_integrations()
        assert tmp_hub.get_integration("svc")["config"]["token"] == "stored-tok"

    def test_empty_secret_value_not_replaced_by_mask(self, tmp_hub):
        tmp_hub.add_integration("svc", "native", {"adapter_module": "a", "token": ""})
        cfg = {i["name"]: i for i in tmp_hub.list_integrations()}["svc"]["config"]
        assert cfg["token"] == ""


class TestUpdatePreservesSecretOnPlaceholder:
    def test_placeholder_keeps_stored_token(self, tmp_hub):
        tmp_hub.add_integration("svc", "native", {"adapter_module": "a", "token": "stored-tok"})
        tmp_hub.update_integration("svc", {"token": MASK, "extra": "v"})
        cfg = tmp_hub.get_integration("svc")["config"]
        assert cfg["token"] == "stored-tok"
        assert cfg["extra"] == "v"

    def test_placeholder_keeps_stored_api_key_and_password(self, tmp_hub):
        # Regression: only four hard-coded keys were preserved before SEC-5.
        tmp_hub.add_integration("svc", "native", {
            "adapter_module": "a", "api_key": "stored-key", "password": "stored-pw",
        })
        tmp_hub.update_integration("svc", {"api_key": MASK, "password": MASK})
        cfg = tmp_hub.get_integration("svc")["config"]
        assert cfg["api_key"] == "stored-key"
        assert cfg["password"] == "stored-pw"

    def test_placeholder_never_stored_as_literal_when_no_prior_value(self, tmp_hub):
        tmp_hub.add_integration("svc", "native", {"adapter_module": "a"})
        tmp_hub.update_integration("svc", {"token": MASK})
        cfg = tmp_hub.get_integration("svc")["config"]
        assert "token" not in cfg or cfg["token"] != MASK

    def test_placeholder_inside_mcp_env_keeps_stored_value(self, tmp_hub):
        tmp_hub.add_integration("mcp1", "mcp", {
            "command": "echo", "args": [], "env": {"GH_TOKEN": "${env:GH_TOKEN}"},
        })
        tmp_hub.update_integration("mcp1", {"env": {"GH_TOKEN": MASK}})
        env = tmp_hub.get_integration("mcp1")["config"]["env"]
        assert env["GH_TOKEN"] == "${env:GH_TOKEN}"

    def test_real_new_value_replaces_stored_secret(self, tmp_hub):
        tmp_hub.add_integration("svc", "native", {"adapter_module": "a", "token": "old"})
        tmp_hub.update_integration("svc", {"token": "new-value"})
        assert tmp_hub.get_integration("svc")["config"]["token"] == "new-value"


# --------------------------------------------------------------------------
# 2.16 (hub part): atomic writes under the lock, corrupt file is surfaced
# --------------------------------------------------------------------------
import glob
import json
import threading

from api.integration_hub import IntegrationConfigCorruptError


class TestAtomicWritesAndCorruptFile:
    def test_save_leaves_no_temp_files_and_valid_json(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        hub.add_integration("a", "native", {"adapter_module": "x"})
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp") or ".tmp" in p]
        assert leftovers == []
        with open(hub.config_path) as f:
            assert "a" in json.load(f)

    def test_failed_write_keeps_previous_file_intact(self, tmp_path, monkeypatch):
        hub = IntegrationHub(str(tmp_path))
        hub.add_integration("a", "native", {"adapter_module": "x"})
        before = open(hub.config_path).read()

        def boom(*_a, **_k):
            raise OSError("simulated rename failure")

        monkeypatch.setattr("api.integration_hub.os.replace", boom)
        with pytest.raises(Exception):
            hub.add_integration("b", "native", {"adapter_module": "y"})
        monkeypatch.undo()
        assert open(hub.config_path).read() == before
        assert [p for p in os.listdir(tmp_path) if ".tmp" in p] == []

    def test_lock_path_is_used(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        hub.add_integration("a", "native", {"adapter_module": "x"})
        assert os.path.exists(hub._lock_path)

    def test_corrupt_file_is_backed_up_and_raises(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        with open(hub.config_path, "w") as f:
            f.write("{ this is not json")
        with pytest.raises(IntegrationConfigCorruptError):
            hub.list_integrations()
        backups = glob.glob(hub.config_path + ".corrupt-*")
        assert len(backups) == 1
        assert open(backups[0]).read() == "{ this is not json"
        # the original is left in place (nothing is deleted or silently reset)
        assert open(hub.config_path).read() == "{ this is not json"

    def test_corrupt_file_does_not_return_empty_dict(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        with open(hub.config_path, "w") as f:
            f.write("")
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()

    def test_add_on_corrupt_file_does_not_overwrite_it(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        with open(hub.config_path, "w") as f:
            f.write("not-json")
        with pytest.raises(Exception):
            hub.add_integration("a", "native", {"adapter_module": "x"})
        assert open(hub.config_path).read() == "not-json"

    def test_repeated_loads_do_not_pile_up_identical_backups(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        with open(hub.config_path, "w") as f:
            f.write("garbage")
        for _ in range(3):
            with pytest.raises(IntegrationConfigCorruptError):
                hub._load_config()
        assert len(glob.glob(hub.config_path + ".corrupt-*")) == 1

    def test_non_object_json_is_corrupt(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        with open(hub.config_path, "w") as f:
            f.write("[1, 2, 3]")
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()

    def test_missing_file_still_returns_empty(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        assert hub._load_config() == {}
        assert hub.list_integrations() == []

    def test_concurrent_adds_do_not_lose_updates(self, tmp_path):
        hub = IntegrationHub(str(tmp_path))
        errors = []

        def worker(i):
            try:
                IntegrationHub(str(tmp_path)).add_integration(f"n{i}", "native", {"adapter_module": "x"})
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(hub.list_integrations()) == 12
