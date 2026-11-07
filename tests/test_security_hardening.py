"""Security hardening regression tests (Worker D items SEC-2, SEC-5, SEC-9, SEC-10, SEC-13).

Rules for this file: never assert on or print secret values / response bodies of
secret-bearing files; assert on status codes and booleans only.
"""
import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from api.main import app


# --------------------------------------------------------------------------
# SEC-2: no static mount of the automation-ideas data directory
# --------------------------------------------------------------------------
class TestNoDataDirStaticMount:
    @pytest.mark.parametrize(
        "path",
        [
            "/docs/.vault.key",
            "/docs/secrets.vault",
            "/docs/integrations.json",
            "/docs/pipeline-state.json",
            "/docs/%2e%2e/api/main.py",
            "/docs/../.env",
        ],
    )
    def test_secret_files_not_served(self, path):
        client = TestClient(app)
        resp = client.get(path)
        assert resp.status_code != 200, f"{path} must not be served (status={resp.status_code})"

    def test_no_staticfiles_mount_on_docs(self):
        mounts = [r for r in app.routes if isinstance(r, Mount) and r.path == "/docs"]
        assert mounts == [], "a StaticFiles mount at /docs must not exist"

    def test_no_staticfiles_mount_anywhere_serving_data_dir(self):
        import os
        from api.main import BASE_DIR
        for r in app.routes:
            sub = getattr(r, "app", None)
            directory = getattr(sub, "directory", None)
            if directory is not None:
                assert os.path.realpath(directory) != os.path.realpath(BASE_DIR)


# --------------------------------------------------------------------------
# SEC-10: /api/ai-engine/logs resolves backend.log from the repo root, caps
# lines (default 200, max 2000) and reads only a bounded tail of the file.
# --------------------------------------------------------------------------
import os as _os

from api.routers import ai_engine_config_router as _ai_router


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    target = tmp_path / "backend.log"
    monkeypatch.setattr(_ai_router, "BACKEND_LOG_PATH", str(target))
    return target


def _get_logs(params=None):
    return TestClient(app).get("/api/ai-engine/logs", params=params or {})


class TestLogsEndpointBounds:
    def test_path_is_repo_root_not_cwd(self, monkeypatch, tmp_path):
        expected = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(_ai_router.__file__)))), "backend.log")
        assert _os.path.realpath(_ai_router.BACKEND_LOG_PATH) == _os.path.realpath(expected)
        monkeypatch.chdir(tmp_path)
        assert _os.path.realpath(_ai_router._resolve_backend_log_path()) == _os.path.realpath(expected)

    def test_returns_last_lines_default_200(self, log_file):
        log_file.write_text("".join(f"line {i}\n" for i in range(1000)))
        body = _get_logs().json()["logs"]
        lines = body.splitlines()
        assert len(lines) == 200
        assert lines[-1] == "line 999"
        assert lines[0] == "line 800"

    def test_lines_param_is_respected(self, log_file):
        log_file.write_text("".join(f"line {i}\n" for i in range(50)))
        lines = _get_logs({"lines": 5}).json()["logs"].splitlines()
        assert lines == [f"line {i}" for i in range(45, 50)]

    def test_lines_param_clamped_to_max_2000(self, log_file):
        log_file.write_text("".join(f"line {i}\n" for i in range(5000)))
        lines = _get_logs({"lines": 999999}).json()["logs"].splitlines()
        assert len(lines) == 2000

    def test_negative_or_zero_lines_rejected_or_clamped(self, log_file):
        log_file.write_text("a\nb\n")
        resp = _get_logs({"lines": 0})
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert len(resp.json()["logs"].splitlines()) >= 1

    def test_huge_file_reads_only_bounded_tail(self, log_file, monkeypatch):
        # 10 MiB file; the endpoint must not read it whole.
        big = ("x" * 99 + "\n") * (10 * 1024 * 1024 // 100)
        log_file.write_text(big)
        read_sizes = []
        real_open = open

        class Spy:
            def __init__(self, f):
                self._f = f

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self._f.close()

            def read(self, n=-1):
                data = self._f.read(n)
                read_sizes.append(len(data))
                return data

            def seek(self, *a):
                return self._f.seek(*a)

            def tell(self):
                return self._f.tell()

        def spy_open(path, mode="r", *a, **kw):
            f = real_open(path, mode, *a, **kw)
            return Spy(f) if str(path) == str(log_file) and "b" in mode else f

        monkeypatch.setattr("builtins.open", spy_open)
        resp = _get_logs({"lines": 2000})
        assert resp.status_code == 200
        assert sum(read_sizes) <= 256 * 1024 + 4096, f"read {sum(read_sizes)} bytes"

    def test_ui_tail_param_does_not_bypass_byte_cap(self, log_file):
        log_file.write_text("y" * (3 * 1024 * 1024))
        resp = _get_logs({"tail": 1048576})
        assert resp.status_code == 200
        assert len(resp.json()["logs"]) <= 256 * 1024

    def test_missing_file_returns_empty(self, log_file):
        assert not log_file.exists()
        resp = _get_logs()
        assert resp.status_code == 200
        assert resp.json()["logs"] == ""

    def test_tail_bytes_huge_value_is_capped(self, log_file):
        log_file.write_text("z\n" * 10)
        resp = _get_logs({"tail": 10 ** 12})
        assert resp.status_code == 200
