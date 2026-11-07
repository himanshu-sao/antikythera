"""R7b / P0-2 (hub part): bad UTF-8 and non-object roots are corrupt, exactly like invalid JSON.

The file is copied to ``<file>.corrupt-<UTC>`` (identical copies are reused), the original
is left untouched, and IntegrationConfigCorruptError is raised instead of a raw
UnicodeDecodeError.
"""
import glob
import json

import pytest

from api.integration_hub import IntegrationConfigCorruptError, IntegrationHub

BAD_UTF8 = b'{"a": "\xff\xfe\xfa"}'


def _hub_with(tmp_path, payload: bytes) -> IntegrationHub:
    hub = IntegrationHub(str(tmp_path))
    with open(hub.config_path, "wb") as f:
        f.write(payload)
    return hub


def _backups(hub):
    return glob.glob(hub.config_path + ".corrupt-*")


class TestBadUtf8:
    def test_raises_corrupt_error_not_unicode_error(self, tmp_path):
        hub = _hub_with(tmp_path, BAD_UTF8)
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()

    def test_backup_is_byte_identical_and_original_untouched(self, tmp_path):
        hub = _hub_with(tmp_path, BAD_UTF8)
        with pytest.raises(IntegrationConfigCorruptError):
            hub.list_integrations()
        backups = _backups(hub)
        assert len(backups) == 1
        assert open(backups[0], "rb").read() == BAD_UTF8
        assert open(hub.config_path, "rb").read() == BAD_UTF8

    def test_repeated_loads_reuse_the_identical_backup(self, tmp_path):
        hub = _hub_with(tmp_path, BAD_UTF8)
        for _ in range(3):
            with pytest.raises(IntegrationConfigCorruptError):
                hub._load_config()
        assert len(_backups(hub)) == 1

    def test_write_paths_do_not_overwrite_the_bad_file(self, tmp_path):
        hub = _hub_with(tmp_path, BAD_UTF8)
        with pytest.raises(Exception):
            hub.add_integration("a", "native", {"adapter_module": "x"})
        with pytest.raises(IntegrationConfigCorruptError):
            hub.delete_integration("a")
        with pytest.raises(IntegrationConfigCorruptError):
            hub.update_status("a", "error")
        assert open(hub.config_path, "rb").read() == BAD_UTF8

    def test_utf8_bom_file_is_not_corrupt_text_but_invalid_json(self, tmp_path):
        # A BOM decodes fine as utf-8 but json.loads rejects it: still the invalid-JSON path.
        hub = _hub_with(tmp_path, b"\xef\xbb\xbf{}")
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()
        assert len(_backups(hub)) == 1

    def test_valid_utf8_non_ascii_content_still_loads(self, tmp_path):
        payload = json.dumps({"svc": {"type": "native", "config": {"note": "café ✓"}}},
                             ensure_ascii=False).encode("utf-8")
        hub = _hub_with(tmp_path, payload)
        assert hub._load_config()["svc"]["config"]["note"] == "café ✓"
        assert _backups(hub) == []


class TestNonDictRoot:
    @pytest.mark.parametrize("payload", [b"[]", b"[1, 2]", b'"text"', b"42", b"null", b"true"])
    def test_non_object_root_is_corrupt(self, tmp_path, payload):
        hub = _hub_with(tmp_path, payload)
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()
        assert open(_backups(hub)[0], "rb").read() == payload
        assert open(hub.config_path, "rb").read() == payload

    def test_non_object_root_backup_is_reused(self, tmp_path):
        hub = _hub_with(tmp_path, b"[1]")
        for _ in range(2):
            with pytest.raises(IntegrationConfigCorruptError):
                hub._load_config()
        assert len(_backups(hub)) == 1

    def test_changed_bad_content_gets_a_new_backup(self, tmp_path):
        hub = _hub_with(tmp_path, b"[1]")
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()
        with open(hub.config_path, "wb") as f:
            f.write(BAD_UTF8)
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()
        assert len(_backups(hub)) == 2


class TestExistingBehaviourKept:
    def test_invalid_json_still_corrupt(self, tmp_path):
        hub = _hub_with(tmp_path, b"{ nope")
        with pytest.raises(IntegrationConfigCorruptError):
            hub._load_config()

    def test_missing_file_is_empty(self, tmp_path):
        assert IntegrationHub(str(tmp_path))._load_config() == {}

    def test_valid_object_loads(self, tmp_path):
        hub = _hub_with(tmp_path, b'{"a": {"type": "native", "config": {}}}')
        assert "a" in hub._load_config()
        assert _backups(hub) == []
