"""D1: bearer-token authentication, CORS and docs gating.

conftest.py installs an autouse override that bypasses ``require_token`` for
the rest of the suite. The ``real_auth`` fixture below removes it so these
tests exercise the real dependency.
"""
import logging
import os
import stat

import pytest
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import api.main as api_main
from api import security
from api.security import get_or_create_token, require_token

TOKEN = "test-token"
GOOD = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def real_auth(monkeypatch):
    """Use the real require_token with a known token."""
    api_main.app.dependency_overrides.pop(require_token, None)
    monkeypatch.setenv("ANTIKYTHERA_API_TOKEN", TOKEN)
    yield TestClient(api_main.app)


# --------------------------------------------------------------------------
# require_token on the real app
# --------------------------------------------------------------------------
PROTECTED_GETS = [
    "/api/state",
    "/api/integrations/",
    "/api/ai-engine/config",
    "/api/workflows/templates",
    "/api/studio/graphs",
    "/api/pipelines/",
    "/api/brain/artifacts",
    "/api/automation/templates",
]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_no_token_is_401(real_auth, path):
    r = real_auth.get(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_wrong_token_is_401(real_auth, path):
    r = real_auth.get(path, headers={"Authorization": "Bearer not-the-token"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_right_token_is_200(real_auth, path):
    r = real_auth.get(path, headers=GOOD)
    assert r.status_code == 200, path


@pytest.mark.parametrize(
    "header",
    ["", "Bearer", "Bearer ", f"Basic {TOKEN}", TOKEN, f"Token {TOKEN}"],
)
def test_malformed_authorization_header_is_401(real_auth, header):
    r = real_auth.get("/api/state", headers={"Authorization": header})
    assert r.status_code == 401


def test_scheme_is_case_insensitive(real_auth):
    r = real_auth.get("/api/state", headers={"Authorization": f"bearer {TOKEN}"})
    assert r.status_code == 200


def test_post_without_token_is_401_before_body_validation(real_auth):
    r = real_auth.post("/api/move", json={})
    assert r.status_code == 401


def test_every_api_route_requires_token(real_auth):
    """No /api route (except the setup router, which guards itself) is open."""
    # Docs are off by default (openapi_url is None), so build the schema directly.
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title="t", version="0", routes=api_main.app.routes)
    checked = 0
    for path, methods in schema["paths"].items():
        if not path.startswith("/api/") or path.startswith("/api/setup"):
            continue
        concrete = path.replace("{", "").replace("}", "")
        for method in methods:
            r = real_auth.request(method.upper(), concrete)
            assert r.status_code == 401, f"{method.upper()} {path} -> {r.status_code}"
            checked += 1
    assert checked > 50


def test_root_stays_open(real_auth):
    assert real_auth.get("/").status_code == 200


def test_setup_router_has_no_token_dependency():
    """The setup router must not be wrapped in require_token."""
    from fastapi.routing import APIRoute

    import api.setup_router as setup_router

    for route in setup_router.router.routes:
        if isinstance(route, APIRoute):
            assert all(d.call is not require_token for d in route.dependant.dependencies)
    # And the app-level include for it carries no auth dependency either.
    src = open(api_main.__file__, encoding="utf-8").read()
    assert "app.include_router(setup_router)" in src


def test_settings_router_requires_token(real_auth):
    assert real_auth.get("/api/settings").status_code == 401
    assert real_auth.get("/api/settings", headers=GOOD).status_code == 200


def test_late_set_env_token_is_honoured(real_auth, monkeypatch):
    monkeypatch.setenv("ANTIKYTHERA_API_TOKEN", "late-value")
    assert real_auth.get("/api/state", headers=GOOD).status_code == 401
    ok = real_auth.get("/api/state", headers={"Authorization": "Bearer late-value"})
    assert ok.status_code == 200


# --------------------------------------------------------------------------
# get_or_create_token
# --------------------------------------------------------------------------
def test_env_token_wins_and_no_file_is_written(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
    monkeypatch.setenv("ANTIKYTHERA_API_TOKEN", "from-env")
    assert get_or_create_token() == "from-env"
    assert not home.exists()


def test_existing_token_file_is_used(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "api_token").write_text("from-file\n")
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
    monkeypatch.delenv("ANTIKYTHERA_API_TOKEN", raising=False)
    assert get_or_create_token() == "from-file"


def test_token_generated_0600_and_value_never_logged(tmp_path, monkeypatch, caplog):
    home = tmp_path / "fresh" / "dotdir"  # parent dirs do not exist yet
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
    monkeypatch.delenv("ANTIKYTHERA_API_TOKEN", raising=False)
    with caplog.at_level(logging.DEBUG):
        token = get_or_create_token()
    path = home / "api_token"
    assert path.is_file()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert path.read_text().strip() == token
    assert len(token) >= 32
    # The path is logged at INFO; the value never appears in any record.
    messages = [r.getMessage() for r in caplog.records]
    assert any(str(path) in m for m in messages)
    assert not any(token in m for m in messages)
    assert [r for r in caplog.records if r.name == "antikythera.security"][0].levelno == logging.INFO
    # No leftover temp files in the directory.
    assert [p.name for p in home.iterdir()] == ["api_token"]


def test_generated_token_is_stable_across_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(tmp_path / "h"))
    monkeypatch.delenv("ANTIKYTHERA_API_TOKEN", raising=False)
    assert get_or_create_token() == get_or_create_token()


def test_generated_file_token_authenticates_requests(real_auth, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(tmp_path / "h"))
    monkeypatch.delenv("ANTIKYTHERA_API_TOKEN", raising=False)
    token = get_or_create_token()
    assert real_auth.get("/api/state").status_code == 401
    r = real_auth.get("/api/state", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_blank_env_falls_through_to_file(tmp_path, monkeypatch):
    home = tmp_path / "h"
    home.mkdir()
    (home / "api_token").write_text("file-token")
    monkeypatch.setenv("ANTIKYTHERA_HOME", str(home))
    monkeypatch.setenv("ANTIKYTHERA_API_TOKEN", "   ")
    assert get_or_create_token() == "file-token"


def test_default_config_dir_without_home_override(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTIKYTHERA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert security.config_dir() == tmp_path / ".antikythera"


def test_require_token_uses_compare_digest(monkeypatch):
    calls = []
    real = security.hmac.compare_digest

    def spy(a, b):
        calls.append((type(a), type(b)))
        return real(a, b)

    monkeypatch.setattr(security.hmac, "compare_digest", spy)
    app = FastAPI()

    @app.get("/x", dependencies=[Depends(require_token)])
    def x():
        return {}

    monkeypatch.setenv("ANTIKYTHERA_API_TOKEN", TOKEN)
    c = TestClient(app)
    assert c.get("/x", headers=GOOD).status_code == 200
    assert calls


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------
def test_cors_default_origin(monkeypatch):
    monkeypatch.delenv("ANTIKYTHERA_CORS_ORIGINS", raising=False)
    assert api_main.cors_origins() == ["http://localhost:15173"]


def test_cors_origins_parsed_from_env(monkeypatch):
    monkeypatch.setenv("ANTIKYTHERA_CORS_ORIGINS", " http://a.test:1 ,http://b.test ,, ")
    assert api_main.cors_origins() == ["http://a.test:1", "http://b.test"]


def test_preflight_allows_authorization_and_json_from_configured_origin(real_auth):
    """The UI sends Authorization on every call and Content-Type on JSON bodies."""
    origin = "http://localhost:15173"
    r = real_auth.options(
        "/api/move",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    allowed = {h.strip().lower() for h in r.headers["access-control-allow-headers"].split(",")}
    assert {"authorization", "content-type"} <= allowed
    assert "access-control-allow-credentials" not in r.headers


def test_preflight_from_other_origin_has_no_allow_origin(real_auth):
    r = real_auth.options(
        "/api/move",
        headers={
            "Origin": "http://evil.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-origin" not in r.headers


def test_real_app_cors_allows_default_origin_and_blocks_others(real_auth):
    origin = "http://localhost:15173"
    r = real_auth.options(
        "/api/state",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in r.headers

    bad = real_auth.options(
        "/api/state",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers

    star = real_auth.get("/", headers={"Origin": "http://evil.test"})
    assert star.headers.get("access-control-allow-origin") != "*"


def test_cors_header_on_authenticated_response(real_auth):
    r = real_auth.get("/api/state", headers={**GOOD, "Origin": "http://localhost:15173"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:15173"


def test_cors_configured_origin_from_env(monkeypatch):
    monkeypatch.setenv("ANTIKYTHERA_CORS_ORIGINS", "http://ui.example:9999")
    mini = FastAPI()
    mini.add_middleware(
        CORSMiddleware,
        allow_origins=api_main.cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @mini.get("/p")
    def p():
        return {}

    c = TestClient(mini)
    ok = c.get("/p", headers={"Origin": "http://ui.example:9999"})
    assert ok.headers["access-control-allow-origin"] == "http://ui.example:9999"
    no = c.get("/p", headers={"Origin": "http://localhost:15173"})
    assert "access-control-allow-origin" not in no.headers


# --------------------------------------------------------------------------
# Docs gating
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_are_404_by_default(real_auth, path):
    assert real_auth.get(path).status_code == 404
    assert real_auth.get(path, headers=GOOD).status_code == 404


def test_docs_kwargs_off_by_default(monkeypatch):
    monkeypatch.delenv("ANTIKYTHERA_ENABLE_DOCS", raising=False)
    assert api_main.docs_kwargs() == {"docs_url": None, "redoc_url": None, "openapi_url": None}


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_docs_stay_off_for_falsy_values(monkeypatch, value):
    monkeypatch.setenv("ANTIKYTHERA_ENABLE_DOCS", value)
    assert api_main.docs_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_docs_present_when_enabled(monkeypatch, value):
    monkeypatch.setenv("ANTIKYTHERA_ENABLE_DOCS", value)
    assert api_main.docs_kwargs() == {}
    mini = FastAPI(**api_main.docs_kwargs())
    c = TestClient(mini)
    assert c.get("/docs").status_code == 200
    assert c.get("/redoc").status_code == 200
    assert c.get("/openapi.json").status_code == 200


def _app_docs_urls(tmp_path, enable):
    """Import api.main in a clean interpreter and report its docs URLs."""
    import json
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTIKYTHERA_ENABLE")}
    env.update(
        ANTIKYTHERA_HOME=str(tmp_path / "home"),
        ANTIKYTHERA_API_TOKEN=TOKEN,
        ANTIKYTHERA_BOB_STUB="1",
        PYTHONPATH=root,
    )
    if enable:
        env["ANTIKYTHERA_ENABLE_DOCS"] = "1"
    code = (
        "import json, api.main as m;"
        "print(json.dumps([m.app.docs_url, m.app.redoc_url, m.app.openapi_url]))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr[-500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_real_app_docs_off_by_default_and_on_when_enabled(tmp_path):
    assert _app_docs_urls(tmp_path, enable=False) == [None, None, None]
    assert _app_docs_urls(tmp_path, enable=True) == ["/docs", "/redoc", "/openapi.json"]
