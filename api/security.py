"""Shared bearer-token authentication for the Antikythera API (decision D1).

Token resolution order, evaluated lazily on every call so a value set after
import still works:

1. ``ANTIKYTHERA_API_TOKEN`` environment variable.
2. ``api_token`` file in the config directory (``$ANTIKYTHERA_HOME``, default
   ``~/.antikythera``).
3. A freshly generated ``secrets.token_urlsafe(32)`` value, written atomically
   to that file with mode 0600. Only the file path is logged, never the value.
"""
from __future__ import annotations

import hmac
import logging
import os
import secrets
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger("antikythera.security")

TOKEN_ENV_VAR = "ANTIKYTHERA_API_TOKEN"
TOKEN_FILENAME = "api_token"

# First-run setup wizard (P0-1). The one-time setup secret gates the setup
# write routes instead of the old loopback-only peer check (which rejected
# every legitimate client behind Docker NAT / a reverse proxy).
SETUP_MARKER_FILENAME = ".setup_complete"
SETUP_SECRET_FILENAME = "setup_secret"

_lock = threading.Lock()
_setup_secret_lock = threading.Lock()


def config_dir() -> Path:
    """``$ANTIKYTHERA_HOME`` when set, else ``<home>/.antikythera``."""
    override = os.environ.get("ANTIKYTHERA_HOME", "").strip()
    if override:
        return Path(os.path.expanduser(override))
    return Path.home() / ".antikythera"


def token_file_path() -> Path:
    return config_dir() / TOKEN_FILENAME


def _read_token_file(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return value or None


def _write_token_file(path: Path, token: str) -> None:
    """Atomic write (temp file in the same directory, then rename), mode 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".api_token.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(token + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def get_or_create_token() -> str:
    """Return the API token, generating and persisting one if none exists."""
    env_value = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_value:
        return env_value

    path = token_file_path()
    with _lock:
        existing = _read_token_file(path)
        if existing:
            return existing
        token = secrets.token_urlsafe(32)
        _write_token_file(path, token)
        logger.info("Generated API token and wrote it to %s", path)
        return token


# ---------------------------------------------------------------------------
# One-time setup secret (P0-1, fix-session contract 2026-11-08)
# ---------------------------------------------------------------------------

def setup_marker_path() -> Path:
    """Path of the ``.setup_complete`` marker in the config directory."""
    return config_dir() / SETUP_MARKER_FILENAME


def setup_secret_file_path() -> Path:
    """Path of the ``setup_secret`` file in the config directory."""
    return config_dir() / SETUP_SECRET_FILENAME


def setup_secret_exists() -> bool:
    """True when a non-empty setup secret file exists (presence only)."""
    return _read_token_file(setup_secret_file_path()) is not None


def get_or_create_setup_secret() -> Optional[str]:
    """Return the one-time setup secret, creating it while setup is open.

    Like the API token: a ``secrets.token_urlsafe(24)`` value written atomically
    to ``setup_secret`` in the config directory (``$ANTIKYTHERA_HOME``, default
    ``~/.antikythera``) with mode 0600. Created only while the
    ``.setup_complete`` marker is absent; the setup router deletes it on
    successful completion. Only the file path is logged, never the value.
    """
    if setup_marker_path().is_file():
        return None
    path = setup_secret_file_path()
    with _setup_secret_lock:
        existing = _read_token_file(path)
        if existing:
            return existing
        secret = secrets.token_urlsafe(24)
        _write_token_file(path, secret)
        logger.info("Generated first-run setup secret and wrote it to %s", path)
        return secret


def delete_setup_secret() -> None:
    """Remove the setup secret file (idempotent; called on completion)."""
    try:
        setup_secret_file_path().unlink()
    except FileNotFoundError:
        pass


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_token(request: Request) -> None:
    """FastAPI dependency: require ``Authorization: Bearer <token>``."""
    header = request.headers.get("authorization", "")
    scheme, _, supplied = header.partition(" ")
    supplied = supplied.strip()
    if scheme.lower() != "bearer" or not supplied:
        raise _unauthorized("Missing bearer token")
    expected = get_or_create_token()
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise _unauthorized("Invalid bearer token")
