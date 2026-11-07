"""Tests for the D9 first-run setup wizard router (api/setup_router.py).

Client addresses: the TestClient default is the string ``testclient``, which is not
an IP and is therefore treated as non-loopback. Loopback cases construct the client with
``client=("127.0.0.1", 50000)``; non-loopback cases use ``client=("203.0.113.7", 50000)``.
The mini app mounts only the setup router; the last test checks the real ``api.main`` app.
"""

import os
import stat

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import api.services.ai_engine_config as aec
import api.setup_router as setup_router
from api.security import TOKEN_ENV_VAR

LOOPBACK = ("127.0.0.1", 50000)
REMOTE = ("203.0.113.7", 50000)

SECRET_VALUE = "sk-live-VALUE-must-not-leak-9f3a"
PAT_VALUE = "jira-pat-VALUE-must-not-leak-77c1"
SLACK_VALUE = "https://hooks.slack.com/services/T000/B000/VALUE-must-not-leak"


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolated ANTIKYTHERA_HOME with every setup-relevant env var cleared."""
    antikythera_home = tmp_path / "setup-wizard-home"
    antikythera_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(antikythera_home))
    for name in (
        TOKEN_ENV_VAR,
        "PORT",
        "ANTIKYTHERA_CORS_ORIGINS",
        "ANTIKYTHERA_BACKUP_DIR",
        "JIRA_BASE_URL",
        "JIRA_PAT",
        "ANTIKYTHERA_SLACK_WEBHOOK",
        "ISV_SLACK_WEBHOOK_URL",
        *setup_router.PROVIDER_KEY_NAMES,
    ):
        # setenv then delenv records the prior state, so the router's os.environ
        # writes are undone at teardown and cannot leak into other tests.
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)
    # Secrets file lives where the real AI engine writer would put it under ANTIKYTHERA_HOME.
    # (conftest patches _persistent_env_path to a different tmp path; this restores the
    # ANTIKYTHERA_HOME-aware behaviour for these tests.)
    monkeypatch.setattr(
        aec.AIEngineConfigService,
        "_persistent_env_path",
        lambda self: str(aec._antikythera_dir(use_pwd=True) / ".ai_env"),
    )
    setup_router._reset_rate_limit()
    yield antikythera_home
    setup_router._reset_rate_limit()


@pytest.fixture
def client(home):
    app = FastAPI()
    app.include_router(setup_router.router)
    return TestClient(app, client=LOOPBACK)


def _client_at(address):
    app = FastAPI()
    app.include_router(setup_router.router)
    return TestClient(app, client=address)


def _items_by_id(body):
    return {item["id"]: item for item in body["items"]}


# ---------------------------------------------------------------------------
# Loopback classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.8.9.10", "127.255.255.254", "::1", "::ffff:127.0.0.1", "::1%lo0"],
)
def test_is_loopback_accepts_loopback_addresses(host):
    assert setup_router._is_loopback(host) is True


@pytest.mark.parametrize(
    "host",
    [None, "", "testclient", "10.0.0.5", "192.168.1.9", "128.0.0.1", "203.0.113.7", "::2", "fe80::1", "localhost"],
)
def test_is_loopback_rejects_everything_else(host):
    assert setup_router._is_loopback(host) is False


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_status_reports_typed_items_and_incomplete(client):
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    body = response.json()
    assert body["complete"] is False
    items = _items_by_id(body)
    expected_ids = {
        "env_file",
        "NVIDIA_API_KEY",
        "GOOGLE_API_KEY",
        "IBM_BOB_API_KEY",
        "OLLAMA_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "JIRA_BASE_URL",
        "JIRA_PAT",
        "ANTIKYTHERA_SLACK_WEBHOOK",
        "api_token",
        "PORT",
        "ANTIKYTHERA_CORS_ORIGINS",
        "data_dir",
        "ANTIKYTHERA_BACKUP_DIR",
    }
    assert expected_ids <= set(items)
    for item in body["items"]:
        assert set(item) == {"id", "kind", "name", "label", "ok", "state", "settable", "secret"}


def test_status_never_contains_secret_values(client, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", SECRET_VALUE)
    monkeypatch.setenv("JIRA_PAT", PAT_VALUE)
    monkeypatch.setenv("ANTIKYTHERA_SLACK_WEBHOOK", SLACK_VALUE)
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    response = client.get("/api/setup/status")
    text = response.text
    assert SECRET_VALUE not in text
    assert PAT_VALUE not in text
    assert SLACK_VALUE not in text
    assert "example.atlassian.net" not in text
    items = _items_by_id(response.json())
    assert items["NVIDIA_API_KEY"]["ok"] is True and items["NVIDIA_API_KEY"]["state"] == "set"
    assert items["JIRA_PAT"]["secret"] is True
    assert items["ANTIKYTHERA_SLACK_WEBHOOK"]["ok"] is True
    assert items["GOOGLE_API_KEY"]["ok"] is False and items["GOOGLE_API_KEY"]["state"] == "unset"


def test_status_slack_fallback_var_counts_as_set(client, monkeypatch):
    monkeypatch.setenv("ISV_SLACK_WEBHOOK_URL", SLACK_VALUE)
    items = _items_by_id(client.get("/api/setup/status").json())
    assert items["ANTIKYTHERA_SLACK_WEBHOOK"]["ok"] is True
    assert SLACK_VALUE not in client.get("/api/setup/status").text


def test_status_ports_and_origins_default_vs_custom(client, monkeypatch):
    items = _items_by_id(client.get("/api/setup/status").json())
    assert items["PORT"]["state"] == "default"
    assert items["ANTIKYTHERA_CORS_ORIGINS"]["state"] == "default"
    monkeypatch.setenv("PORT", "19000")
    monkeypatch.setenv("ANTIKYTHERA_CORS_ORIGINS", "https://ui.example")
    items = _items_by_id(client.get("/api/setup/status").json())
    assert items["PORT"]["state"] == "custom"
    assert items["ANTIKYTHERA_CORS_ORIGINS"]["state"] == "custom"


def test_status_api_token_states(client, home):
    assert _items_by_id(client.get("/api/setup/status").json())["api_token"]["state"] == "missing"
    (home / "api_token").write_text("tok-file-value\n", encoding="utf-8")
    body = client.get("/api/setup/status").json()
    assert _items_by_id(body)["api_token"]["state"] == "generated"
    assert "tok-file-value" not in client.get("/api/setup/status").text


def test_status_env_file_presence(client, home):
    assert _items_by_id(client.get("/api/setup/status").json())["env_file"]["state"] == "missing"
    (home / ".env").write_text("PORT=18006\n", encoding="utf-8")
    assert _items_by_id(client.get("/api/setup/status").json())["env_file"]["state"] == "present"


def test_status_data_dir_reports_presence_and_writability(client, monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(setup_router, "_data_dir", lambda: data_dir)
    assert _items_by_id(client.get("/api/setup/status").json())["data_dir"]["state"] == "missing"
    data_dir.mkdir()
    assert _items_by_id(client.get("/api/setup/status").json())["data_dir"]["state"] == "writable"
    data_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        if not os.access(data_dir, os.W_OK):
            assert _items_by_id(client.get("/api/setup/status").json())["data_dir"]["state"] == "read_only"
    finally:
        data_dir.chmod(0o700)


def test_status_complete_is_false_while_incomplete(client):
    # A 200 status always means setup is open, so complete is false here. Once the
    # marker exists the route returns 404 (covered in the lock tests below).
    assert client.get("/api/setup/status").json()["complete"] is False


# ---------------------------------------------------------------------------
# Config writes
# ---------------------------------------------------------------------------

def test_config_writes_secrets_to_secrets_file_and_plain_to_env(client, home):
    response = client.post(
        "/api/setup/config",
        json={
            "NVIDIA_API_KEY": SECRET_VALUE,
            "JIRA_PAT": PAT_VALUE,
            "ANTIKYTHERA_SLACK_WEBHOOK": SLACK_VALUE,
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "PORT": "18006",
        },
    )
    assert response.status_code == 200
    assert response.json()["written"] == sorted(
        ["NVIDIA_API_KEY", "JIRA_PAT", "ANTIKYTHERA_SLACK_WEBHOOK", "JIRA_BASE_URL", "PORT"]
    )
    # The response never echoes a value.
    for value in (SECRET_VALUE, PAT_VALUE, SLACK_VALUE, "example.atlassian.net"):
        assert value not in response.text

    secrets_text = (home / ".ai_env").read_text(encoding="utf-8")
    assert f"NVIDIA_API_KEY='{SECRET_VALUE}'" in secrets_text
    assert f"JIRA_PAT='{PAT_VALUE}'" in secrets_text
    assert f"ANTIKYTHERA_SLACK_WEBHOOK='{SLACK_VALUE}'" in secrets_text
    assert "JIRA_BASE_URL" not in secrets_text

    plain_text = (home / ".env").read_text(encoding="utf-8")
    assert "JIRA_BASE_URL='https://example.atlassian.net'" in plain_text
    assert "PORT='18006'" in plain_text
    assert SECRET_VALUE not in plain_text
    assert PAT_VALUE not in plain_text
    assert SLACK_VALUE not in plain_text


def test_config_writes_are_mode_0600(client, home):
    client.post("/api/setup/config", json={"NVIDIA_API_KEY": SECRET_VALUE, "PORT": "18006"})
    for name in (".ai_env", ".env"):
        mode = stat.S_IMODE(os.stat(home / name).st_mode)
        assert mode == 0o600, name


def test_config_single_quote_is_escaped_like_the_safe_writer(client, home):
    client.post("/api/setup/config", json={"NVIDIA_API_KEY": "ab'cd"})
    assert "NVIDIA_API_KEY='ab'\\''cd'" in (home / ".ai_env").read_text(encoding="utf-8")


def test_config_merges_existing_lines_without_duplicates(client, home):
    (home / ".env").write_text("# mine\nPORT='18006'\nOTHER='keep'\n", encoding="utf-8")
    client.post("/api/setup/config", json={"PORT": "19001", "JIRA_BASE_URL": "https://j.example"})
    text = (home / ".env").read_text(encoding="utf-8")
    assert text.count("PORT=") == 1
    assert "PORT='19001'" in text
    assert "OTHER='keep'" in text
    assert "# mine" in text
    assert "JIRA_BASE_URL='https://j.example'" in text


def test_config_blank_values_are_skipped(client, home):
    response = client.post("/api/setup/config", json={"NVIDIA_API_KEY": "   ", "JIRA_BASE_URL": None})
    assert response.status_code == 200
    assert response.json()["written"] == []
    assert not (home / ".ai_env").exists()


def test_config_partial_map_writes_only_given_keys(client, home):
    client.post("/api/setup/config", json={"JIRA_BASE_URL": "https://only.example"})
    assert not (home / ".ai_env").exists()
    assert "JIRA_BASE_URL='https://only.example'" in (home / ".env").read_text(encoding="utf-8")


def test_config_applies_values_to_the_running_process(client, monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "placeholder")  # records teardown state
    client.post("/api/setup/config", json={"JIRA_BASE_URL": "https://live.example"})
    assert os.environ["JIRA_BASE_URL"] == "https://live.example"


@pytest.mark.parametrize(
    "payload",
    [
        {"NOT_A_SETTING": "x"},
        {"PATH": "/bin"},
        {"NVIDIA_API_KEY": "line1\nline2"},
        {"NVIDIA_API_KEY": "line1\rline2"},
        {"JIRA_PAT": "pat\x00tail"},
        {"JIRA_BASE_URL": "https://ok.example\nINJECTED=1"},
        {"PORT": "not-a-port"},
        {"PORT": "70000"},
        {"PORT": 18006},
        {"JIRA_PAT": "x" * (setup_router.MAX_VALUE_LEN + 1)},
    ],
)
def test_config_rejects_bad_keys_and_values(client, home, payload):
    response = client.post("/api/setup/config", json=payload)
    assert response.status_code == 422
    assert "\x00" not in response.text and "INJECTED=1" not in response.text
    assert not (home / ".ai_env").exists()
    assert not (home / ".env").exists()


def test_config_rejection_does_not_write_partial_batch(client, home):
    response = client.post(
        "/api/setup/config",
        json={"JIRA_BASE_URL": "https://ok.example", "NOT_A_SETTING": "x"},
    )
    assert response.status_code == 422
    assert not (home / ".env").exists()


def test_config_rate_limit_returns_429_after_budget(client):
    for _ in range(setup_router.RATE_LIMIT_MAX_CALLS):
        assert client.post("/api/setup/config", json={}).status_code == 200
    response = client.post("/api/setup/config", json={})
    assert response.status_code == 429


def test_config_rate_limit_window_expires(client, monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(setup_router.time, "monotonic", lambda: clock["now"])
    for _ in range(setup_router.RATE_LIMIT_MAX_CALLS):
        client.post("/api/setup/config", json={})
    assert client.post("/api/setup/config", json={}).status_code == 429
    clock["now"] += setup_router.RATE_LIMIT_WINDOW_S + 1
    assert client.post("/api/setup/config", json={}).status_code == 200


def test_rate_limit_is_not_spent_by_status_or_refused_remote_calls(home):
    local = _client_at(LOOPBACK)
    remote = _client_at(REMOTE)
    for _ in range(setup_router.RATE_LIMIT_MAX_CALLS + 5):
        assert remote.post("/api/setup/config", json={}).status_code == 403
    assert local.post("/api/setup/config", json={}).status_code == 200


# ---------------------------------------------------------------------------
# Loopback gate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/setup/status", None),
    ("post", "/api/setup/config", {"JIRA_BASE_URL": "https://x.example"}),
    ("post", "/api/setup/complete", None),
])
def test_non_loopback_client_gets_403_while_incomplete(home, method, path, body):
    remote = _client_at(REMOTE)
    kwargs = {"json": body} if body is not None else {}
    response = getattr(remote, method)(path, **kwargs)
    assert response.status_code == 403
    assert "local machine" in response.json()["detail"]
    assert not (home / ".setup_complete").exists()
    assert not (home / ".env").exists()


def test_testclient_default_address_is_refused(home):
    # The default TestClient address ('testclient') is not loopback.
    app = FastAPI()
    app.include_router(setup_router.router)
    response = TestClient(app).get("/api/setup/status")
    assert response.status_code == 403


def test_ipv6_loopback_client_is_served(home):
    response = _client_at(("::1", 50000)).get("/api/setup/status")
    assert response.status_code == 200


def test_ipv4_mapped_loopback_client_is_served(home):
    response = _client_at(("::ffff:127.0.0.1", 50000)).get("/api/setup/status")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Complete, lock and reopen
# ---------------------------------------------------------------------------

def test_complete_writes_marker_mode_0600_and_returns_generated_token_once(client, home):
    response = client.post("/api/setup/complete")
    assert response.status_code == 200
    body = response.json()
    assert body["complete"] is True
    marker = home / ".setup_complete"
    assert marker.is_file()
    assert stat.S_IMODE(os.stat(marker).st_mode) == 0o600
    token = body["api_token"]
    assert isinstance(token, str) and len(token) >= 32
    assert token == (home / "api_token").read_text(encoding="utf-8").strip()


def test_complete_does_not_reecho_an_existing_token(client, home):
    (home / "api_token").write_text("already-there-token\n", encoding="utf-8")
    response = client.post("/api/setup/complete")
    assert response.json()["api_token"] is None
    assert "already-there-token" not in response.text


def test_complete_does_not_return_env_supplied_token(client, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token-value")
    body = client.post("/api/setup/complete").json()
    assert body["api_token"] is None


def test_all_routes_return_404_after_completion(client, home):
    assert client.post("/api/setup/complete").status_code == 200
    for response in (
        client.get("/api/setup/status"),
        client.post("/api/setup/config", json={"JIRA_BASE_URL": "https://late.example"}),
        client.post("/api/setup/complete"),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
    assert not (home / ".env").exists()


def test_completed_locks_remote_clients_to_404_not_403(home):
    _client_at(LOOPBACK).post("/api/setup/complete")
    remote = _client_at(REMOTE)
    response = remote.get("/api/setup/status")
    assert response.status_code == 404
    assert "local machine" not in response.text


def test_delete_reopen_requires_token(home, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "reopen-token")
    local = _client_at(LOOPBACK)
    local.post("/api/setup/complete")
    assert (home / ".setup_complete").exists()

    no_token = local.delete("/api/setup/complete")
    assert no_token.status_code == 401
    assert (home / ".setup_complete").exists()

    wrong = local.delete("/api/setup/complete", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    assert (home / ".setup_complete").exists()

    ok = local.delete("/api/setup/complete", headers={"Authorization": "Bearer reopen-token"})
    assert ok.status_code == 200
    assert ok.json() == {"complete": False}
    assert not (home / ".setup_complete").exists()
    assert local.get("/api/setup/status").status_code == 200


def test_reopen_works_from_non_loopback_with_token(home, monkeypatch):
    # The token is the protection for reopen, so the loopback gate does not apply to DELETE.
    monkeypatch.setenv(TOKEN_ENV_VAR, "reopen-token")
    _client_at(LOOPBACK).post("/api/setup/complete")
    response = _client_at(REMOTE).delete(
        "/api/setup/complete", headers={"Authorization": "Bearer reopen-token"}
    )
    assert response.status_code == 200


def test_marker_path_honours_antikythera_home(home):
    assert setup_router._marker_path() == home / ".setup_complete"


# ---------------------------------------------------------------------------
# Real application wiring
# ---------------------------------------------------------------------------

def test_setup_status_on_main_app_needs_no_bearer_token(home, monkeypatch):
    import api.main as api_main
    from api.security import require_token

    # conftest overrides require_token for the whole suite; pop it so this test sees the
    # real router wiring, which must not require a token for the setup routes.
    api_main.app.dependency_overrides.pop(require_token, None)
    local = TestClient(api_main.app, client=LOOPBACK)
    response = local.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json()["complete"] is False
