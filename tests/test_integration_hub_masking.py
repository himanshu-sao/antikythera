"""P1-1 / R9: secret masking in integration configs.

Covers camelCase keys, nested dicts, header maps, secret flags inside ``args``
lists, URL userinfo, and the PATCH round trip that restores nested stored values.
All secret-looking values here are fake literals.
"""
import pytest

from api.integration_hub import (
    IntegrationHub,
    MASK_PLACEHOLDER as MASK,
    mask_config,
    merge_config_preserving_mask,
)


@pytest.fixture
def hub(tmp_path):
    return IntegrationHub(str(tmp_path))


# --------------------------------------------------------------------------
# Key shapes
# --------------------------------------------------------------------------
class TestSecretKeyShapes:
    @pytest.mark.parametrize("key", [
        "accessToken", "clientSecret", "apiToken", "privateKey", "apiKey", "APIKey",
        "access_token", "client-secret", "x-api-key", "X-Api-Key", "Authorization",
        "authorization", "auth", "bearer", "Cookie", "sessionId", "session_id",
        "db_password", "dbPassword", "passwd", "PWD", "pat", "github_pat",
        "credentials", "credential", "token", "key",
        "refreshToken", "secret", "API_TOKEN",
    ])
    def test_secret_key_masked(self, key):
        assert mask_config({key: "fake-value"})[key] == MASK

    @pytest.mark.parametrize("key", [
        "path", "paths", "command", "name", "url", "monkey", "keyboard", "keyword",
        "pattern", "patch", "adapter_module", "jira_url", "timeout", "enabled",
        "description", "host", "port", "tokenizer", "passenger", "workdir",
        "file_path", "filePath", "type",
    ])
    def test_non_secret_key_untouched(self, key):
        assert mask_config({key: "visible"})[key] == "visible"

    def test_empty_and_none_secret_values_left_alone(self):
        out = mask_config({"accessToken": "", "clientSecret": None})
        assert out == {"accessToken": "", "clientSecret": None}

    def test_does_not_mutate_input(self):
        src = {"auth": {"token": "fake"}, "args": ["--token", "fake"]}
        mask_config(src)
        assert src == {"auth": {"token": "fake"}, "args": ["--token", "fake"]}


# --------------------------------------------------------------------------
# Nesting
# --------------------------------------------------------------------------
class TestNestedMasking:
    def test_nested_dict_secret_masked_sibling_visible(self):
        out = mask_config({"auth": {"token": "fake-tok", "type": "bearer"}})
        # "auth" is itself a secret segment, so everything under it is masked
        assert out["auth"] == {"token": MASK, "type": MASK}

    def test_nested_secret_under_plain_parent(self):
        out = mask_config({"oauth2": {"clientSecret": "fake", "scope": "read"}})
        assert out["oauth2"]["clientSecret"] == MASK
        assert out["oauth2"]["scope"] == "read"

    def test_headers_authorization_masked_others_visible(self):
        out = mask_config({"headers": {"Authorization": "Bearer fake", "Accept": "application/json"}})
        assert out["headers"]["Authorization"] == MASK
        assert out["headers"]["Accept"] == "application/json"

    def test_deeply_nested(self):
        out = mask_config({"a": {"b": {"c": {"password": "fake", "note": "x"}}}})
        assert out["a"]["b"]["c"] == {"password": MASK, "note": "x"}

    def test_list_of_dicts(self):
        out = mask_config({"servers": [{"name": "a", "apiKey": "fake"}, {"name": "b"}]})
        assert out["servers"] == [{"name": "a", "apiKey": MASK}, {"name": "b"}]

    def test_nested_env_mapping_masked_wholesale(self):
        out = mask_config({"server": {"env": {"LOG_LEVEL": "debug", "EMPTY": ""}}})
        assert out["server"]["env"] == {"LOG_LEVEL": MASK, "EMPTY": ""}

    def test_top_level_env_still_masked(self):
        out = mask_config({"env": {"A": "x", "B": None}})
        assert out["env"] == {"A": MASK, "B": None}

    def test_secret_key_holding_a_list(self):
        out = mask_config({"tokens": ["fake-a", "fake-b"], "credentials": ["x", ""]})
        assert out["tokens"] == [MASK, MASK]
        assert out["credentials"] == [MASK, ""]

    def test_non_secret_nested_values_pass_through(self):
        cfg = {"limits": {"max": 5, "names": ["a", "b"], "flag": True}}
        assert mask_config(cfg) == cfg


