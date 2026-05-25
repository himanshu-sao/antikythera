import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.workflow_router import router as workflow_router
from api.integrations_router import router as integrations_router
from api.trigger_router import router as trigger_router
from api.builder_router import router as builder_router
from api.board_router import router as board_router
from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub
from api.secret_vault import SecretVault

app = FastAPI(title="Antikythera Kanban API")

# Initialize dependencies
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas")
vault = SecretVault(BASE_DIR)
hub = IntegrationHub(BASE_DIR, vault)
state_manager = WorkflowStateManager(BASE_DIR)

# Set dependencies for trigger router
from api.trigger_router import set_trigger_deps
set_trigger_deps(state_manager, hub)

# Register Routers
app.include_router(workflow_router)
app.include_router(integrations_router)
app.include_router(trigger_router)
app.include_router(builder_router)
app.include_router(board_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    try:
        _ = state_manager.load_state()
        return {"status": "healthy", "service": "antikythera-kanban-api"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
