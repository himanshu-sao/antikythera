"""D14 backend: settings store (``settings.json``), ``/api/settings`` router, consumers.

Every test points ``ANTIKYTHERA_HOME`` at ``tmp_path`` so nothing touches the
real ``~/.antikythera``. The autouse ``bypass_api_token`` conftest fixture
overrides the token dependency; the auth tests clear that override to exercise
the real ``require_token``.
"""
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import settings_store as store
from api.settings_store import (
    SCHEMA,
    SettingsValidationError,
    effective_settings,
    get_setting,
    save_settings,
    settings_path,
    validate_settings,
)

DEFAULTS = {
    "orchestrator_interval_s": 30,
    "retry_delays_min": [5, 10, 15],
    "poison_strikes": 3,
    "reap_age_s": 3600,
    "bob_timeout_s": 120,
    "max_tasks": 6,
    "digest_interval_h": 6,
    "studio_undefined_queue_cap": 100,
    "studio_max_run_logs": 50,
}


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated ANTIKYTHERA_HOME for one test; returns its path."""
    d = tmp_path / "ak-home"
    d.mkdir()
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(d))
    return d


def _write_file(home, payload):
    (home / "settings.json").write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------- defaults

class TestDefaults:
    def test_absent_file_yields_todays_defaults(self, home):
        assert not (home / "settings.json").exists()
        for key, value in DEFAULTS.items():
            assert get_setting(key) == value

    def test_defaults_match_schema(self):
        assert {k: s.default for k, s in SCHEMA.items()} == DEFAULTS

    def test_absent_file_does_not_create_it(self, home):
        get_setting("poison_strikes")
        effective_settings()
        assert not (home / "settings.json").exists()

    def test_config_dir_honours_antikythera_home(self, home):
        assert store.config_dir() == home
        assert settings_path() == home / "settings.json"

    def test_config_dir_default_is_home_dot_antikythera(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ANTIKYTHERA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert store.config_dir() == tmp_path / ".antikythera"

    def test_get_setting_returns_stored_value(self, home):
        _write_file(home, {"poison_strikes": 7})
        assert get_setting("poison_strikes") == 7
        assert get_setting("max_tasks") == 6  # untouched key keeps its default

    def test_get_setting_returns_a_copy_of_list_defaults(self, home):
        first = get_setting("retry_delays_min")
        first.append(999)
        assert get_setting("retry_delays_min") == [5, 10, 15]

    def test_unknown_key_raises_key_error(self, home):
        with pytest.raises(KeyError):
            get_setting("not_a_setting")

    def test_corrupt_file_falls_back_to_defaults(self, home):
        (home / "settings.json").write_text("{not json", encoding="utf-8")
        assert get_setting("poison_strikes") == 3

    def test_non_object_file_falls_back_to_defaults(self, home):
        (home / "settings.json").write_text("[1, 2]", encoding="utf-8")
        assert get_setting("poison_strikes") == 3

    def test_invalid_stored_value_is_ignored_not_fatal(self, home):
        _write_file(home, {"poison_strikes": 999, "max_tasks": 4})
        assert get_setting("poison_strikes") == 3
        assert get_setting("max_tasks") == 4

    def test_unknown_stored_key_is_ignored(self, home):
        _write_file(home, {"mystery": 1, "max_tasks": 4})
        assert get_setting("max_tasks") == 4


# -------------------------------------------------------------------- validation

class TestBoundsValidation:
    @pytest.mark.parametrize(
        "key,low,high",
        [
            ("orchestrator_interval_s", 5, 3600),
            ("poison_strikes", 1, 10),
            ("reap_age_s", 0, 86400),
            ("bob_timeout_s", 10, 600),
            ("max_tasks", 1, 20),
            ("digest_interval_h", 0.25, 24),
            ("studio_undefined_queue_cap", 1, 1000),
            ("studio_max_run_logs", 1, 1000),
        ],
    )
    def test_bounds_are_inclusive_and_accepted(self, home, key, low, high):
        validate_settings({key: low})
        validate_settings({key: high})

    @pytest.mark.parametrize(
        "key,low,high",
        [
            ("orchestrator_interval_s", 5, 3600),
            ("poison_strikes", 1, 10),
            ("reap_age_s", 0, 86400),
            ("bob_timeout_s", 10, 600),
            ("max_tasks", 1, 20),
            ("digest_interval_h", 0.25, 24),
            ("studio_undefined_queue_cap", 1, 1000),
            ("studio_max_run_logs", 1, 1000),
        ],
    )
    def test_out_of_bounds_rejected_with_clear_message(self, home, key, low, high):
        with pytest.raises(SettingsValidationError) as exc:
            validate_settings({key: high + 1})
        assert key in exc.value.errors
        assert "out of bounds" in exc.value.errors[key]
        with pytest.raises(SettingsValidationError):
            validate_settings({key: low - 1})

    def test_retry_delays_list_bounds(self, home):
        validate_settings({"retry_delays_min": [1]})
        validate_settings({"retry_delays_min": [1440, 1, 1440, 1, 1440]})
        for bad in ([], [1, 2, 3, 4, 5, 6], [0], [1441], [5, "x"], "5,10"):
            with pytest.raises(SettingsValidationError) as exc:
                validate_settings({"retry_delays_min": bad})
            assert "retry_delays_min" in exc.value.errors

    def test_booleans_and_floats_rejected_for_int_settings(self, home):
        for bad in (True, 3.5, "3", [3]):
            with pytest.raises(SettingsValidationError):
                validate_settings({"poison_strikes": bad})

    def test_float_setting_accepts_int_and_float(self, home):
        assert validate_settings({"digest_interval_h": 6}) == {"digest_interval_h": 6}
        assert validate_settings({"digest_interval_h": 0.5}) == {"digest_interval_h": 0.5}

    def test_nan_and_inf_rejected_for_float(self, home):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(SettingsValidationError):
                validate_settings({"digest_interval_h": bad})

    def test_unknown_key_rejected(self, home):
        with pytest.raises(SettingsValidationError) as exc:
            validate_settings({"no_such_setting": 1})
        assert exc.value.errors == {"no_such_setting": "unknown setting"}

    def test_every_problem_reported_together(self, home):
        with pytest.raises(SettingsValidationError) as exc:
            validate_settings({"poison_strikes": 0, "bogus": 1, "max_tasks": 2})
        assert set(exc.value.errors) == {"poison_strikes", "bogus"}

    def test_non_object_body_rejected(self, home):
        with pytest.raises(SettingsValidationError):
            validate_settings(["poison_strikes", 3])

    def test_null_is_accepted_as_reset(self, home):
        assert validate_settings({"poison_strikes": None}) == {"poison_strikes": None}


class TestSaveRejectsWithoutWriting:
    def test_unknown_key_rejected_on_save_and_nothing_written(self, home):
        with pytest.raises(SettingsValidationError):
            save_settings({"poison_strikes": 4, "bogus": 1})
        assert not (home / "settings.json").exists()

    def test_out_of_bounds_on_save_leaves_existing_file_unchanged(self, home):
        _write_file(home, {"poison_strikes": 4})
        before = (home / "settings.json").read_bytes()
        with pytest.raises(SettingsValidationError):
            save_settings({"poison_strikes": 99})
        assert (home / "settings.json").read_bytes() == before


# ---------------------------------------------------------------- write semantics

class TestAtomicSave:
    def test_save_writes_only_overrides(self, home):
        save_settings({"poison_strikes": 5})
        on_disk = json.loads((home / "settings.json").read_text())
        assert on_disk == {"poison_strikes": 5}

    def test_save_merges_with_existing_overrides(self, home):
        save_settings({"poison_strikes": 5})
        save_settings({"max_tasks": 9})
        on_disk = json.loads((home / "settings.json").read_text())
        assert on_disk == {"poison_strikes": 5, "max_tasks": 9}

    def test_null_removes_override(self, home):
        save_settings({"poison_strikes": 5, "max_tasks": 9})
        save_settings({"poison_strikes": None})
        on_disk = json.loads((home / "settings.json").read_text())
        assert on_disk == {"max_tasks": 9}
        assert get_setting("poison_strikes") == 3

    def test_file_mode_is_0600(self, home):
        save_settings({"poison_strikes": 5})
        mode = stat.S_IMODE(os.stat(home / "settings.json").st_mode)
        assert mode == 0o600

    def test_mode_is_0600_after_overwrite_too(self, home):
        save_settings({"poison_strikes": 5})
        os.chmod(home / "settings.json", 0o644)  # loosen, then a save must tighten again
        save_settings({"poison_strikes": 6})
        assert stat.S_IMODE(os.stat(home / "settings.json").st_mode) == 0o600

    def test_no_temp_file_left_behind(self, home):
        save_settings({"poison_strikes": 5})
        leftovers = [p.name for p in home.iterdir() if p.name.startswith(".settings.")]
        assert leftovers == []

    def test_failed_write_preserves_previous_file(self, home):
        save_settings({"poison_strikes": 5})
        before = (home / "settings.json").read_bytes()
        with patch("api.settings_store.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                save_settings({"poison_strikes": 6})
        assert (home / "settings.json").read_bytes() == before
        leftovers = [p.name for p in home.iterdir() if p.name.startswith(".settings.")]
        assert leftovers == []

    def test_save_creates_missing_config_dir(self, tmp_path, monkeypatch):
        target = tmp_path / "nested" / "home"
        monkeypatch.setenv("ANTIKYTHERA_HOME", str(target))
        save_settings({"max_tasks": 4})
        assert (target / "settings.json").exists()
        assert stat.S_IMODE(os.stat(target / "settings.json").st_mode) == 0o600

    def test_save_returns_effective_values(self, home):
        out = save_settings({"max_tasks": 4})
        assert out["max_tasks"]["value"] == 4
        assert out["max_tasks"]["source"] == "settings.json"
        assert out["poison_strikes"]["value"] == 3
        assert out["poison_strikes"]["source"] == "default"

    def test_save_is_seen_by_get_setting_immediately(self, home):
        assert get_setting("max_tasks") == 6
        save_settings({"max_tasks": 11})
        assert get_setting("max_tasks") == 11


# ------------------------------------------------------------------ effective view

class TestEffectiveSettings:
    def test_every_key_has_the_documented_shape(self, home):
        eff = effective_settings()
        assert set(eff) == set(DEFAULTS)
        for key, entry in eff.items():
            for field in ("value", "default", "type", "bounds", "source",
                          "restart_required", "description", "consumer", "wired"):
                assert field in entry, (key, field)

    def test_defaults_and_source_without_file(self, home):
        eff = effective_settings()
        for key, value in DEFAULTS.items():
            assert eff[key]["value"] == value
            assert eff[key]["default"] == value
            assert eff[key]["source"] == "default"

    def test_source_reports_settings_json_for_overridden_key(self, home):
        _write_file(home, {"max_tasks": 4})
        eff = effective_settings()
        assert eff["max_tasks"]["source"] == "settings.json"
        assert eff["max_tasks"]["value"] == 4
        assert eff["max_tasks"]["default"] == 6
        assert eff["poison_strikes"]["source"] == "default"

    def test_bounds_shape_for_scalar_and_list(self, home):
        eff = effective_settings()
        assert eff["poison_strikes"]["bounds"] == {"min": 1, "max": 10}
        assert eff["retry_delays_min"]["bounds"] == {
            "min_items": 1, "max_items": 5, "item_min": 1, "item_max": 1440,
        }

    def test_restart_required_flags_match_consumers(self, home):
        eff = effective_settings()
        # Read per call by a consumer, so no restart needed.
        for key in ("retry_delays_min", "poison_strikes", "reap_age_s",
                    "bob_timeout_s", "max_tasks", "studio_undefined_queue_cap",
                    "studio_max_run_logs"):
            assert eff[key]["restart_required"] is False, key
        # Read once at process start (or not wired yet, so a change needs a restart).
        for key in ("orchestrator_interval_s", "digest_interval_h"):
            assert eff[key]["restart_required"] is True, key

    def test_unwired_settings_are_marked(self, home):
        eff = effective_settings()
        assert eff["orchestrator_interval_s"]["wired"] is False
        assert eff["digest_interval_h"]["wired"] is False
        assert eff["studio_undefined_queue_cap"]["wired"] is False
        assert eff["studio_max_run_logs"]["wired"] is False
        assert eff["max_tasks"]["wired"] is True
        assert eff["retry_delays_min"]["wired"] is True
        assert eff["poison_strikes"]["wired"] is True
        assert eff["reap_age_s"]["wired"] is True
        assert eff["bob_timeout_s"]["wired"] is True


# ----------------------------------------------------------------------- router

@pytest.fixture
def client(home):
    from api.main import app
    return TestClient(app)


class TestRouterShapes:
    def test_get_returns_every_setting(self, client):
        res = client.get("/api/settings")
        assert res.status_code == 200
        body = res.json()
        assert set(body["settings"]) == set(DEFAULTS)
        entry = body["settings"]["max_tasks"]
        assert entry["value"] == 6
        assert entry["default"] == 6
        assert entry["bounds"] == {"min": 1, "max": 20}
        assert entry["source"] == "default"
        assert entry["restart_required"] is False

    def test_patch_partial_body_returns_new_effective_values(self, client, home):
        res = client.patch("/api/settings", json={"max_tasks": 4})
        assert res.status_code == 200
        settings = res.json()["settings"]
        assert settings["max_tasks"]["value"] == 4
        assert settings["max_tasks"]["source"] == "settings.json"
        assert settings["poison_strikes"]["value"] == 3
        assert json.loads((home / "settings.json").read_text()) == {"max_tasks": 4}

    def test_patch_null_resets_to_default(self, client, home):
        client.patch("/api/settings", json={"max_tasks": 4})
        res = client.patch("/api/settings", json={"max_tasks": None})
        assert res.json()["settings"]["max_tasks"]["value"] == 6
        assert res.json()["settings"]["max_tasks"]["source"] == "default"

    def test_patch_out_of_bounds_is_422_and_writes_nothing(self, client, home):
        res = client.patch("/api/settings", json={"poison_strikes": 11})
        assert res.status_code == 422
        errors = res.json()["detail"]["errors"]
        assert "poison_strikes" in errors
        assert not (home / "settings.json").exists()

    def test_patch_unknown_key_is_422(self, client, home):
        res = client.patch("/api/settings", json={"bogus": 1})
        assert res.status_code == 422
        assert res.json()["detail"]["errors"] == {"bogus": "unknown setting"}
        assert not (home / "settings.json").exists()

    def test_patch_non_object_body_is_422(self, client, home):
        res = client.patch("/api/settings", json=[1, 2])
        assert res.status_code == 422

    def test_patch_retry_delays_list(self, client, home):
        res = client.patch("/api/settings", json={"retry_delays_min": [2, 4]})
        assert res.status_code == 200
        assert res.json()["settings"]["retry_delays_min"]["value"] == [2, 4]
        assert get_setting("retry_delays_min") == [2, 4]

    def test_get_after_patch_reflects_change(self, client, home):
        client.patch("/api/settings", json={"bob_timeout_s": 300})
        body = client.get("/api/settings").json()
        assert body["settings"]["bob_timeout_s"]["value"] == 300
        assert body["settings"]["bob_timeout_s"]["source"] == "settings.json"

    def test_no_secret_fields_are_exposed(self, client):
        body = client.get("/api/settings").json()
        assert "slack_webhook" not in body["settings"]
        assert "api_token" not in json.dumps(body).lower()


class TestRouterRequiresToken:
    """With the conftest bypass removed, the real require_token guards the router."""

    @pytest.fixture
    def real_auth(self, monkeypatch):
        from api.main import app
        from api.security import require_token
        monkeypatch.setenv("ANTIKYTHERA_API_TOKEN", "settings-test-token")
        app.dependency_overrides.pop(require_token, None)
        yield  # bypass_api_token's teardown pops the (already absent) override

    def test_get_without_token_is_401(self, real_auth, home):
        from api.main import app
        res = TestClient(app).get("/api/settings")
        assert res.status_code == 401

    def test_patch_without_token_is_401_and_writes_nothing(self, real_auth, home):
        from api.main import app
        res = TestClient(app).patch("/api/settings", json={"max_tasks": 4})
        assert res.status_code == 401
        assert not (home / "settings.json").exists()

    def test_wrong_token_is_401(self, real_auth, home):
        from api.main import app
        res = TestClient(app).get(
            "/api/settings", headers={"Authorization": "Bearer nope"}
        )
        assert res.status_code == 401

    def test_correct_token_is_200(self, real_auth, home):
        from api.main import app
        res = TestClient(app).get(
            "/api/settings",
            headers={"Authorization": "Bearer settings-test-token"},
        )
        assert res.status_code == 200
        assert "settings" in res.json()


# -------------------------------------------------------------------- consumers

class TestRetryManagerHonoursSetting:
    def _manager_and_run(self, home, retry_count):
        from api.retry_manager import RetryManager
        run = {"status": "RUNNING", "retry_count": retry_count}

        class _SM:
            def get_run(self, run_id):
                return run

        return RetryManager(_SM())

    def test_default_delays_when_absent(self, home):
        mgr = self._manager_and_run(home, 0)
        assert mgr.should_retry("r") == 5

    def test_changed_delays_are_honoured(self, home):
        save_settings({"retry_delays_min": [2, 4, 8, 16]})
        assert self._manager_and_run(home, 0).should_retry("r") == 2
        assert self._manager_and_run(home, 3).should_retry("r") == 16
        # Exhausted after four entries.
        assert self._manager_and_run(home, 4).should_retry("r") is None

    def test_record_failure_blocks_after_configured_retries(self, home):
        from api.retry_manager import RetryManager

        class _SM:
            def __init__(self):
                self.run = {"status": "RUNNING", "retry_count": 0}
                self.updates = []

            def get_run(self, run_id):
                return dict(self.run)

            def log_event(self, *a, **k):
                pass

            def update_run(self, run_id, updates):
                self.updates.append(updates)
                self.run.update(updates)

        save_settings({"retry_delays_min": [1]})  # one retry allowed
        sm = _SM()
        mgr = RetryManager(sm)
        mgr.record_failure("r", "boom")  # retry_count 1, still <= 1
        assert "status" not in sm.updates[-1]
        sm.run["retry_count"] = 1
        mgr.record_failure("r", "boom")  # retry_count 2 > 1 -> BLOCKED
        assert sm.updates[-1]["status"] == "BLOCKED"


class TestRunManagerReapDefault:
    def test_default_reap_age_is_3600(self, tmp_path, home):
        from api.managers.run_manager import RunManager
        manager = RunManager(str(tmp_path))
        now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
        ts = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        runs = {
            "old": {"status": "RUNNING", "started_at": ts(now - timedelta(seconds=7200))},
            "young": {"status": "RUNNING", "started_at": ts(now - timedelta(seconds=60))},
        }
        with open(manager.path, "w") as f:
            json.dump(runs, f)
        assert manager.reap_stale_runs(now=now) == ["old"]

    def test_changed_reap_age_is_honoured_without_argument(self, tmp_path, home):
        from api.managers.run_manager import RunManager
        manager = RunManager(str(tmp_path))
        now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
        ts = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        runs = {
            "a": {"status": "RUNNING", "started_at": ts(now - timedelta(seconds=120))},
        }
        with open(manager.path, "w") as f:
            json.dump(runs, f)
        save_settings({"reap_age_s": 60})
        assert manager.reap_stale_runs(now=now) == ["a"]

    def test_explicit_argument_still_wins_over_setting(self, tmp_path, home):
        from api.managers.run_manager import RunManager
        manager = RunManager(str(tmp_path))
        now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
        ts = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with open(manager.path, "w") as f:
            json.dump({"a": {"status": "RUNNING", "started_at": ts(now - timedelta(seconds=120))}}, f)
        save_settings({"reap_age_s": 60})
        assert manager.reap_stale_runs(max_age_seconds=3600, now=now) == []
        assert manager.reap_stale_runs(max_age_seconds=0, now=now) == ["a"]


class TestPlannerHonoursMaxTasks:
    def _planner(self, response):
        from agents.executor_planner import ExecutorPlanner

        class _LLM:
            def __init__(self):
                self.system_prompts = []

            def chat(self, system_prompt, user_prompt):
                self.system_prompts.append(system_prompt)
                return response

        llm = _LLM()
        return ExecutorPlanner(llm), llm

    def _tasks(self, n):
        return json.dumps([{"task": f"Create f{i}.py", "type": "file_creation"} for i in range(n)])

    def test_default_cap_is_six(self, home):
        planner, _ = self._planner(self._tasks(9))
        assert len(planner.create_checklist("spec", "arch")) == 6

    def test_changed_cap_truncates_and_prompt_reflects_it(self, home):
        save_settings({"max_tasks": 3})
        planner, llm = self._planner(self._tasks(9))
        out = planner.create_checklist("spec", "arch")
        assert [t["task"] for t in out] == ["Create f0.py", "Create f1.py", "Create f2.py"]
        assert "no more than 3 tasks" in llm.system_prompts[0]
        assert "__MAX_TASKS__" not in llm.system_prompts[0]

    def test_default_prompt_still_says_six(self, home):
        planner, llm = self._planner(self._tasks(2))
        planner.create_checklist("spec", "arch")
        assert "no more than 6 tasks" in llm.system_prompts[0]


class TestBobTimeoutHonoursSetting:
    def _client(self, tmp_path, monkeypatch):
        from agents import llm_client as lc_mod
        monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", "0")
        monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)
        import yaml
        cfg = tmp_path / "config.yaml"
        with open(cfg, "w") as f:
            yaml.safe_dump({"llm": {"provider": "ibm_bob"}}, f)
        return lc_mod, lc_mod.LLMClient(config_path=str(cfg))

    def _capture_timeout(self, lc_mod, client, monkeypatch):
        seen = {}

        class _Done:
            returncode = 0
            stdout = "ok\n"
            stderr = ""

        def fake_run(cmd, *a, **kw):
            seen["timeout"] = kw.get("timeout")
            return _Done()

        monkeypatch.setattr(lc_mod.subprocess, "run", fake_run)
        client.chat("s", "u")
        return seen["timeout"]

    def test_default_timeout_is_120(self, tmp_path, monkeypatch, home):
        lc_mod, client = self._client(tmp_path, monkeypatch)
        assert self._capture_timeout(lc_mod, client, monkeypatch) == 120

    def test_changed_timeout_is_passed_to_subprocess(self, tmp_path, monkeypatch, home):
        save_settings({"bob_timeout_s": 300})
        lc_mod, client = self._client(tmp_path, monkeypatch)
        assert self._capture_timeout(lc_mod, client, monkeypatch) == 300


class TestPoisonStrikesHonoursSetting:
    def _run_failing(self, n):
        from agents import orchestrator
        from agents import state as state_module
        from tests.test_helpers import make_item
        state_module.save_state({
            "last_heartbeat": None,
            "items": {"ID-001": make_item(stage="INTAKE")},
        })
        calls = []
        real = orchestrator.Orchestrator.process_item

        def flaky(self, item, state, item_id):
            calls.append(item_id)
            raise RuntimeError("poison")

        with patch("agents.orchestrator.Orchestrator.process_item", flaky):
            for _ in range(n):
                orchestrator.run_pipeline()
        return calls, state_module.load_state()["items"]["ID-001"]

    def test_default_three_strikes_block(self, home):
        calls, item = self._run_failing(6)
        assert calls == ["ID-001"] * 3
        assert "3 consecutive failures" in item["blocked_reason"]

    def test_changed_strikes_block_at_new_threshold(self, home):
        save_settings({"poison_strikes": 2})
        calls, item = self._run_failing(6)
        assert calls == ["ID-001"] * 2
        assert "2 consecutive failures" in item["blocked_reason"]


class TestStoreReadsFreshFromDisk:
    def test_external_edit_is_seen_without_restart(self, home):
        assert get_setting("max_tasks") == 6
        _write_file(home, {"max_tasks": 9})
        assert get_setting("max_tasks") == 9
        _write_file(home, {"max_tasks": 2})
        assert get_setting("max_tasks") == 2
