from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from api.secret_vault import SecretVault
from api.integration_hub import IntegrationHub
import os

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])

class IntegrationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., pattern=r'^(native|mcp)$')
    config: Dict[str, Any]

class SecretRequest(BaseModel):
    profile_id: str
    secrets: Dict[str, Any]

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

@router.post("/{name}/call", summary="Call a specific tool")
async def call_tool(name: str, request: Request, req: ToolCallRequest):
    hub: IntegrationHub = request.app.state.hub
    try:
        # For MCP, the action is 'tools/call' and the tool name/args are in the params
        res = hub.execute_action(name, "tools/call", {"name": req.name, "arguments": req.arguments})
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", summary="List all integrations")
async def list_integrations(request: Request):
    hub: IntegrationHub = request.app.state.hub
    return hub.list_integrations()

@router.post("/", summary="Add a new integration")
async def add_integration(request: Request, req: IntegrationCreateRequest):
    hub: IntegrationHub = request.app.state.hub
    try:
        if hub.add_integration(req.name, req.type, req.config):
            return {"status": "success", "message": f"Integration {req.name} added"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{name}/test", summary="Test an integration connection")
async def test_integration(name: str, request: Request):
    hub: IntegrationHub = request.app.state.hub
    try:
        # Use 'tools/list' as a standard way to verify an MCP server is alive
        res = hub.execute_action(name, "tools/list", {})
        return {"status": "success", "data": res}
    except Exception as e:
        # Note: We're catching everything here to ensure even unexpected errors 
        # are returned as a 500.
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{name}/tools", summary="List available tools for an MCP integration")
async def list_integration_tools(name: str, request: Request):
    hub: IntegrationHub = request.app.state.hub
    try:
        res = hub.execute_action(name, "tools/list", {})
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{name}", summary="Delete integration")
async def delete_integration(name: str, request: Request):
    hub: IntegrationHub = request.app.state.hub
    if hub.delete_integration(name):
        return {"status": "success", "message": f"Integration {name} deleted"}
    raise HTTPException(status_code=404, detail="Integration not found")

@router.post("/secrets", summary="Store secrets for a profile")
async def store_secrets(request: Request, req: SecretRequest):
    vault: SecretVault = request.app.state.vault
    try:
        if vault.store_secret(req.profile_id, req.secrets):
            return {"status": "success", "message": f"Secrets stored for {req.profile_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=400, detail="Failed to store secrets")

@router.get("/secrets/{profile_id}", summary="Retrieve secrets for a profile (Secure)")
async def get_secrets(profile_id: str, request: Request):
    vault: SecretVault = request.app.state.vault
    secrets = vault.get_secret(profile_id)
    if secrets:
        return secrets
    raise HTTPException(status_code=404, detail="Secrets not found for profile")
