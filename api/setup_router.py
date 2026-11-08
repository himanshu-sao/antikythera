"""First-run setup wizard router (D9, P0-1 setup-secret gate).

Routes under ``/api/setup`` (no token dependency, except DELETE):

- ``GET /status``: typed setup items, names and presence only, never values.
  Also reports ``setup_secret_required`` and ensures the one-time setup secret
  exists while setup is open, so the wizard can ask for it up front.
- ``POST /config``: partial map of settings, written to ``.ai_env`` (secrets) or
  ``.env`` (plain) in the config directory. Requires the ``X-Setup-Secret``
  header matching the setup secret (constant-time compare).
- ``POST /complete``: writes the ``.setup_complete`` marker, deletes the setup
  secret and, when no ``ANTIKYTHERA_API_TOKEN`` is set, returns the generated
  API token once. Also requires ``X-Setup-Secret``.
- ``DELETE /complete``: reopens setup; requires the bearer token (not the
  secret).

The old loopback-only peer-address gate is gone (P0-1): under Docker NAT or a
reverse proxy the backend never sees 127.0.0.1, so it locked out the
legitimate first-run user. Possession of the setup secret — a 0600 file in the
server's config directory — is the proof of local access instead. Once the
marker exists the GET/POST routes return 404.
"""

from __future__ import annotations

import hmac
import os
import re
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from api.security import (
    TOKEN_ENV_VAR,
    SETUP_MARKER_FILENAME,
    config_dir,
    delete_setup_secret,
    get_or_create_setup_secret,
    get_or_create_token,
    setup_secret_exists,
    token_file_path,
)
from api.services.ai_engine_config import _format_env_line, _validate_env_value, get_ai_engine_config

router = APIRouter(prefix="/api/setup", tags=["setup"])

MARKER_FILENAME = SETUP_MARKER_FILENAME
ENV_FILENAME = ".env"
DEFAULT_PORT = "18006"
DEFAULT_CORS_ORIGINS = "http://localhost:15173"
DATA_DIR_NAME = "automation-ideas"

# Known provider keys (names only). Matches the api_key_env values in the default
# AI engine config plus the OpenAI and Ollama keys documented in .env.example.
PROVIDER_KEY_NAMES: Tuple[str, ...] = (
    "GOOGLE_API_KEY",
    "IBM_BOB_API_KEY",
    "NVIDIA_API_KEY",
    "OLLAMA_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
)
SLACK_KEY = "ANTIKYTHERA_SLACK_WEBHOOK"
SLACK_FALLBACK_KEY = "ISV_SLACK_WEBHOOK_URL"  # D10 fallback; presence only
JIRA_BASE_KEY = "JIRA_BASE_URL"
JIRA_PAT_KEY = "JIRA_PAT"
PORT_KEY = "PORT"
CORS_KEY = "ANTIKYTHERA_CORS_ORIGINS"
BACKUP_KEY = "ANTIKYTHERA_BACKUP_DIR"

# Routing: secrets file (.ai_env) vs plain file (.env). The PAT is a credential
# (D9: "Jira and non-secret settings" go to .env), so it goes to the secrets file.
SECRETS_FILE_KEYS = frozenset(PROVIDER_KEY_NAMES + (SLACK_KEY, JIRA_PAT_KEY))
PLAIN_FILE_KEYS = frozenset((JIRA_BASE_KEY, PORT_KEY, CORS_KEY, BACKUP_KEY))
SETTABLE_KEYS = SECRETS_FILE_KEYS | PLAIN_FILE_KEYS
MASKED_KEYS = frozenset(PROVIDER_KEY_NAMES + (SLACK_KEY, JIRA_PAT_KEY))

MAX_VALUE_LEN = 2048
_PORT_RE = re.compile(r"^[0-9]{1,5}$")

RATE_LIMIT_MAX_CALLS = 20
RATE_LIMIT_WINDOW_S = 60.0
_rate_lock = threading.Lock()
_rate_hits: "deque[float]" = deque()

_write_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Paths, gating and rate limit
# ---------------------------------------------------------------------------

def _marker_path() -> Path:
    return config_dir() / MARKER_FILENAME


def _plain_env_path() -> Path:
    return config_dir() / ENV_FILENAME


def _secrets_env_path() -> Path:
    # Same resolution as the AI engine's safe writer (honours ANTIKYTHERA_HOME).
    return Path(get_ai_engine_config()._persistent_env_path())


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / DATA_DIR_NAME


