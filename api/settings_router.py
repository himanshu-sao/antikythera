"""D14 ``/api/settings`` router: list effective settings and patch them.

Registered by ``api/main.py`` under the D1 bearer-token dependency. Secret-bearing
values (Slack webhook, API token) are not stored here and are never returned.
"""
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from api.settings_store import (
    SettingsValidationError,
    effective_settings,
    save_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings() -> Dict[str, Any]:
    """Every setting with value, default, bounds, source and restart_required."""
    return {"settings": effective_settings()}


@router.patch("")
async def patch_settings(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Validate a partial body, write it atomically, return the new effective values.

    A ``null`` value resets that key to its default. Unknown keys and
    out-of-bounds values are rejected with HTTP 422 and nothing is written.
    """
    try:
        settings = save_settings(body)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    return {"settings": settings}
