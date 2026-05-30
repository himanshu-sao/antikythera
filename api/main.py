import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub
from api.secret_vault import SecretVault
from api.workflow_router import router as workflow_router
from api.brain_api import router as brain_router
from api.board_router import router as board_router
from api.integrations_router import router as integrations_router

# Assuming other routers exist, if not I'll add placeholders or just the ones I've built
app = FastAPI(title="Hermes Brain API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Directories and Services
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
vault = SecretVault(BASE_DIR)
hub = IntegrationHub(BASE_DIR, vault)
state_manager = WorkflowStateManager(BASE_DIR)

# Inject state manager into app.state for access in routers via Request
app.state.state_manager = state_manager
app.state.hub = hub
app.state.vault = vault

# Register Routers
app.include_router(workflow_router)
app.include_router(brain_router)
app.include_router(board_router)
app.include_router(integrations_router)

@app.get("/")
async def root():
    return {"message": "Hermes Brain API is running"}
