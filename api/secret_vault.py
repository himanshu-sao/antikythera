import os
import json
import base64
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional
from filelock import FileLock

class SecretVault:
    """
    Secure storage for integration credentials.
    Uses AES-128 (Fernet) for encryption at rest.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.vault_path = os.path.join(base_dir, "secrets.vault")
        self.key_path = os.path.join(base_dir, ".vault.key")
        self._lock = FileLock(self.vault_path + ".lock")
        self._ensure_key()
        self.fernet = Fernet(self._load_key())

    def _ensure_key(self):
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(key)
            os.chmod(self.key_path, 0o600)

    def _load_key(self) -> bytes:
        with open(self.key_path, "rb") as f:
            return f.read()

    def _load_vault(self) -> Dict[str, Any]:
        if not os.path.exists(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()
                if not encrypted_data:
                    return {}
                decrypted_data = self.fernet.decrypt(encrypted_data)
                return json.loads(decrypted_data)
        except Exception as e:
            print(f"Vault decryption error: {e}")
            return {}

    def _save_vault(self, data: Dict[str, Any]):
        json_data = json.dumps(data).encode()
        encrypted_data = self.fernet.encrypt(json_data)
        with open(self.vault_path, "wb") as f:
            f.write(encrypted_data)

    def store_secret(self, profile_id: str, secret_data: Dict[str, Any]) -> bool:
        """Stores a set of credentials for a specific profile."""
        try:
            with self._lock:
                vault = self._load_vault()
                vault[profile_id] = secret_data
                self._save_vault(vault)
            return True
        except Exception:
            return False

    def get_secret(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves credentials for a profile."""
        try:
            with self._lock:
                vault = self._load_vault()
                return vault.get(profile_id)
        except Exception:
            return None

    def delete_secret(self, profile_id: str) -> bool:
        try:
            with self._lock:
                vault = self._load_vault()
                if profile_id in vault:
                    del vault[profile_id]
                    self._save_vault(vault)
                    return True
                return False
        except Exception:
            return False

    def list_profiles(self) -> list[str]:
        try:
            with self._lock:
                vault = self._load_vault()
                return list(vault.keys())
        except Exception:
            return []
