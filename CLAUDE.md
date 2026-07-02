# CLAUDE.md — Antikythera AI Agent Entry Point

This is the authoritative quick-reference for AI agents working on the Antikythera project.

## Project Identity
**Antikythera** is a perpetual, human-in-the-loop, asynchronous multi-agent automation platform. It combines a deterministic Kanban pipeline with LLM-driven cognitive workflows. The project was previously named "Hermes" — now fully renamed to "Antikythera" in both code and docs.

## Quick Facts
| Item | Value |
|------|-------|
| Python | 3.9 (venv at `./venv/`) |
| Backend port | 8006 |
| Frontend dev port | 5173 (proxies API to 8006) |
| Framework | FastAPI (backend), React 19 + Vite + Tailwind (frontend) |
| State storage | JSON files in `automation-ideas/` (file-locked, atomic writes) |
| Test: Python | `pytest` (config: `pytest.ini`, asyncio_mode=auto) |
| Test: UI | `vitest` (via `ui/package.json` scripts) |
| Test: E2E | `playwright` (config: `playwright.config.ts`, tests in `tests/e2e/`) |

## Commands
```bash
# Start system (preferred)
./start_antikythera.sh

# Stop system
./stop_antikythera.sh

# Backend only
source venv/bin/activate && python -m uvicorn api.main:app --host 0.0.0.0 --port 8006

# Frontend only
cd ui && npm run dev

# Run Python tests
source venv/bin/activate && pytest

# Run UI tests
cd ui && npx vitest run

# Run E2E tests
npx playwright test
```

## Actual Directory Structure
```
api/                         # FastAPI backend
├── main.py                  # App factory, router registration, startup
├── board_router.py          # Kanban board state & items
├── pipeline_router.py       # Pipeline CRUD, runs, logs
├── integrations_router.py   # External system connectivity
├── jira_router.py           # Jira-specific endpoints
├── engine_router.py         # Execution engine
├── trigger_router.py        # Event/schedule triggers
├── orchestrator_router.py   # Orchestrator control
├── automation_router.py     # Automation compiler
├── skill_router.py          # Skill brainstormer
├── builder_router.py        # Workflow builder
├── brain_api.py             # Brain/learning endpoints
├── routers/
│   └── ai_engine_config_router.py  # AI engine config endpoints
├── adapters/                # Integration adapters
│   ├── base.py               # Abstract base adapter
│   ├── jira.py, github.py, internal.py, bob_shell.py
├── managers/                # State management (new hierarchy)
│   ├── base.py               # BaseJSONManager (file-lock + atomic write)
│   ├── kanban_state_manager.py
│   ├── template_manager.py
│   ├── run_manager.py
│   └── binding_manager.py
├── models/                   # Pydantic models (automation, config)
├── services/                 # Service layer (ai_engine_config)
├── executors/                # SafeExecutor for sandbox execution
├── state_manager.py          # LEGACY — do not use for new code
├── workflow_state_manager.py # Facade delegating to managers/
├── secret_vault.py           # EXISTS but UNUSED — credentials from env vars now
├── operator_registry.py      # Operator Registry for skill routing
├── execution_engine.py       # Step-by-step workflow execution
├── scheduler.py, retry_manager.py, trigger_manager.py
agents/                      # AI agent implementations
├── orchestrator.py, refiner.py, architect.py, tester.py, memory.py
ui/                          # React frontend
├── src/components/           # Kanban, Pipeline, Workflow, AI Engine, Integrations
automation-ideas/             # Data store (JSON state, requirements, brain patterns)
├── pipeline-state.json       # Single source of truth for pipeline state
├── workflow_templates.json, workflow_runs.json
├── requirements/{IDEA-ID}/   # Per-item: spec.md, architecture.md, tests.md, review.md
├── audit/                    # Daily audit logs
brain/                       # Learned patterns and pending updates
```

## Known Gotchas
1. **Hermes→Antikythera rename**: Formerly named "Hermes". The rename to "Antikythera" is now complete in code and docs. A few old design/spec files may still reference "Hermes" in git history.
2. **SecretVault exists but is dead code**: `api/secret_vault.py` implements Fernet encryption but `main.py` explicitly comments it out. Credentials now come from environment variables (`~/.antikythera/.env` → project `.env` symlink).
3. **Legacy StateManager**: `api/state_manager.py` is the old monolithic class. New code uses `WorkflowStateManager` → `managers/` hierarchy. Do not write new code against the legacy StateManager.
4. **Router locations are inconsistent**: Most routers are flat files in `api/`, only `ai_engine_config_router.py` is in `api/routers/`. The `api/AI.md` doc has been updated to reflect this.
5. **Empty pattern/knowledge files**: `automation-ideas/brain/patterns.md` has been cleaned (stub entries removed, real patterns preserved). `automation-ideas/knowledge/user.md` remains an empty placeholder.
6. **`.env` is a symlink**: Points to `~/.antikythera/.env`. The project `.env.example` documents the expected variables.
7. **ID normalization**: All Idea IDs (e.g., `ID-001`) **MUST** be uppercase.
8. **Atomic writes**: All JSON state writes must follow the temp-file-then-rename pattern (enforced by `BaseJSONManager._save()`).

## Specialized Briefings
For deep technical context, refer to these files:

| Scope | File | Focus |
|-------|------|-------|
| Agents | `docs/agents/AI.md` | Pipeline stages, agent roster, artifact specs |
| Backend/API | `api/AI.md` | FastAPI, state management, adapters |
| Workflows | `api/workflow_AI.md` | Workflow engine, triggers, automation |
| Frontend/UI | `ui/AI.md` | React 19, Tailwind, Kanban UX |
| Project Status | `PROJECT_STATUS.md` | Roadmap, gaps, verification strategy |
| API Contract | `docs/api-spec.md` | REST endpoint schemas |