# --------------------------------------------------------------------------
# args lists
# --------------------------------------------------------------------------
class TestArgsFlags:
    def test_value_after_secret_flag_masked(self):
        out = mask_config({"args": ["--api-key", "fake-val", "--verbose"]})
        assert out["args"] == ["--api-key", MASK, "--verbose"]

    def test_password_flag(self):
        out = mask_config({"args": ["--password", "fake-pw"]})
        assert out["args"] == ["--password", MASK]

    def test_flag_equals_value(self):
        out = mask_config({"args": ["--token=fake-tok", "--name=ok"]})
        assert out["args"] == [f"--token={MASK}", "--name=ok"]

    def test_single_dash_secret_word_flag(self):
        out = mask_config({"args": ["-token", "fake"]})
        assert out["args"] == ["-token", MASK]

    def test_non_secret_flags_untouched(self):
        args = ["-y", "@modelcontextprotocol/server", "--path", "/tmp/x", "--port", "8080"]
        assert mask_config({"args": list(args)})["args"] == args

    def test_secret_flag_followed_by_another_flag_does_not_swallow_it(self):
        out = mask_config({"args": ["--token", "--verbose", "x"]})
        assert out["args"] == ["--token", "--verbose", "x"]

    def test_trailing_secret_flag_without_value(self):
        assert mask_config({"args": ["--token"]})["args"] == ["--token"]

    def test_empty_value_after_flag_left_alone(self):
        assert mask_config({"args": ["--token", ""]})["args"] == ["--token", ""]

    def test_non_string_args_do_not_break(self):
        assert mask_config({"args": [1, None, "--token", "x"]})["args"] == [1, None, "--token", MASK]


# --------------------------------------------------------------------------
# URL userinfo
# --------------------------------------------------------------------------
class TestUrlUserinfo:
    def test_password_part_masked_user_and_host_kept(self):
        out = mask_config({"dsn": "postgres://u:fakepw@db.example/app"})
        assert out["dsn"] == f"postgres://u:{MASK}@db.example/app"

    def test_url_key_with_credentials_masked(self):
        out = mask_config({"url": "https://svc:fakepw@host.example/x?y=1"})
        assert out["url"] == f"https://svc:{MASK}@host.example/x?y=1"

    def test_url_without_credentials_untouched(self):
        for url in ("https://example.invalid", "https://example.invalid:8443/a:b@c",
                    "postgres://db.example/app", "ssh://git@host.example/repo.git"):
            assert mask_config({"url": url})["url"] == url

    def test_url_in_args_list(self):
        out = mask_config({"args": ["--dsn", "mysql://root:fakepw@h/db"]})
        assert out["args"] == ["--dsn", f"mysql://root:{MASK}@h/db"]

    def test_url_inside_nested_dict(self):
        out = mask_config({"backend": {"endpoint": "redis://:fakepw@cache:6379/0"}})
        assert out["backend"]["endpoint"] == f"redis://:{MASK}@cache:6379/0"

    def test_env_placeholder_password_masked(self):
        out = mask_config({"dsn": "postgres://u:${env:DB_PW}@h/db"})
        assert out["dsn"] == f"postgres://u:{MASK}@h/db"

    def test_plain_text_with_colon_not_a_url(self):
        assert mask_config({"note": "a:b@c"})["note"] == "a:b@c"

    def test_no_secret_text_survives_in_serialized_output(self):
        import json
        cfg = {
            "accessToken": "LEAK1", "auth": {"token": "LEAK2"},
            "headers": {"Authorization": "LEAK3"},
            "args": ["--api-key", "LEAK4", "--token=LEAK5", "--password", "LEAK6"],
            "dsn": "postgres://u:LEAK7@h/db",
        }
        text = json.dumps(mask_config(cfg))
        for i in range(1, 8):
            assert f"LEAK{i}" not in text


# --------------------------------------------------------------------------
# list_integrations goes through the same masking
# --------------------------------------------------------------------------
class TestListIntegrationsMasksShapes:
    def test_list_masks_every_shape_stored_values_untouched(self, hub):
        cfg = {
            "command": "npx", "name": "svc", "path": "/tmp/p", "url": "https://example.invalid",
            "accessToken": "fake1", "auth": {"token": "fake2"},
            "headers": {"Authorization": "fake3", "Accept": "x"},
            "args": ["--api-key", "fake4"], "dsn": "postgres://u:fake5@h/db",
        }
        hub.add_integration("svc", "mcp", cfg)
        listed = {i["name"]: i for i in hub.list_integrations()}["svc"]["config"]
        assert listed["accessToken"] == MASK
        assert listed["auth"]["token"] == MASK
        assert listed["headers"] == {"Authorization": MASK, "Accept": "x"}
        assert listed["args"] == ["--api-key", MASK]
        assert listed["dsn"] == f"postgres://u:{MASK}@h/db"
        assert (listed["command"], listed["name"], listed["path"], listed["url"]) == (
            "npx", "svc", "/tmp/p", "https://example.invalid")
        stored = hub.get_integration("svc")["config"]
        assert stored["accessToken"] == "fake1"
        assert stored["auth"]["token"] == "fake2"
        assert stored["args"] == ["--api-key", "fake4"]


