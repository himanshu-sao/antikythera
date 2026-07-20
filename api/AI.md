# Antikythera API Briefing

**Purpose**: Technical context for the FastAPI backend and the data persistence layer.

---

## API Architecture
- **Framework**: FastAPI (Python 3.11+)
- **App entry point**: `api/main.py`
- **Pattern**: Router-based architecture. Note: most routers are flat files in `api/`, not in `api/routers/`.

### Registered Routers (from `main.py`)

| Router File | Prefix | Tag |
|---|---|---|
| `automation_router.py` | `/api/automation` | Automation Compiler |
| `skill_router.py` | `/api/skills` | Skill Brainstormer |
| `pipeline_router.py` | `/api/pipelines` | Pipeline Management |
| `brain_api.py` | (root) | — |
| `board_router.py` | (root) | — |
| `integrations_router.py` | (root) | — |
| `jira_router.py` | (root) | — |
| `orchestrator_router.py` | (root) | — |
| `engine_router.py` | (root) | — |
| `trigger_router.py` | (root) | — |
| `builders/ai_engine_config_router.py` | `/api/ai-engine` | AI Engine Config |

Additionally, `/docs` serves the `automation-ideas/` directory as static files.

## State Management
The system has **two generations** of state management:

### New (preferred): Managers hierarchy
- **`WorkflowStateManager`** (`api/workflow_state_manager.py`): Facade that delegates to specialized managers.
- **`BaseJSONManager`** (`api/managers/base.py`): Abstract base with `filelock.FileLock` and atomic writes (`temp → os.rename`).
- **`KanbanStateManager`** (`api/managers/kanban_state_manager.py`): Pipeline board state.
- **`TemplateManager`**, **`RunManager`**, **`BindingManager`**: Workflow-specific state.

### Legacy (do not extend)
- **`StateManager`** (`api/state_manager.py`): Monolithic class. Still importable but should not be used for new features.

### Single Source of Truth
- `automation-ideas/pipeline-state.json` — Kanban board state
- `automation-ideas/workflow_templates.json` — Workflow template definitions
- `automation-ideas/workflow_runs.json` — Workflow execution history

All state files use `filelock` for concurrency safety and atomic temp→rename writes.

## Integration Hub
- **Adapter Pattern**: All external systems (Jira, GitHub, etc.) extend `api/adapters/base.py`.
- **Implementations**: `jira.py`, `github.py`, `internal.py`, `bob_shell.py`
- **Consistency**: Adapters must normalize external data into the internal Antikythera format.
- **SecretVault** (`api/secret_vault.py`): **Exists but is currently unused.** Main.py comments: "SecretVault removed — credentials now come from environment variables." The vault implements Fernet encryption but is not wired into the app.

## Execution Layer
- **`execution_engine.py`**: Step-by-step workflow runner with retry logic.
- **`api/executors/safe_executor.py`**: Sandboxed code execution.
- **`operator_registry.py`**: Routes skill operations to adapters.
- **`retry_manager.py`**: Transient/permanent failure classification and retry scheduling.
- **`trigger_manager.py`**: Event, schedule, and webhook trigger handling.
- **`scheduler.py`**: APScheduler-based background polling.

## Development Guardrails
- **Async First**: Use `async def` for all route handlers to prevent blocking the event loop.
- **Pydantic Validation**: All API inputs/outputs must be strictly typed using Pydantic models (`api/models/`).
- **Error Handling**: Use custom FastAPI exceptions to return consistent error schemas to the frontend.
- **No Direct State Writes**: Always use the `WorkflowStateManager` or `BaseJSONManager` subclasses. Never write directly to JSON files.
