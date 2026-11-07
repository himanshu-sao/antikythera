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
