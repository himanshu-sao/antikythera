# CLAUDE.md — Antikythera AI Agent Entry Point

This is the authoritative quick-reference for AI agents working on the Antikythera project.

## Project Identity
**Antikythera** is a perpetual, human-in-the-loop, asynchronous multi-agent automation platform. It combines a deterministic Kanban pipeline with LLM-driven cognitive workflows. The project was previously named "Hermes" — now fully renamed to "Antikythera" in both code and docs.

## Quick Facts
| Item | Value |
|------|-------|
| Python | 3.12 (venv at `./venv/`) |
| Backend port | 18006 (loopback only; `/api/*` needs a bearer token) |
| Frontend dev port | 15173 (proxies API to 18006) |
| Help page | `/help` (built-in instructions, no token) |
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
./venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 18006

# Frontend only
cd ui && npm run dev

# Run Python tests (default run stubs bob, blocks network, bypasses the API token;
# -m live_llm opts into live provider tests)
./venv/bin/python -m pytest

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
2. **SecretVault exists but is dead code**: `api/secret_vault.py` implements Fernet encryption but `main.py` explicitly comments it out. Credentials now come from environment variables (`~/.antikythera/.env` → project `.env` symlink). Nothing in production instantiates it; leftover references exist only in `api/integration_hub.py` fallback code and one test.
3. **Legacy StateManager**: `api/state_manager.py` is the old monolithic class. New code uses `WorkflowStateManager` → `managers/` hierarchy. Do not write new code against the legacy StateManager. `api/adapters/internal.py` was migrated to `api.main.get_state_manager()` in P1.5.
4. **Router registration**: All routers are now `include_router`'d in `api/main.py` (P1.3). `workflow_router` uses `prefix="/api/workflows"` (matches UI). Only `ai_engine_config_router.py` lives in `api/routers/`; the rest are flat files in `api/`.
5. **Stub detection is centralised**: `LLMClient.is_stub()` is the single source of truth for unusable LLM output; the memory loop and the routers skip writes on stub replies (P3.1/P2.4). The old `stub response` bodies were cleaned out of `brain/patterns.md`.
6. **`.env` is a symlink**: Points to `~/.antikythera/.env`. The project `.env.example` documents the expected variables.
7. **ID normalization**: All Idea IDs (e.g., `ID-001`) **MUST** be uppercase.
8. **Atomic writes**: All JSON state writes must follow the temp-file-then-rename pattern (enforced by `BaseJSONManager._save()`).
9. **Pending-work list lives in `PROJECT_STATUS.md`**: That doc (reconciled 2026-07-12) is the canonical backlog — it supersedes the stale `SESSION_UPDATE.md` (last entry 2026-06-06). AI agents: read `PROJECT_STATUS.md` for what's done vs. pending; do not trust `SESSION_UPDATE.md`.
10. **`ibm_bob` is a CLI-based LLM provider**: Unlike the other 7 providers (all HTTP/OpenAI-compatible), `ibm_bob` shells out to the local `bob` binary (v1.0.6), which manages its own auth (browser SSO, 24h cache). Do not wire `ibm_bob` through the HTTP OpenAI client. Routed via `LLMClient._chat_bob()` in `agents/llm_client.py` (see P2.6 in `PROJECT_STATUS.md`, now DONE). The verified `bob` invocation: `bob --chat-mode ask --allowed-mcp-server-names "" --hide-intermediary-output -o text [-m <model>]`, with the **prompt piped on stdin** (`subprocess.run(input=prompt, ...)`) — do NOT use the deprecated `-p` or a positional prompt, do NOT fabricate a model id (an unrecognized id crashes the binary with "[object Object]"). There are two distinct "BOB" things in this project: `ibm_bob` the LLM provider (`LLMClient`) and `bob_shell` the integration adapter (`api/adapters/bob_shell.py` / `ExecutionEngine`). They shell out to the same binary but serve different purposes.
11. **LLM resolution chain**: `LLMClient` (in `agents/llm_client.py`) resolves provider/model from `AIEngineConfigService` (UI-selected default in `~/.antikythera/ai_config.json`) first, falling back to `config.yaml`'s `llm` block. `config.yaml` is a fallback only — the AI Engine config UI is the primary dial. All agent and router LLM call sites go through `LLMClient` (P2.4 wired `/propose` and `/brainstorm`).

## Specialized Briefings
For deep technical context, refer to these files:

| Scope | File | Focus |
|-------|------|-------|
| Agents | `docs/agents/AI.md` | Pipeline stages, agent roster, artifact specs |
| Backend/API | `api/AI.md` | FastAPI, state management, adapters |
| Workflows | `api/workflow_AI.md` | Workflow engine, triggers, automation |
| Frontend/UI | `ui/AI.md` | React 19, Tailwind, Kanban UX |
| Project Status | `PROJECT_STATUS.md` | **Canonical pending-work doc** (P0→P3 remediation ledger, roadmap)
| API Contract | `docs/api-spec.md` | REST endpoint schemas |