def _is_complete() -> bool:
    return _marker_path().is_file()


def _token_exists() -> bool:
    path = token_file_path()
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _guard_open() -> None:
    """Gate for GET status, POST config and POST complete.

    Once the marker exists the routes do not exist (404, same body as an unknown
    path). While setup is open the routes are reachable from any address; the
    write routes are protected by the one-time setup secret instead (P0-1).
    """
    if _is_complete():
        raise HTTPException(status_code=404)


def _require_setup_secret(request: Request) -> None:
    """P0-1: gate the setup write routes on the one-time setup secret.

    The secret lives in a 0600 file in the server's config directory, so
    presenting its value proves access to the server's filesystem — the same
    trust the old loopback check tried to establish, but one that survives
    Docker NAT and reverse proxies. Compared in constant time; a single generic
    message for a missing, wrong or unavailable secret.
    """
    expected = get_or_create_setup_secret()
    supplied = request.headers.get("x-setup-secret", "")
    if (
        expected is None
        or not supplied
        or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    ):
        raise HTTPException(status_code=403, detail="Invalid setup secret")


def _check_rate_limit() -> None:
    now = time.monotonic()
    with _rate_lock:
        while _rate_hits and now - _rate_hits[0] > RATE_LIMIT_WINDOW_S:
            _rate_hits.popleft()
        if len(_rate_hits) >= RATE_LIMIT_MAX_CALLS:
            raise HTTPException(status_code=429, detail="Too many setup requests; try again shortly")
        _rate_hits.append(now)


def _reset_rate_limit() -> None:
    """Test helper: forget recorded config POSTs."""
    with _rate_lock:
        _rate_hits.clear()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _item(
    item_id: str,
    kind: str,
    name: str,
    label: str,
    ok: bool,
    state: str,
    *,
    settable: bool = False,
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "kind": kind,
        "name": name,
        "label": label,
        "ok": ok,
        "state": state,
        "settable": settable,
        "secret": name in MASKED_KEYS,
    }


def _data_dir_state() -> str:
    path = _data_dir()
    if not path.is_dir():
        return "missing"
    return "writable" if os.access(path, os.W_OK) else "read_only"


def _status_items() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    env_present = _plain_env_path().is_file()
    items.append(_item("env_file", "env_file", ENV_FILENAME, "Environment file",
                       env_present, "present" if env_present else "missing"))

    for key in PROVIDER_KEY_NAMES:
        is_set = bool(_env(key))
        items.append(_item(key, "provider_key", key, "Provider API key",
                           is_set, "set" if is_set else "unset", settable=True))

    for key, label in ((JIRA_BASE_KEY, "Jira base URL"), (JIRA_PAT_KEY, "Jira personal access token")):
        is_set = bool(_env(key))
        items.append(_item(key, "jira", key, label, is_set, "set" if is_set else "unset", settable=True))

    slack_set = bool(_env(SLACK_KEY) or _env(SLACK_FALLBACK_KEY))
    items.append(_item(SLACK_KEY, "slack", SLACK_KEY, "Slack webhook",
                       slack_set, "set" if slack_set else "unset", settable=True))

    token_generated = bool(_env(TOKEN_ENV_VAR)) or _token_exists()
    items.append(_item("api_token", "api_token", "api_token", "API token",
                       token_generated, "generated" if token_generated else "missing"))

    port_custom = _env(PORT_KEY) not in ("", DEFAULT_PORT)
    items.append(_item(PORT_KEY, "port", PORT_KEY, "API port",
                       True, "custom" if port_custom else "default", settable=True))

    cors_custom = _env(CORS_KEY) not in ("", DEFAULT_CORS_ORIGINS)
    items.append(_item(CORS_KEY, "origins", CORS_KEY, "Allowed UI origins",
                       True, "custom" if cors_custom else "default", settable=True))

    data_state = _data_dir_state()
    items.append(_item("data_dir", "data_dir", DATA_DIR_NAME, "Data directory",
                       data_state == "writable", data_state))

    backup_set = bool(_env(BACKUP_KEY))
    items.append(_item(BACKUP_KEY, "backup_dir", BACKUP_KEY, "Backup directory",
                       backup_set, "configured" if backup_set else "unset", settable=True))

    return items


# ---------------------------------------------------------------------------
# Config writes
# ---------------------------------------------------------------------------

