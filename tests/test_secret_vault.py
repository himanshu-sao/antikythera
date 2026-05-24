import unittest
import os
import shutil
from api.secret_vault import SecretVault

class TestSecretVault(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/vault_test_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.vault = SecretVault(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_store_and_retrieve(self):
        profile_id = "github_prod"
        secrets = {"api_key": "ghp_123456789", "org": "nous-research"}
        
        self.assertTrue(self.vault.store_secret(profile_id, secrets))
        retrieved = self.vault.get_secret(profile_id)
        self.assertEqual(retrieved, secrets)

    def test_encryption_at_rest(self):
        profile_id = "test_secret"
        secrets = {"token": "supersecret"}
        self.vault.store_secret(profile_id, secrets)
        
        vault_path = os.path.join(self.test_dir, "secrets.vault")
        with open(vault_path, "rb") as f:
            content = f.read()
            # Ensure the raw content is not plain text JSON
            self.assertNotIn(b"supersecret", content)

    def test_delete_secret(self):
        profile_id = "to_be_deleted"
        self.vault.store_secret(profile_id, {"k": "v"})
        self.assertTrue(self.vault.delete_secret(profile_id))
        self.assertIsNone(self.vault.get_secret(profile_id))

    def test_list_profiles(self):
        self.vault.store_secret("p1", {"k": "v"})
        self.vault.store_secret("p2", {"k": "v"})
        profiles = self.vault.list_profiles()
        self.assertIn("p1", profiles)
        self.assertIn("p2", profiles)
        self.assertEqual(len(profiles), 2)

if __name__ == "__main__":
    unittest.main()
