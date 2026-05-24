from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from api.secret_vault import SecretVault
from api.integration_hub import IntegrationHub
import os

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])

# Initialize persistence
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas")
vault = SecretVault(BASE_DIR)
hub = IntegrationHub(BASE_DIR, vault)

class IntegrationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., pattern=r'^(native|mcp)$')
    config: Dict[str, Any]

class SecretRequest(BaseModel):
    profile_id: str
    secrets: Dict[str, Any]

@router.get("/", summary="List all integrations")
async def list_integrations():
    return hub.list_integrations()

@router.post("/", summary="Add a new integration")
async def add_integration(request: IntegrationCreateRequest):
    if hub.add_integration(request.name, request.type, request.config):
        return {"status": "success", "message": f"Integration {request.name} added"}
    raise HTTPException(status_code=400, detail="Failed to add integration")

@router.delete("/{name}", summary="Delete integration")
async def delete_integration(name: str):
    if hub.delete_integration(name):
        return {"status": "success", "message": f"Integration {name} deleted"}
    raise HTTPException(status_code=404, detail="Integration not found")

@router.post("/secrets", summary="Store secrets for a profile")
async def store_secrets(request: SecretRequest):
    if vault.store_secret(request.profile_id, request.secrets):
        return {"status": "success", "message": f"Secrets stored for {request.profile_id}"}
    raise HTTPException(status_code=400, detail="Failed to store secrets")

@router.get("/secrets/{profile_id}", summary="Retrieve secrets for a profile (Secure)")
async def get_secrets(profile_id: str):
    # In a production system, this would be highly restricted.
    secrets = vault.get_secret(profile_id)
    if secrets:
        return secrets
    raise HTTPException(status_code=404, detail="Secrets not found for profile")
