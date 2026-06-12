import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub
from api.secret_vault import SecretVault
from api.escalation_manager import EscalationManager
from api.execution_engine import ExecutionEngine
from api.automation_router import router as automation_router
from api.skill_router import router as skill_router
from api.pipeline_router import router as pipeline_router
from api.brain_api import router as brain_router
from api.board_router import router as board_router
from api.integrations_router import router as integrations_router
from api.jira_router import router as jira_router
from api.orchestrator_router import router as orchestrator_router
from api.engine_router import router as engine_router
from api.routers.ai_engine_config_router import router as ai_engine_config_router

# Assuming other routers exist, if not I'll add placeholders or just the ones I've built
# Include Jira integration routes
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
escalator = EscalationManager(state_manager)
engine = ExecutionEngine(state_manager, hub, escalator)

# Inject state manager into app.state for access in routers via Request
app.state.state_manager = state_manager
app.state.hub = hub
app.state.vault = vault
app.state.escalator = escalator
app.state.engine = engine

# Register Routers
app.include_router(automation_router, prefix="/api/automation", tags=["Automation Compiler"])
app.include_router(skill_router, prefix="/api/skills", tags=["Skill Brainstormer"])
app.include_router(pipeline_router, prefix="/api/pipelines", tags=["Pipeline Management"])
app.include_router(brain_router)
app.include_router(board_router)
app.include_router(integrations_router)
app.include_router(jira_router)
app.include_router(orchestrator_router)
app.include_router(engine_router)
app.include_router(ai_engine_config_router, prefix="/api/ai-engine", tags=["AI Engine Configuration"])

# Mount static files for requirements and documentation
app.mount("/docs", StaticFiles(directory=BASE_DIR), name="docs")

@app.get("/")
async def root():
    return {"message": "Hermes Brain API is running"}
