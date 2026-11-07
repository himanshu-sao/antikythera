"""P0-2 / R23: agents.state.load_state quarantines corruption; save_state keeps file mode."""

import json
import os
import stat

import pytest

from agents import state
from api.managers.base import CorruptStateError


@pytest.fixture
def target(tmp_path, monkeypatch):
    d = tmp_path / "state-dir"
    d.mkdir()
    path = d / "pipeline-state.json"
    monkeypatch.setattr(state, "STATE_FILE", str(path))
    return path


def _backups(path):
    return sorted(p for p in path.parent.iterdir() if ".corrupt-" in p.name)


def test_missing_file_returns_default(target):
    assert state.load_state() == {"last_heartbeat": None, "items": {}}
    assert _backups(target) == []


def test_valid_file_loads(target):
    target.write_text(json.dumps({"items": {"ID-001": {"title": "x"}}}))
    assert state.load_state()["items"]["ID-001"]["title"] == "x"


def test_corrupt_json_backed_up_and_raises(target):
    target.write_bytes(b'{"items": {')
    with pytest.raises(CorruptStateError) as exc:
        state.load_state()
    backups = _backups(target)
    assert len(backups) == 1
    assert exc.value.backup_path == str(backups[0])
    assert backups[0].read_bytes() == b'{"items": {'
    assert target.read_bytes() == b'{"items": {'  # original untouched
    assert isinstance(exc.value, RuntimeError)


def test_repeated_loads_back_up_once(target):
    target.write_bytes(b"not json at all")
    for _ in range(4):
        with pytest.raises(CorruptStateError):
            state.load_state()
    assert len(_backups(target)) == 1
    assert target.read_bytes() == b"not json at all"


def test_changed_corruption_gets_new_backup(target):
    target.write_bytes(b"bad one")
    with pytest.raises(CorruptStateError):
        state.load_state()
    target.write_bytes(b"bad two")
    with pytest.raises(CorruptStateError):
        state.load_state()
    contents = sorted(p.read_bytes() for p in _backups(target))
    assert contents == [b"bad one", b"bad two"]


@pytest.mark.parametrize("payload", [b"[1, 2]", b'"text"', b"null", b"42"])
def test_non_dict_root_is_corrupt(target, payload):
    target.write_bytes(payload)
    with pytest.raises(CorruptStateError):
        state.load_state()
    assert len(_backups(target)) == 1
    assert target.read_bytes() == payload


def test_bad_utf8_is_corrupt(target):
    payload = b'{"items": {"ID-001": {"title": "\xff\xfe"}}}'
    target.write_bytes(payload)
    with pytest.raises(CorruptStateError):
        state.load_state()
    backups = _backups(target)
    assert len(backups) == 1 and backups[0].read_bytes() == payload
    assert target.read_bytes() == payload


def test_save_state_preserves_existing_mode(target):
    target.write_text(json.dumps({"items": {}}))
    os.chmod(target, 0o640)
    state.save_state({"items": {"ID-001": {}}})
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o640
    assert json.loads(target.read_text())["items"] == {"ID-001": {}}


def test_save_state_new_file_defaults_to_0644(target):
    state.save_state({"items": {}})
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o644


def test_save_state_mode_preserved_across_repeated_saves(target):
    target.write_text("{}")
    os.chmod(target, 0o600)
    state.save_state({"items": {}})
    state.save_state({"items": {"A": {}}})
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
