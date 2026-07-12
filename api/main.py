import os
import asyncio
# Ensure a default asyncio event loop exists for any code that calls get_event_loop()
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure the latest version of brain_api is loaded (in case it was imported before code changes)
import importlib, sys
if 'api.brain_api' in sys.modules:
    importlib.reload(sys.modules['api.brain_api'])

# Helper to access the current state manager (allows test overrides)

def get_state_manager():
    """Return the current StateManager instance.
    Test code can replace the module‑level ``state_manager`` variable and this
    function will always return the latest value.
    """
    return state_manager

from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub
# SecretVault removed – credentials now come from environment variables
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
app = FastAPI(title="Antikythera API")


# Enable CORS for frontend development.
# allow_origins=["*"] cannot be combined with allow_credentials=True (per spec,
# browsers reject the response), and the UI does not send cookies/credentials,
# so credentials are left disabled here. For a production deploy, set explicit
# origins and re-enable credentials only if actually needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Directories and Services
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
# No vault – credentials are read directly from environment variables via placeholders
hub = IntegrationHub(BASE_DIR)
state_manager = WorkflowStateManager(BASE_DIR)
escalator = EscalationManager(state_manager)
engine = ExecutionEngine(state_manager, hub, escalator)

# Inject core services into app.state for routers
app.state.state_manager = state_manager
app.state.hub = hub
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
    return {"message": "Antikythera API is running"}
