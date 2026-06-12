import httpx
from fastapi import APIRouter, HTTPException, Request
from api.adapters.jira import JiraAdapter

router = APIRouter(prefix="/api/integrations/jira", tags=["Jira Integration"])

def get_adapter(request: Request) -> JiraAdapter:
    vault = request.app.state.vault
    return JiraAdapter(vault)

@router.get("/ticket/{ticket_id}")
async def get_ticket(ticket_id: str, request: Request):
    adapter = get_adapter(request)
    try:
        result = await adapter.fetch(ticket_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_tickets(request: Request, jql: str = ""):
    adapter = get_adapter(request)
    token = adapter.vault.get_secret("jira")
    if not token:
        raise HTTPException(status_code=401, detail="Jira token not found")
    headers = {
        "Authorization": f"Bearer {token.get('access_token') or token.get('token')}",
        "Accept": "application/json"
    }
    params = {"jql": jql} if jql else {}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://your-domain.atlassian.net/rest/api/3/search",
            headers=headers,
            params=params,
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized")
        resp.raise_for_status()
        return resp.json()

@router.post("/transition")
async def transition_issue(*, request: Request, payload: dict):
    # Expected payload: {"id": "TICKET-123", "transition": "Done"}
    issue_id = payload.get("id")
    transition = payload.get("transition")
    if not issue_id or not transition:
        raise HTTPException(status_code=400, detail="Missing id or transition")
    adapter = get_adapter(request)
    token = adapter.vault.get_secret("jira")
    if not token:
        raise HTTPException(status_code=401, detail="Jira token not found")
    headers = {
        "Authorization": f"Bearer {token.get('access_token') or token.get('token')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = {"transition": {"id": transition}}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://your-domain.atlassian.net/rest/api/3/issue/{issue_id}/transitions",
            headers=headers,
            json=data,
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized")
        resp.raise_for_status()
        return {"status": "transitioned", "response": resp.json()}

@router.post("/assign")
async def assign_issue(request: Request, payload: dict):
    # Expected payload: {"id": "TICKET-123", "assignee": "user@example.com"}
    issue_id = payload.get("id")
    assignee = payload.get("assignee")
    if not issue_id or not assignee:
        raise HTTPException(status_code=400, detail="Missing id or assignee")
    adapter = get_adapter(request)
    token = adapter.vault.get_secret("jira")
    if not token:
        raise HTTPException(status_code=401, detail="Jira token not found")
    headers = {
        "Authorization": f"Bearer {token.get('access_token') or token.get('token')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = {"fields": {"assignee": {"name": assignee}}}
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"https://your-domain.atlassian.net/rest/api/3/issue/{issue_id}",
            headers=headers,
            json=data,
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized")
        resp.raise_for_status()
        return {"status": "assigned", "response": resp.json()}

@router.post("/comment")
async def comment_issue(request: Request, payload: dict):
    # Expected payload: {"id": "TICKET-123", "comment": "Your comment text"}
    issue_id = payload.get("id")
    comment = payload.get("comment")
    if not issue_id or not comment:
        raise HTTPException(status_code=400, detail="Missing id or comment")
    adapter = get_adapter(request)
    token = adapter.vault.get_secret("jira")
    if not token:
        raise HTTPException(status_code=401, detail="Jira token not found")
    headers = {
        "Authorization": f"Bearer {token.get('access_token') or token.get('token')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = {"body": comment}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://your-domain.atlassian.net/rest/api/3/issue/{issue_id}/comment",
            headers=headers,
            json=data,
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized")
        resp.raise_for_status()
        return {"status": "commented", "response": resp.json()}
