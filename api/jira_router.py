import httpx
from fastapi import APIRouter, HTTPException, Request
from api.adapters.jira import JiraAdapter

router = APIRouter(prefix="/api/integrations/jira", tags=["Jira Integration"])

def get_adapter(request: Request) -> JiraAdapter:
    # No vault needed; adapter reads from environment variables
    return JiraAdapter(None)

@router.get("/ticket/{ticket_id}")
async def get_ticket(ticket_id: str, request: Request):
    adapter = get_adapter(request)
    try:
        result = await adapter.fetch(ticket_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
