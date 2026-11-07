"""P1-10 prep: ``ANTIKYTHERA_HOME`` redirects both the default AI config and the .ai_env file.

``ANTIKYTHERA_HOME`` names the ``.antikythera`` directory itself (the same meaning
docker/entrypoint.sh gives it). Without it, the default location is unchanged:
the real home from the password database, then ``~/.antikythera``.
"""
import json
import os
from pathlib import Path

import pytest

import api.services.ai_engine_config as aec

# conftest's autouse isolate_provider_env replaces these two methods with fixed tmp paths.
# This module tests the real methods, so it restores the originals for each test.
_REAL_DEFAULT_PATH = aec.AIEngineConfigService.__dict__["_get_default_config_path"]
_REAL_ENV_PATH = aec.AIEngineConfigService.__dict__["_persistent_env_path"]


@pytest.fixture(autouse=True)
def real_path_methods(monkeypatch):
    monkeypatch.setattr(aec.AIEngineConfigService, "_get_default_config_path", _REAL_DEFAULT_PATH)
    monkeypatch.setattr(aec.AIEngineConfigService, "_persistent_env_path", _REAL_ENV_PATH)
    monkeypatch.delenv("ANTIKYTHERA_HOME", raising=False)
    yield


def _svc_without_load(monkeypatch):
    """Build a service object without running load_config or the persistent env load."""
    monkeypatch.setattr(aec.AIEngineConfigService, "load_config", lambda self: aec.DEFAULT_AI_ENGINE_CONFIG)
    monkeypatch.setattr(aec.AIEngineConfigService, "_load_persistent_env", lambda self: None)
    return aec.AIEngineConfigService


class TestDefaultConfigPath:
    def test_override_directory_is_used(self, tmp_path, monkeypatch):
        home = tmp_path / "ah"
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
        svc_cls = _svc_without_load(monkeypatch)
        obj = object.__new__(svc_cls)
        assert obj._get_default_config_path() == str(home / "ai_config.json")

    def test_override_directory_is_created(self, tmp_path, monkeypatch):
        home = tmp_path / "nested" / "ah"
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
        obj = object.__new__(_svc_without_load(monkeypatch))
        obj._get_default_config_path()
        assert home.is_dir()

    def test_override_expands_user_and_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(tmp_path / "x"))
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert os.path.dirname(obj._get_default_config_path()) == str(tmp_path / "x")

    def test_empty_override_falls_back_to_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTIKYTHERA_HOME", "")
        monkeypatch.setattr(aec.Path, "home", classmethod(lambda cls: tmp_path))
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert obj._get_default_config_path() == str(tmp_path / ".antikythera" / "ai_config.json")

    def test_unset_falls_back_to_home_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ANTIKYTHERA_HOME", raising=False)
        monkeypatch.setattr(aec.Path, "home", classmethod(lambda cls: tmp_path))
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert obj._get_default_config_path() == str(tmp_path / ".antikythera" / "ai_config.json")


class TestPersistentEnvPath:
    def test_override_directory_is_used(self, tmp_path, monkeypatch):
        home = tmp_path / "ah2"
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert obj._persistent_env_path() == str(home / ".ai_env")
        assert home.is_dir()

    def test_monkeypatched_home_does_not_redirect_without_override(self, tmp_path, monkeypatch):
        # Setting HOME does not move the pwd-based default; that is the documented behaviour.
        monkeypatch.delenv("ANTIKYTHERA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert not obj._persistent_env_path().startswith(str(tmp_path / "fake-home"))

    def test_override_wins_over_pwd_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(tmp_path / "wins"))
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert obj._persistent_env_path().startswith(str(tmp_path / "wins"))

    def test_default_uses_pwd_home_when_no_override(self, monkeypatch, tmp_path):
        import pwd
        monkeypatch.delenv("ANTIKYTHERA_HOME", raising=False)
        real = pwd.getpwuid(os.getuid()).pw_dir
        # Stub mkdir so the real ~/.antikythera is not created by this test.
        monkeypatch.setattr(aec.Path, "mkdir", lambda self, *a, **k: None)
        obj = object.__new__(_svc_without_load(monkeypatch))
        assert obj._persistent_env_path() == os.path.join(real, ".antikythera", ".ai_env")


class TestEndToEndRedirect:
    def test_service_writes_config_and_env_under_override(self, tmp_path, monkeypatch):
        home = tmp_path / "e2e"
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
        svc = aec.AIEngineConfigService()
        assert svc.config_path == str(home / "ai_config.json")
        svc.save_config()
        assert (home / "ai_config.json").is_file()
        assert json.loads((home / "ai_config.json").read_text())
        assert svc._persistent_env_path() == str(home / ".ai_env")

    def test_explicit_config_path_still_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(tmp_path / "ignored"))
        explicit = tmp_path / "explicit.json"
        svc = aec.AIEngineConfigService(config_path=str(explicit))
        assert svc.config_path == str(explicit)
