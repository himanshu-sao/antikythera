"""Concurrency and persistence-safety tests for the JSON state managers.

Covers:
- 2.11 / T9 lost update: read-modify-write on a shared file must not drop
  concurrent writes to other keys (``BaseJSONManager._update``).
- 2.16 (managers part): corrupt JSON files raise ``CorruptStateError`` and are
  backed up, never silently replaced by an empty state.

Everything lives under pytest's ``tmp_path``. No network, no real data.
"""
import json
import os
import threading

import pytest

from api.managers.base import BaseJSONManager, CorruptStateError
from api.managers.binding_manager import BindingManager
from api.managers.kanban_state_manager import KanbanStateManager
from api.managers.run_manager import RunManager
from api.managers.template_manager import TemplateManager


def _run_pair(fn_a, fn_b):
    """Run two callables on threads, released together by a barrier."""
    barrier = threading.Barrier(2)
    errors = []

    def wrap(fn):
        def inner():
            try:
                barrier.wait(timeout=10)
                fn()
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)
        return inner

    threads = [threading.Thread(target=wrap(fn_a)), threading.Thread(target=wrap(fn_b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors


# ---------------------------------------------------------------------------
# Lost update (2.11)
# ---------------------------------------------------------------------------

class TestRunManagerLostUpdate:
    def test_concurrent_updates_to_different_keys_both_survive(self, tmp_path):
        rm = RunManager(str(tmp_path))
        rm.create_run("R1", {"status": "RUNNING", "context": {}})

        # Make each load yield the GIL first so the two read-modify-write
        # cycles overlap; with the old split lock, one update would be lost.
        real_load = rm._load

        def slow_load():
            data = real_load()
            threading.Event().wait(0.05)
            return data

        rm._load = slow_load

        _run_pair(
            lambda: rm.update_run("R1", {"current_step_index": 3}),
            lambda: rm.update_run("R1", {"last_note": "from-b"}),
        )

        run = RunManager(str(tmp_path)).get_run("R1")
        assert run["current_step_index"] == 3
        assert run["last_note"] == "from-b"
        assert run["status"] == "RUNNING"

    def test_concurrent_updates_to_different_runs_both_survive(self, tmp_path):
        rm = RunManager(str(tmp_path))
        rm.create_run("A", {"status": "RUNNING"})
        rm.create_run("B", {"status": "RUNNING"})
        _run_pair(
            lambda: rm.update_run("A", {"status": "COMPLETED"}),
            lambda: rm.update_run("B", {"status": "FAILED"}),
        )
        fresh = RunManager(str(tmp_path))
        assert fresh.get_run("A")["status"] == "COMPLETED"
        assert fresh.get_run("B")["status"] == "FAILED"

    def test_concurrent_creates_both_survive(self, tmp_path):
        rm = RunManager(str(tmp_path))
        _run_pair(
            lambda: rm.create_run("X", {"status": "RUNNING"}),
            lambda: rm.create_run("Y", {"status": "RUNNING"}),
        )
        fresh = RunManager(str(tmp_path))
        assert fresh.get_run("X") is not None
        assert fresh.get_run("Y") is not None

    def test_update_missing_run_returns_false_and_writes_nothing(self, tmp_path):
        rm = RunManager(str(tmp_path))
        rm.create_run("R1", {"status": "RUNNING"})
        before = open(rm.path).read()
        assert rm.update_run("NOPE", {"status": "X"}) is False
        assert open(rm.path).read() == before


class TestUpdateHelper:
    def test_update_helper_saves_only_when_changed(self, tmp_path):
        m = BaseJSONManager(str(tmp_path), "thing.json")
        m._save({"a": 1})
        calls = []
        real_save = m._save

        def counting_save(data):
            calls.append(data)
            real_save(data)

        m._save = counting_save
        assert m._update(lambda d: (False, "noop")) == "noop"
        assert calls == []
        assert m._update(lambda d: (True, "wrote")) == "wrote"
        assert len(calls) == 1
        assert m._load() == {"a": 1}

    def test_update_helper_applies_fn_to_loaded_state(self, tmp_path):
        m = BaseJSONManager(str(tmp_path), "thing.json")
        m._save({"a": 1})

        def apply(d):
            d["b"] = d["a"] + 1
            return True, d["b"]

        assert m._update(apply) == 2
        assert m._load() == {"a": 1, "b": 2}

    def test_update_helper_runs_under_one_lock_acquisition(self, tmp_path):
        m = BaseJSONManager(str(tmp_path), "thing.json")
        m._save({})
        observed = []

        def apply(d):
            # Reentrant acquisition from inside fn must not deadlock, and the
            # lock must still be held for the whole read-modify-write.
            observed.append(m.lock.is_locked)
            d["k"] = 1
            return True, None

        m._update(apply)
        assert observed == [True]
        assert m._load() == {"k": 1}

    def test_update_helper_propagates_exceptions_without_saving(self, tmp_path):
        m = BaseJSONManager(str(tmp_path), "thing.json")
        m._save({"a": 1})

        def boom(d):
            d["a"] = 999
            raise RuntimeError("fail mid-update")

        with pytest.raises(RuntimeError):
            m._update(boom)
        assert m._load() == {"a": 1}


class TestOtherManagersReadModifyWrite:
    def test_binding_ids_are_unique_within_same_millisecond(self, tmp_path, monkeypatch):
        import api.managers.binding_manager as bm

        class FrozenDatetime:
            @staticmethod
            def utcnow():
                from datetime import datetime
                return datetime(2026, 1, 1, 12, 0, 0)

        monkeypatch.setattr(bm, "datetime", FrozenDatetime)
        bmgr = BindingManager(str(tmp_path))
        assert bmgr.bind_run_to_item("R1", "id-1") is True
        assert bmgr.bind_run_to_item("R2", "id-2") is True
        data = json.load(open(bmgr.path))
        assert len(data) == 2
        assert {b["run_id"] for b in data.values()} == {"R1", "R2"}

    def test_template_delete_and_save_round_trip(self, tmp_path):
        tm = TemplateManager(str(tmp_path))
        assert tm.save_template("T1", {"name": "one", "steps": []}) is True
        assert tm.save_template("T2", {"name": "two", "steps": []}) is True
        assert tm.delete_template("T1") is True
        assert tm.delete_template("T1") is False
        assert [t["id"] for t in TemplateManager(str(tmp_path)).list_templates()] == ["T2"]

    def test_kanban_concurrent_item_creates_both_survive(self, tmp_path):
        km = KanbanStateManager(str(tmp_path))
        _run_pair(
            lambda: km.create_item("C-1", "one"),
            lambda: km.create_item("C-2", "two"),
        )
        items = KanbanStateManager(str(tmp_path)).load_state()["items"]
        assert set(items) == {"C-1", "C-2"}


# ---------------------------------------------------------------------------
# Corrupt state files (2.16, managers part)
# ---------------------------------------------------------------------------

BAD_JSON = '{"runs": {"R1": {"status": "RUNNING"'  # truncated on purpose


def _backups(path):
    d, base = os.path.dirname(path), os.path.basename(path)
    return sorted(n for n in os.listdir(d) if n.startswith(base + ".corrupt-"))


class TestCorruptFiles:
    def test_missing_file_returns_empty_default(self, tmp_path):
        m = BaseJSONManager(str(tmp_path), "x.json")
        assert m._load() == {}
        assert _backups(m.path) == []

    def test_missing_pipeline_state_returns_default_stages(self, tmp_path):
        km = KanbanStateManager(str(tmp_path))
        state = km.load_state()
        assert state["items"] == {}
        assert "INTAKE" in state["stages"]
        assert _backups(km.path) == []

    def test_corrupt_file_raises_and_is_backed_up(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text(BAD_JSON)
        m = BaseJSONManager(str(tmp_path), "x.json")
        with pytest.raises(CorruptStateError) as info:
            m._load()
        backups = _backups(str(path))
        assert len(backups) == 1
        assert info.value.backup_path == os.path.join(str(tmp_path), backups[0])
        assert open(os.path.join(str(tmp_path), backups[0])).read() == BAD_JSON

    def test_corrupt_file_is_not_overwritten_by_next_save(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text(BAD_JSON)
        m = BaseJSONManager(str(tmp_path), "x.json")
        with pytest.raises(CorruptStateError):
            m._update(lambda d: (True, None))
        # Original left in place, so no write clobbered it.
        assert path.read_text() == BAD_JSON

    def test_backup_filename_has_utc_timestamp(self, tmp_path):
        import re
        path = tmp_path / "x.json"
        path.write_text(BAD_JSON)
        with pytest.raises(CorruptStateError):
            BaseJSONManager(str(tmp_path), "x.json")._load()
        (name,) = _backups(str(path))
        assert re.fullmatch(r"x\.json\.corrupt-\d{8}T\d{6}\d{6}Z(-\d+)?", name), name

    def test_repeated_reads_of_same_corrupt_file_reuse_one_backup(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text(BAD_JSON)
        m = BaseJSONManager(str(tmp_path), "x.json")
        for _ in range(3):
            with pytest.raises(CorruptStateError):
                m._load()
        assert len(_backups(str(path))) == 1

    def test_changed_corrupt_content_gets_a_new_backup(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text(BAD_JSON)
        m = BaseJSONManager(str(tmp_path), "x.json")
        with pytest.raises(CorruptStateError):
            m._load()
        path.write_text('{"other": ')
        with pytest.raises(CorruptStateError):
            m._load()
        assert len(_backups(str(path))) == 2

    def test_kanban_corrupt_file_raises_not_empty_state(self, tmp_path):
        path = tmp_path / "pipeline-state.json"
        path.write_text("not json at all")
        km = KanbanStateManager(str(tmp_path))
        with pytest.raises(CorruptStateError):
            km.load_state()
        with pytest.raises(CorruptStateError):
            km.create_item("K-1", "should not overwrite")
        assert path.read_text() == "not json at all"
        assert len(_backups(str(path))) == 1

    def test_run_manager_corrupt_file_surfaces_error_on_write(self, tmp_path):
        path = tmp_path / "workflow_runs.json"
        path.write_text(BAD_JSON)
        rm = RunManager(str(tmp_path))
        with pytest.raises(CorruptStateError):
            rm.create_run("R9", {"status": "RUNNING"})
        assert path.read_text() == BAD_JSON

    def test_corrupt_file_with_invalid_utf8_is_backed_up(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_bytes(b"\xff\xfe\x00garbage")
        with pytest.raises(CorruptStateError):
            BaseJSONManager(str(tmp_path), "x.json")._load()
        assert len(_backups(str(path))) == 1


# ---------------------------------------------------------------------------
# W3: non-object roots, bad UTF-8, error propagation, public_message
# ---------------------------------------------------------------------------

class TestNonObjectRootIsCorrupt:
    @pytest.mark.parametrize("payload", ["[]", "[1, 2, 3]", '"just a string"', "42", "null", "true"])
    def test_base_load_quarantines_non_dict_root(self, tmp_path, payload):
        path = tmp_path / "x.json"
        path.write_text(payload)
        m = BaseJSONManager(str(tmp_path), "x.json")
        with pytest.raises(CorruptStateError) as info:
            m._load()
        # The file is left in place and a backup with the same bytes exists.
        assert path.read_text() == payload
        (name,) = _backups(str(path))
        assert open(os.path.join(str(tmp_path), name)).read() == payload
        assert "expected a JSON object" in str(info.value)

    def test_non_dict_root_is_not_overwritten_by_update(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text("[1, 2]")
        m = BaseJSONManager(str(tmp_path), "x.json")
        with pytest.raises(CorruptStateError):
            m._update(lambda d: (True, None))
        assert path.read_text() == "[1, 2]"

    def test_empty_object_is_valid(self, tmp_path):
        (tmp_path / "x.json").write_text("{}")
        assert BaseJSONManager(str(tmp_path), "x.json")._load() == {}
        assert _backups(str(tmp_path / "x.json")) == []

    def test_invalid_utf8_raises_corrupt_not_unicode_error(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_bytes(b'{"a": "\xff\xfe"}')
        with pytest.raises(CorruptStateError):
            BaseJSONManager(str(tmp_path), "x.json")._load()
        assert len(_backups(str(path))) == 1

    @pytest.mark.parametrize("payload", ["[]", '"s"', "7"])
    def test_kanban_load_state_quarantines_non_dict_root(self, tmp_path, payload):
        path = tmp_path / "pipeline-state.json"
        path.write_text(payload)
        km = KanbanStateManager(str(tmp_path))
        with pytest.raises(CorruptStateError):
            km.load_state()
        with pytest.raises(CorruptStateError):
            km.create_item("K-1", "must not overwrite")
        assert path.read_text() == payload
        assert len(_backups(str(path))) == 1

    def test_kanban_load_state_invalid_utf8(self, tmp_path):
        path = tmp_path / "pipeline-state.json"
        path.write_bytes(b"\xff\xfe\x00")
        with pytest.raises(CorruptStateError):
            KanbanStateManager(str(tmp_path)).load_state()
        assert len(_backups(str(path))) == 1

    def test_run_and_binding_managers_reject_list_root(self, tmp_path):
        (tmp_path / "workflow_runs.json").write_text("[]")
        (tmp_path / "workflow_bindings.json").write_text("[]")
        with pytest.raises(CorruptStateError):
            RunManager(str(tmp_path)).get_run("R1")
        with pytest.raises(CorruptStateError):
            BindingManager(str(tmp_path)).get_run_id_for_item("I-1")


class TestWritesPropagateErrors:
    def test_create_run_propagates_corrupt_state(self, tmp_path):
        (tmp_path / "workflow_runs.json").write_text(BAD_JSON)
        with pytest.raises(CorruptStateError):
            RunManager(str(tmp_path)).create_run("R1", {"status": "RUNNING"})

    def test_create_run_propagates_oserror_instead_of_returning_false(self, tmp_path, monkeypatch):
        rm = RunManager(str(tmp_path))

        def boom(data):
            raise OSError("disk full")

        monkeypatch.setattr(rm, "_save", boom)
        with pytest.raises(OSError):
            rm.create_run("R1", {"status": "RUNNING"})

    def test_create_run_still_returns_true_on_success(self, tmp_path):
        rm = RunManager(str(tmp_path))
        assert rm.create_run("R1", {"status": "RUNNING"}) is True
        assert rm.get_run("R1")["status"] == "RUNNING"

    def test_bind_run_to_item_propagates_corrupt_state(self, tmp_path):
        (tmp_path / "workflow_bindings.json").write_text(BAD_JSON)
        with pytest.raises(CorruptStateError):
            BindingManager(str(tmp_path)).bind_run_to_item("R1", "i-1")
        assert (tmp_path / "workflow_bindings.json").read_text() == BAD_JSON

    def test_bind_run_to_item_propagates_oserror(self, tmp_path, monkeypatch):
        bm = BindingManager(str(tmp_path))
        monkeypatch.setattr(bm, "_save", lambda data: (_ for _ in ()).throw(OSError("ro fs")))
        with pytest.raises(OSError):
            bm.bind_run_to_item("R1", "i-1")

    def test_bind_run_to_item_still_returns_true_and_uppercases(self, tmp_path):
        bm = BindingManager(str(tmp_path))
        assert bm.bind_run_to_item("R1", "i-1") is True
        assert bm.get_run_id_for_item("I-1") == "R1"

    def test_facade_create_run_and_bind_propagate_corrupt(self, tmp_path):
        from api.workflow_state_manager import WorkflowStateManager
        sm = WorkflowStateManager(str(tmp_path))
        (tmp_path / "workflow_runs.json").write_text(BAD_JSON)
        (tmp_path / "workflow_bindings.json").write_text(BAD_JSON)
        with pytest.raises(CorruptStateError):
            sm.create_run("R1", {"status": "RUNNING"})
        with pytest.raises(CorruptStateError):
            sm.bind_run_to_item("R1", "I-1")


class TestPublicMessage:
    def test_corrupt_error_message_has_no_path(self, tmp_path):
        from api.managers.base import public_message
        path = tmp_path / "x.json"
        path.write_text(BAD_JSON)
        with pytest.raises(CorruptStateError) as info:
            BaseJSONManager(str(tmp_path), "x.json")._load()
        # The full message names the path; the public one must not.
        assert str(tmp_path) in str(info.value)
        msg = public_message(info.value)
        assert str(tmp_path) not in msg
        assert "x.json" not in msg
        assert "/" not in msg
        assert "corrupt" in msg.lower()
        assert "backup" in msg.lower()

    def test_other_exceptions_pass_through(self):
        from api.managers.base import public_message
        assert public_message(ValueError("plain")) == "plain"
