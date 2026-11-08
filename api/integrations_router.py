from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import List, Dict, Any
# SecretVault import removed – credentials are now read from environment
from api.integration_hub import IntegrationHub, public_error_detail
import os
import re
import logging
import httpx

logger = logging.getLogger("backend")

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


def _server_error(exc: BaseException, code: str, what: str) -> HTTPException:
    """500 with a path-free message; the exception itself is logged (P1-6)."""
    return HTTPException(status_code=500, detail=public_error_detail(exc, code, what))


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
        # R12/P2-5: hub calls block (MCP subprocess up to 30 s), so they run in the threadpool.
        res = await run_in_threadpool(hub.execute_action, name, "tools/call",
                                      {"name": req.name, "arguments": req.arguments})
        return {"status": "success", "data": res}
    except Exception as e:
        raise _server_error(e, "INTEGRATION_CALL_FAILED", "Tool call")

@router.get("/", summary="List all integrations")
async def list_integrations(request: Request):
    hub: IntegrationHub = request.app.state.hub
    try:
        return await run_in_threadpool(hub.list_integrations)
    except Exception as e:
        raise _server_error(e, "INTEGRATION_LIST_FAILED", "Listing integrations")

@router.post("/", summary="Add a new integration")
async def add_integration(request: Request, req: IntegrationCreateRequest):
    hub: IntegrationHub = request.app.state.hub
    try:
        if await run_in_threadpool(hub.add_integration, req.name, req.type, req.config):
            return {"status": "success", "message": f"Integration {req.name} added"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise _server_error(e, "INTEGRATION_ADD_FAILED", "Adding the integration")

@router.post("/{name}/test", summary="Test an integration connection")
async def test_integration(name: str, request: Request):
    hub: IntegrationHub = request.app.state.hub
    try:
        integration = await run_in_threadpool(hub.get_integration, name)
    except Exception as e:
        raise _server_error(e, "INTEGRATION_READ_FAILED", "Reading the integration")
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
            # Token and URL come from the integration config; ${env:VAR} placeholders are
            # resolved from the environment. The hub has no vault (P2-19), so there is no
            # further fallback. A missing value is a 404 below.
            config = integration.get("config", {})

            def resolve_env_placeholder(val):
                """Extracts variable name from ${env:VAR_NAME} and returns os.getenv value."""
                if isinstance(val, str) and val.startswith("${env:") and val.endswith("}"):
                    var_name = val[6:-1]
                    return os.getenv(var_name)
                return val

            token = None
            url_secret = None
            token_val = config.get("token") or config.get("access_token")
            if token_val:
                resolved_token = resolve_env_placeholder(token_val)
                if resolved_token:
                    token = {"token": resolved_token}

            url_val = config.get("jira_url") or config.get("url")
            if url_val:
                resolved_url = resolve_env_placeholder(url_val)
                if resolved_url:
                    url_secret = resolved_url

            if not token or not url_secret:
                await run_in_threadpool(hub.update_status, name, "error")
                raise HTTPException(status_code=404, detail="Missing Jira credentials")

            base_url = url_secret
            # Perform a lightweight GET to the Jira "myself" endpoint to verify token
            headers = {"Authorization": f"Bearer {token.get('access_token') or token.get('token')}", "Accept": "application/json"}
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.get(f"{base_url}/rest/api/2/myself", headers=headers, timeout=10)
                except httpx.RequestError as err:
                    await run_in_threadpool(hub.update_status, name, "error")
                    logger.warning("Jira test request for %s failed: %s", name, err)
                    raise HTTPException(status_code=502, detail="Could not reach the Jira server (error code INTEGRATION_UPSTREAM_UNREACHABLE)")
                if resp.status_code == 200:
                    await run_in_threadpool(hub.update_status, name, "connected")
                    json_body = resp.json()
                    if callable(getattr(json_body, '__await__', None)):
                        json_body = await json_body
                    return {"status": "success", "data": {"principal": json_body}}
                else:
                    await run_in_threadpool(hub.update_status, name, "error")
                    detail_msg = f"Jira authentication failed (status {resp.status_code})"
                    raise HTTPException(status_code=resp.status_code, detail=detail_msg)
        # For MCP integrations, use 'tools/list' as a standard way to verify an MCP server is alive
        if integration["type"] == "mcp":
            res = await run_in_threadpool(hub.execute_action, name, "tools/list", {})
            return {"status": "success", "data": res}
        # Fallback for other native integrations – assume connection is fine
        await run_in_threadpool(hub.update_status, name, "connected")
        return {"status": "success", "data": {"message": "Native integration assumed reachable"}}
    except HTTPException as he:
        # Propagate known HTTP errors
        raise he
    except Exception as e:
        try:
            await run_in_threadpool(hub.update_status, name, "error")
        except Exception:
            logger.exception("Could not record error status for integration %s", name)
        raise _server_error(e, "INTEGRATION_TEST_FAILED", "Testing the integration")

@router.get("/{name}/tools", summary="List available tools for an MCP integration")
async def list_integration_tools(name: str, request: Request):
    hub: IntegrationHub = request.app.state.hub
    try:
        res = await run_in_threadpool(hub.execute_action, name, "tools/list", {})
        return {"status": "success", "data": res}
    except Exception as e:
        raise _server_error(e, "INTEGRATION_TOOLS_FAILED", "Listing tools")

@router.delete("/{name}", summary="Delete integration")
async def delete_integration(name: str, request: Request):
    hub: IntegrationHub = request.app.state.hub
    try:
        deleted = await run_in_threadpool(hub.delete_integration, name)
    except Exception as e:
        raise _server_error(e, "INTEGRATION_DELETE_FAILED", "Deleting the integration")
    if deleted:
        return {"status": "success", "message": f"Integration {name} deleted"}
    raise HTTPException(status_code=404, detail="Integration not found")

@router.patch("/{name}", summary="Update integration configuration")
async def update_integration(name: str, request: Request, req: IntegrationUpdateRequest):
    hub: IntegrationHub = request.app.state.hub
    try:
        await run_in_threadpool(hub.update_integration, name, req.config)
        return {"status": "success", "message": f"Integration {name} updated"}
    except ValueError as ve:
        # The hub raises ValueError for both not-found and validation
        # rejections (e.g. a non-canonical adapter_module). Not-found stays
        # 404; validation errors are 400, matching the add path.
        if str(ve) == f"Integration {name} not found":
            raise HTTPException(status_code=404, detail=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise _server_error(e, "INTEGRATION_UPDATE_FAILED", "Updating the integration")

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
