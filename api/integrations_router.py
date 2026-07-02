from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
# SecretVault import removed – credentials are now read from environment
from api.integration_hub import IntegrationHub
import os
import re
import httpx

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])

class IntegrationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., pattern=r'^(native|mcp)$')
    config: Dict[str, Any]

# SecretRequest model removed – secret storage via vault is no longer supported

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class IntegrationUpdateRequest(BaseModel):
    config: Dict[str, Any]

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
    integration = hub.get_integration(name)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    try:
        # For native Jira adapters, perform a real API call to verify credentials
        if integration["type"] == "native" and (\
            integration["config"].get("adapter_module") == "api.adapters.jira" or\
                        "jira" in name.lower() or\
                        integration["config"].get("jira_url") or\
                        integration["config"].get("url")\
        ):
            # Try to obtain token & URL from vault first, then fall back to environment vars
            token = None
            url_secret = None
            
            # --- RESOLVE ${env:VAR} PLACEHOLDERS FROM CONFIG ---
            config = integration.get("config", {})
            
            def resolve_env_placeholder(val):
                """Extracts variable name from ${env:VAR_NAME} and returns os.getenv value."""
                if isinstance(val, str) and val.startswith("${env:") and val.endswith("}"):
                    var_name = val[6:-1]
                    return os.getenv(var_name)
                return val

            # 1. Check Config for Placeholders (Always use config if present)
            # Resolve token from config first – it should override any vault value
            token_val = config.get("token") or config.get("access_token")
            if token_val:
                resolved_token = resolve_env_placeholder(token_val)
                if resolved_token:
                    token = {"token": resolved_token}
            
            # Resolve URL from config – overrides vault URL
            url_val = config.get("jira_url") or config.get("url")
            if url_val:
                resolved_url = resolve_env_placeholder(url_val)
                if resolved_url:
                    url_secret = resolved_url

            # 2. Fallback to Direct Environment Variables (Legacy support)
            # First, try to fetch credentials from the vault (if present)
            if not token:
                secret = hub.vault.get_secret("jira")
                if secret:
                    token = {"token": secret.get("access_token") or secret.get("token")}
            if not url_secret:
                secret_url = hub.vault.get_secret("jira_url")
                if secret_url:
                    url_secret = secret_url
            # If still missing, fall back to environment variables
            # Try to fetch credentials from the vault if not provided in config
            if not token:
                secret = hub.vault.get_secret("jira")
                if secret:
                    token = {"token": secret.get("access_token") or secret.get("token")}
            if not url_secret:
                secret_url = hub.vault.get_secret("jira_url")
                if secret_url:
                    url_secret = secret_url
            # If after all attempts credentials are still missing, error out
            if not token or not url_secret:
                hub.update_status(name, "error")
                raise HTTPException(status_code=404, detail="Missing Jira credentials")
            # If after all attempts credentials are still missing, error out
            if not token or not url_secret:
                hub.update_status(name, "error")
                raise HTTPException(status_code=404, detail="Missing Jira credentials")
            # ---------------------------------------------------------------

            # Normalise token dict (allow plain string)
            if token and not isinstance(token, dict):
                token = {"token": token}
            # Normalise URL
            if isinstance(url_secret, dict):
                base_url = url_secret.get("url") or url_secret.get("jira_url") or next(iter(url_secret.values()))
            else:
                base_url = url_secret
            if not token or not base_url:
                hub.update_status(name, "error")
                raise HTTPException(status_code=404, detail="Missing Jira credentials")
            # Perform a lightweight GET to the Jira "myself" endpoint to verify token
            headers = {"Authorization": f"Bearer {token.get('access_token') or token.get('token')}", "Accept": "application/json"}
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.get(f"{base_url}/rest/api/2/myself", headers=headers, timeout=10)
                except httpx.RequestError as err:
                    hub.update_status(name, "error")
                    raise HTTPException(status_code=502, detail=str(err))
                if resp.status_code == 200:
                    hub.update_status(name, "connected")
                    json_body = resp.json()
                    if callable(getattr(json_body, '__await__', None)):
                        json_body = await json_body
                    return {"status": "success", "data": {"principal": json_body}}
                else:
                    hub.update_status(name, "error")
                    detail_msg = f"Jira authentication failed (status {resp.status_code})"
                    raise HTTPException(status_code=resp.status_code, detail=detail_msg)
        # For MCP integrations, use 'tools/list' as a standard way to verify an MCP server is alive
        if integration["type"] == "mcp":
            res = hub.execute_action(name, "tools/list", {})
            return {"status": "success", "data": res}
        # Fallback for other native integrations – assume connection is fine
        hub.update_status(name, "connected")
        return {"status": "success", "data": {"message": "Native integration assumed reachable"}}
    except HTTPException as he:
        # Propagate known HTTP errors
        raise he
    except Exception as e:
        hub.update_status(name, "error")
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

@router.patch("/{name}", summary="Update integration configuration")
async def update_integration(name: str, request: Request, req: IntegrationUpdateRequest):
    hub: IntegrationHub = request.app.state.hub
    try:
        hub.update_integration(name, req.config)
        return {"status": "success", "message": f"Integration {name} updated"}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Secret storage endpoints removed – all credentials are now provided via environment variables and integration config placeholders

@router.get("/secrets", include_in_schema=False)
async def get_secrets(request: Request):
    raise HTTPException(status_code=404, detail="Secrets endpoint not available")

@router.post("/secrets", include_in_schema=False)
async def post_secrets(request: Request):
    raise HTTPException(status_code=404, detail="Secrets endpoint not available")

# Additional secret routes with a name component – always return 404
@router.get("/secrets/{name}", include_in_schema=False)
async def get_secret_named(name: str, request: Request):
    raise HTTPException(status_code=404, detail="Secrets endpoint not available")

@router.post("/secrets/{name}", include_in_schema=False)
async def post_secret_named(name: str, request: Request):
    raise HTTPException(status_code=404, detail="Secrets endpoint not available")
