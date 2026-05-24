# 🤖 Antikythera API Briefing

**Purpose**: Technical context for the FastAPI backend and the data persistence layer.

---

## 🏗 API Architecture
- **Framework**: FastAPI (Python 3.9+)
- **Pattern**: Router-based architecture.
- **Core Routers**:
    - `board_router.py`: Kanban board state and item management.
    - `workflow_router.py`: Workflow template and run management.
    - `integrations_router.py`: External system connectivity.
    - `trigger_router.py`: Event and schedule trigger handling.

## 💾 State Management
- **Single Source of Truth**: `automation-ideas/pipeline-state.json`.
- **`StateManager`**: Handles all I/O. Uses `filelock` to prevent corruption during concurrent agent/API writes.
- **Atomic Writes**: All updates must follow the "Write to Temp $\rightarrow$ Rename" pattern to prevent partial writes on crash.

## 🔌 Integration Hub
- **Adapter Pattern**: All external systems (GitHub, Jira, etc.) are implemented via `api/adapters/base.py`.
- **Consistency**: Adapters must normalize external data into the internal Antikythera format before passing it to the Orchestrator.

## 🛠 Development Guardrails
- **Async First**: Use `async def` for all route handlers to prevent blocking the event loop.
- **Pydantic Validation**: All API inputs/outputs must be strictly typed using Pydantic models.
- **Error Handling**: Use custom FastAPI exceptions to return consistent error schemas to the frontend.