# --------------------------------------------------------------------------
# PATCH round trip: masked nested values restore the stored ones
# --------------------------------------------------------------------------
class TestRoundTripRestoresNestedSecrets:
    def _stored(self):
        return {
            "adapter_module": "x",
            "accessToken": "stored-1",
            "auth": {"token": "stored-2", "type": "bearer"},
            "headers": {"Authorization": "stored-3", "Accept": "a"},
            "args": ["--api-key", "stored-4", "--token=stored-5", "--name", "n"],
            "dsn": "postgres://u:stored-6@h/db",
            "env": {"GH_TOKEN": "stored-7"},
        }

    def test_masked_roundtrip_is_identity(self, hub):
        hub.add_integration("svc", "native", self._stored())
        listed = {i["name"]: i for i in hub.list_integrations()}["svc"]["config"]
        hub.update_integration("svc", listed)
        assert hub.get_integration("svc")["config"] == self._stored()

    def test_edit_one_nested_value_keeps_the_rest(self, hub):
        hub.add_integration("svc", "native", self._stored())
        listed = {i["name"]: i for i in hub.list_integrations()}["svc"]["config"]
        listed["headers"]["Accept"] = "b"
        listed["auth"]["token"] = "brand-new"
        hub.update_integration("svc", listed)
        cfg = hub.get_integration("svc")["config"]
        assert cfg["auth"] == {"token": "brand-new", "type": "bearer"}
        assert cfg["headers"] == {"Authorization": "stored-3", "Accept": "b"}
        assert cfg["accessToken"] == "stored-1"
        assert cfg["args"] == self._stored()["args"]

    def test_nested_mask_without_stored_value_is_dropped_not_stored(self, hub):
        hub.add_integration("svc", "native", {"adapter_module": "x"})
        hub.update_integration("svc", {"auth": {"token": MASK, "type": "bearer"}, "args": ["--api-key", MASK]})
        cfg = hub.get_integration("svc")["config"]
        assert cfg["auth"] == {"type": "bearer"}
        assert MASK not in repr(cfg)

    def test_args_edit_replaces_secret_value(self, hub):
        hub.add_integration("svc", "native", {"adapter_module": "x", "args": ["--api-key", "old"]})
        hub.update_integration("svc", {"args": ["--api-key", "new"]})
        assert hub.get_integration("svc")["config"]["args"] == ["--api-key", "new"]

    def test_nested_dict_replaced_and_masked_leaf_restored(self, hub):
        # Top-level dicts are replaced, as before; only the masked leaf is restored.
        hub.add_integration("svc", "native", {"adapter_module": "x", "headers": {"A": "1", "Authorization": "s"}})
        hub.update_integration("svc", {"headers": {"Authorization": MASK}})
        assert hub.get_integration("svc")["config"]["headers"] == {"Authorization": "s"}

    def test_url_with_unchanged_masked_password_restores(self, hub):
        hub.add_integration("svc", "native", {"adapter_module": "x", "dsn": "postgres://u:pw1@h/db"})
        hub.update_integration("svc", {"dsn": f"postgres://u:{MASK}@h/db"})
        assert hub.get_integration("svc")["config"]["dsn"] == "postgres://u:pw1@h/db"

    def test_url_with_new_password_is_stored(self, hub):
        hub.add_integration("svc", "native", {"adapter_module": "x", "dsn": "postgres://u:pw1@h/db"})
        hub.update_integration("svc", {"dsn": "postgres://u:pw2@h/db"})
        assert hub.get_integration("svc")["config"]["dsn"] == "postgres://u:pw2@h/db"

    def test_masked_element_without_stored_counterpart_is_dropped(self):
        merged = merge_config_preserving_mask({"args": ["--x"]}, {"args": ["--x", "--token", MASK]})
        assert merged["args"] == ["--x", "--token"]

    def test_existing_top_level_behaviour_unchanged(self):
        merged = merge_config_preserving_mask({"token": "t", "keep": 1}, {"token": MASK, "new": 2})
        assert merged == {"token": "t", "keep": 1, "new": 2}
        merged = merge_config_preserving_mask({"env": {"A": "a", "B": "b"}}, {"env": {"A": MASK, "C": "c"}})
        assert merged["env"] == {"A": "a", "B": "b", "C": "c"}
