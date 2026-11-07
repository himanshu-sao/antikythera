"""P1-6 / SEC-10: /api/ai-engine/logs keeps the clamp and says so in a header.

When the request asked for more lines or bytes than the server allows, the response
carries ``X-Log-Truncated: true``. The body stays ``{"logs": str}``.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers import ai_engine_config_router as ai_router


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    target = tmp_path / "backend.log"
    monkeypatch.setattr(ai_router, "BACKEND_LOG_PATH", str(target))
    return target


def _get(params=None):
    return TestClient(app).get("/api/ai-engine/logs", params=params or {})


class TestTruncationHeader:
    def test_lines_over_cap_sets_header(self, log_file):
        log_file.write_text("".join(f"line {i}\n" for i in range(5000)))
        resp = _get({"lines": 999999})
        assert resp.status_code == 200
        assert resp.headers.get("x-log-truncated") == "true"
        assert len(resp.json()["logs"].splitlines()) == 2000

    def test_lines_exactly_at_cap_does_not_set_header(self, log_file):
        log_file.write_text("".join(f"line {i}\n" for i in range(5000)))
        resp = _get({"lines": 2000})
        assert "x-log-truncated" not in resp.headers

    def test_small_request_no_header(self, log_file):
        log_file.write_text("a\nb\nc\n")
        resp = _get({"lines": 2})
        assert resp.status_code == 200
        assert "x-log-truncated" not in resp.headers
        assert resp.json()["logs"] == "b\nc"

    def test_default_request_no_header(self, log_file):
        log_file.write_text("x\n")
        assert "x-log-truncated" not in _get().headers

    def test_tail_bytes_over_cap_sets_header(self, log_file):
        log_file.write_text("y" * (3 * 1024 * 1024))
        resp = _get({"tail": 10 ** 12})
        assert resp.headers.get("x-log-truncated") == "true"
        assert len(resp.json()["logs"]) <= 256 * 1024

    def test_byte_cap_truncation_when_file_is_larger_than_cap(self, log_file):
        # Asked for 2000 lines, the file is much bigger than the byte cap: the tail is cut.
        log_file.write_text("".join(f"{i:08d} " + "p" * 200 + "\n" for i in range(5000)))
        resp = _get({"lines": 2000})
        assert resp.status_code == 200
        assert resp.headers.get("x-log-truncated") == "true"

    def test_missing_file_without_clamping_has_no_header(self, log_file):
        resp = _get()
        assert resp.status_code == 200
        assert resp.json() == {"logs": ""}
        assert "x-log-truncated" not in resp.headers

    def test_header_describes_the_request_even_when_the_file_is_missing(self, log_file):
        # The request itself was clamped, so the header is set; the body is still {"logs": ""}.
        resp = _get({"lines": 999999})
        assert resp.json() == {"logs": ""}
        assert resp.headers.get("x-log-truncated") == "true"


class TestBodyShapeUnchanged:
    def test_body_is_exactly_logs_key(self, log_file):
        log_file.write_text("a\n")
        assert set(_get().json().keys()) == {"logs"}
        assert isinstance(_get().json()["logs"], str)

    def test_zero_lines_is_clamped_to_one_and_not_truncated(self, log_file):
        log_file.write_text("a\nb\n")
        resp = _get({"lines": 0})
        assert resp.status_code == 200
        assert resp.json()["logs"] == "b"
        assert "x-log-truncated" not in resp.headers

    def test_endpoint_docstring_documents_the_shape(self):
        doc = ai_router.get_logs.__doc__ or ""
        assert '{"logs": str}' in doc
        assert "X-Log-Truncated" in doc
