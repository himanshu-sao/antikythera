"""The built-in help page: public, self-contained, accurate."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    # /help is deliberately outside the token wall (public instructions).
    app.dependency_overrides.pop(__import__(
        "api.security", fromlist=["require_token"]).require_token, None)
    with TestClient(app) as c:
        yield c


def _get(client):
    return client.get("/help")


def test_help_is_public_html(client):
    res = _get(client)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")


def test_help_has_the_core_sections(client):
    body = _get(client).text
    for marker in (
        "Getting started", "API token", "Authorization: Bearer",
        "Automation Studio", "dry run", "adapter", "force",
        "Troubleshooting", "Integration github not found",
        "/api/settings", "POST /api/workflows/trigger",
    ):
        assert marker in body, marker


def test_help_documents_the_current_ports(client):
    body = _get(client).text
    assert "18006" in body and "15173" in body


def test_help_loads_no_external_resources(client):
    body = _get(client).text
    for attr in ("src=\"http", "src='http", "href=\"http", "href='http"):
        assert attr not in body, attr


def test_help_does_not_leak_paths_or_tokens(client):
    body = _get(client).text
    # Documents the token *location*, never a value; no absolute host paths.
    assert "sk-" not in body
    assert "/Users/" not in body