def _validate_config(body: Dict[str, Any]) -> Dict[str, str]:
    """Return the cleaned updates. Errors name the key only, never the value."""
    updates: Dict[str, str] = {}
    for key, raw in body.items():
        if key not in SETTABLE_KEYS:
            raise HTTPException(status_code=422, detail="Unknown setting name")
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise HTTPException(status_code=422, detail=f"{key} must be a string")
        value = raw.strip()
        if not value:
            continue  # blank means "leave as is"
        if len(value) > MAX_VALUE_LEN:
            raise HTTPException(status_code=422, detail=f"{key} is too long")
        try:
            _validate_env_value(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{key} must be a single line without NUL bytes")
        if key == PORT_KEY and not (_PORT_RE.match(value) and 1 <= int(value) <= 65535):
            raise HTTPException(status_code=422, detail="PORT must be a port number from 1 to 65535")
        updates[key] = value
    return updates


def _merge_env_text(existing: str, updates: Dict[str, str]) -> str:
    """Replace every existing line for each updated key, append the rest, keep other lines verbatim.

    Every duplicate is rewritten so the last-wins value under ``source`` is the new one.
    """
    written: set = set()
    out: List[str] = []
    for line in existing.splitlines():
        stripped = line.strip()
        key = None
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
        if key and key in updates:
            out.append(_format_env_line(key, updates[key]))
            written.add(key)
        else:
            out.append(line)
    if not existing.strip():
        out.append("# Written by the Antikythera setup wizard")
    for key, value in updates.items():
        if key not in written:
            out.append(_format_env_line(key, value))
    return "\n".join(out) + "\n"


def _atomic_private_write(path: Path, text: str) -> None:
    """Temp file created O_EXCL with mode 0600, fsync, then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp), str(path))
    except BaseException:
        try:
            os.unlink(str(tmp))
        except OSError:
            pass
        raise


def _write_env_file(path: Path, updates: Dict[str, str]) -> None:
    if not updates:
        return
    # Write through a symlink to its target, so a linked .env stays a link.
    target = path.resolve() if path.is_symlink() else path
    with _write_lock:
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        _atomic_private_write(target, _merge_env_text(existing, updates))


def _write_config(updates: Dict[str, str]) -> None:
    secret_updates = {k: v for k, v in updates.items() if k in SECRETS_FILE_KEYS}
    plain_updates = {k: v for k, v in updates.items() if k in PLAIN_FILE_KEYS}
    _write_env_file(_secrets_env_path(), secret_updates)
    _write_env_file(_plain_env_path(), plain_updates)
    for key, value in updates.items():
        os.environ[key] = value


def _write_marker() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _atomic_private_write(_marker_path(), f"setup completed {stamp}\n")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
def setup_status(request: Request) -> Dict[str, Any]:
    _guard_open()
    # P0-1: make sure the one-time secret exists from the first status poll so
    # the wizard can ask for it before the first write. The response reports
    # presence only — never the value.
    get_or_create_setup_secret()
    return {
        "complete": _is_complete(),
        "items": _status_items(),
        "setup_secret_required": setup_secret_exists(),
    }


@router.post("/config")
def setup_config(request: Request, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    _guard_open()
    _require_setup_secret(request)
    _check_rate_limit()
    updates = _validate_config(body)
    _write_config(updates)
    return {"written": sorted(updates), "complete": False}


@router.post("/complete")
def setup_complete(request: Request) -> Dict[str, Any]:
    _guard_open()
    _require_setup_secret(request)
    # A token generated by this call is returned once so the wizard can show it.
    # Status never carries it, and this route is secret-gated while setup is
    # open. A token that already existed, or one supplied by the environment,
    # is not echoed.
    api_token: Optional[str] = None
    if not _env(TOKEN_ENV_VAR) and not _token_exists():
        api_token = get_or_create_token()
    _write_marker()
    # P0-1: the one-time secret has served its purpose.
    delete_setup_secret()
    return {"complete": True, "api_token": api_token}


def _bearer_required(request: Request) -> None:
    """Lazy wrapper around api.security.require_token (imported at call time)."""
    from api.security import require_token as _require_token

    _require_token(request)


@router.delete("/complete", dependencies=[Depends(_bearer_required)])
def setup_reopen() -> Dict[str, Any]:
    try:
        _marker_path().unlink()
    except FileNotFoundError:
        pass
    return {"complete": False}
