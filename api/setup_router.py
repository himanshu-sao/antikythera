"""First-run setup wizard router (D9).

Minimal skeleton so api/main.py can register it early. Routes follow.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/setup", tags=["setup"])
