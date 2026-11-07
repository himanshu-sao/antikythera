"""D14 settings router (minimal placeholder; full implementation follows)."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings() -> dict:
    return {}
