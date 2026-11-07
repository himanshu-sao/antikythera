"""O8 / P5-2: ai_config.json is written atomically, a bad file is backed up (not silently ignored),
and the shared default object is never mutated.

Uses tmp_path only. Builds services directly (not the autouse singleton).
"""
import copy
import glob
import json
import logging
import os
import stat

import pytest

import api.services.ai_engine_config as aec
from api.models.config import DEFAULT_AI_ENGINE_CONFIG, AIProvider


@pytest.fixture(autouse=True)
def real_load_and_save(monkeypatch):
    """conftest's autouse fixture stubs the default path; these tests pass explicit paths."""
    yield


def _defaults_snapshot():
    return DEFAULT_AI_ENGINE_CONFIG.model_dump()


def _write(path, text):
    with open(path, "w") as f:
        f.write(text)


def _svc(path):
    return aec.AIEngineConfigService(config_path=str(path))


class TestLoadErrorBackup:
    def test_bad_json_is_backed_up_and_original_kept(self, tmp_path, caplog):
        cfg = tmp_path / "ai_config.json"
        _write(cfg, "{ not json")
        with caplog.at_level(logging.WARNING, logger=aec.logger.name):
            svc = _svc(cfg)
        backups = glob.glob(str(cfg) + ".corrupt-*")
        assert len(backups) == 1
        assert open(backups[0]).read() == "{ not json"
        assert open(cfg).read() == "{ not json"
        assert svc.config.default_provider == AIProvider.OLLAMA

    def test_warning_names_the_file(self, tmp_path, caplog):
        cfg = tmp_path / "ai_config.json"
        _write(cfg, "[]")  # valid JSON, invalid shape for AIEngineConfig(**data)
        with caplog.at_level(logging.WARNING, logger=aec.logger.name):
            _svc(cfg)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "a load error must log a WARNING"
        assert str(cfg) in " ".join(r.getMessage() for r in warnings)

    def test_wrong_shape_object_is_backed_up(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        _write(cfg, json.dumps({"default_provider": "no-such-provider"}))
        _svc(cfg)
        assert len(glob.glob(str(cfg) + ".corrupt-*")) == 1

    def test_identical_bad_content_reuses_backup(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        _write(cfg, "garbage")
        _svc(cfg)
        _svc(cfg)
        assert len(glob.glob(str(cfg) + ".corrupt-*")) == 1

    def test_missing_file_is_not_a_backup_case(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(cfg)
        assert glob.glob(str(cfg) + ".corrupt-*") == []
        assert svc.config.default_model_id == DEFAULT_AI_ENGINE_CONFIG.default_model_id

    def test_valid_file_loads_without_backup(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(tmp_path / "other.json")
        svc.config.default_model_id = svc.config.default_model_id  # no-op
        svc.config_path = str(cfg)
        svc.save_config()
        _svc(cfg)
        assert glob.glob(str(cfg) + ".corrupt-*") == []


class TestDefaultsNeverMutated:
    def test_load_error_uses_a_copy_not_the_shared_object(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        _write(cfg, "{bad")
        svc = _svc(cfg)
        assert svc.config is not DEFAULT_AI_ENGINE_CONFIG

    def test_mutating_after_load_error_leaves_defaults_alone(self, tmp_path):
        before = _defaults_snapshot()
        cfg = tmp_path / "ai_config.json"
        _write(cfg, "{bad")
        svc = _svc(cfg)
        svc.config.default_model_id = "something-else"
        svc.config.models.pop(next(iter(svc.config.models)))
        svc.config.enable_caching = not svc.config.enable_caching
        assert _defaults_snapshot() == before

    def test_set_default_model_after_error_does_not_touch_defaults(self, tmp_path):
        before = _defaults_snapshot()
        cfg = tmp_path / "ai_config.json"
        _write(cfg, "{bad")
        svc = _svc(cfg)
        target = next(m for m in svc.config.models if m != svc.config.default_model_id)
        svc.set_default_model(target)
        assert _defaults_snapshot() == before

    def test_two_services_after_errors_are_independent(self, tmp_path):
        cfg1 = tmp_path / "a" / "ai_config.json"
        cfg2 = tmp_path / "b" / "ai_config.json"
        for p in (cfg1, cfg2):
            p.parent.mkdir()
            _write(p, "{bad")
        s1, s2 = _svc(cfg1), _svc(cfg2)
        s1.config.default_model_id = "changed-by-one"
        assert s2.config.default_model_id != "changed-by-one"
        assert s1.config is not s2.config

    def test_defaults_intact_after_a_normal_load(self, tmp_path):
        before = _defaults_snapshot()
        svc = _svc(tmp_path / "missing.json")
        svc.config.default_model_id = "other"
        assert _defaults_snapshot() == before


class TestAtomicSave:
    def test_save_writes_valid_json_and_leaves_no_temp_files(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(cfg)
        svc.save_config()
        assert json.loads(open(cfg).read())["default_provider"]
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp") or p.startswith(".ai_config")]
        assert leftovers == []

    def test_failed_write_keeps_previous_file_intact(self, tmp_path, monkeypatch):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(cfg)
        svc.save_config()
        before = open(cfg).read()

        def boom(*a, **k):
            raise OSError("disk full")
        monkeypatch.setattr(aec.os, "fsync", boom)
        with pytest.raises(aec.AIEngineConfigError):
            svc.save_config()
        assert open(cfg).read() == before
        assert [p for p in os.listdir(tmp_path) if p.startswith(".ai_config")] == []

    def test_replace_is_used_for_the_swap(self, tmp_path, monkeypatch):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(cfg)
        calls = []
        real_replace = os.replace

        def spy(src, dst):
            calls.append((os.path.dirname(src), dst))
            return real_replace(src, dst)
        monkeypatch.setattr(aec.os, "replace", spy)
        svc.save_config()
        assert calls and calls[0][1] == str(cfg)
        assert calls[0][0] == str(tmp_path)  # temp file is in the same directory

    def test_default_mode_is_0644_for_new_file(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        _svc(cfg).save_config()
        assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o644

    def test_existing_mode_is_preserved(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        _svc(cfg).save_config()
        os.chmod(cfg, 0o600)
        svc = _svc(cfg)
        svc.set_default_model(next(iter(svc.config.models)))
        assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o600

    def test_round_trip_keeps_changes(self, tmp_path):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(cfg)
        target = next(m for m in svc.config.models if m != svc.config.default_model_id)
        svc.set_default_model(target)
        again = _svc(cfg)
        assert again.config.default_model_id == target

    def test_save_error_is_raised_as_config_error(self, tmp_path, monkeypatch):
        cfg = tmp_path / "ai_config.json"
        svc = _svc(cfg)
        monkeypatch.setattr(aec.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
        with pytest.raises(aec.AIEngineConfigError):
            svc.save_config()
