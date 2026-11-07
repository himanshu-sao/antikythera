# 🚀 Antikythera Cognitive Platform

Antikythera is a perpetual, human-in-the-loop, asynchronous multi-agent automation platform. It has evolved from a linear stage-based pipeline into a **Cognitive Orchestration System** that combines deterministic workflows with LLM-driven reasoning.

## 🌟 Vision
The goal of Antikythera is to provide a high-leverage platform where AI agents handle the "heavy lifting" of software engineering (refining requirements, designing architecture, writing tests) while allowing human operators to maintain absolute control through gated review stages and a high-fidelity Kanban UI.

## 🛠 Tech Stack
- **Agent Logic**: Python 3.11+ (FastAPI)
- **UI**: React 19, Vite, Tailwind CSS, TypeScript
- **State Management**: File-based JSON stores with `filelock` for concurrency
- **Cognitive Layer**: LLM-powered reasoning steps and a few-shot learning pattern store
- **Integrations**: Hybrid architecture supporting **MCP (Model Context Protocol) Servers** and **Native Python Adapters**
- **Scheduling**: `APScheduler` for background polling and event-driven triggers

---

## 🏗 System Architecture

### 1. The Cognitive Pipeline
The system supports two modes of operation:
- **Generic Pipeline**: A linear flow for high-level idea refinement (`INTAKE` → `DONE`)
- **Cognitive Workflows**: Reusable blueprints consisting of:
  - **Triggers**: Webhooks, Polling (JQL/Cron), or Manual starts
  - **Steps**: Action steps (via adapters), AI Reasoning steps (decisions), or Human Approval gates
  - **Context**: A `RunContext` that persists data across the entire lifecycle of a run

### 2. The Integration Hub
A centralized hub for managing external services:
- **Credentials**: Read from environment variables (`~/.antikythera/.env`, then the project `.env`) and the AI Engine config (`~/.antikythera/.ai_env`). The Fernet Secret Vault code remains in the repo but is not used by the running app.
- **Connector Types**:
  - **MCP Servers**: Plug-and-play discovery of tools from external MCP servers
  - **Native Adapters**: Custom Python glue code for complex local tasks or niche APIs
  - **Shell Sandbox**: Secure execution of whitelisted local scripts

### 3. The Learning Loop
Antikythera implements "Self-Learning" through human intervention:
- **Blocked State**: If the AI cannot make a decision, the run enters a `BLOCKED` state
- **Human Correction**: The operator provides the correct resolution in the UI
- **Pattern Promotion**: This correction is saved to the `PatternStore`
- **Future Application**: The AI uses these learned patterns to resolve similar future cases automatically

### 4. The Operational Surface (UI)
- **Global Pipeline**: The universal triage board for all ideas
- **Virtual Boards**: Template-specific filtered views that show only the items processed by a specific workflow
- **Workflow Architect**: A visual builder allowing users to generate blueprints using natural language prompts
- **Cognitive Timeline**: A high-fidelity event stream showing the AI's reasoning, adapter outputs, and state transitions

---

## 🗺️ Project Roadmap & Status

### Completed Phases ✅

| Phase | Title | Status |
|-------|-------|--------|
| **Phase 0** | Directory structure + state schema + `ideas.md` format | ✅ Completed |
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler | ✅ Completed |
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent | ✅ Completed |
| **Phase 3** | Stage-transition logging | ✅ Completed |
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow | ✅ Completed |
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) | ✅ Completed |
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) | ✅ Completed |
| **Phase 7** | File watcher / event-driven triggers | ✅ Completed |
| **Phase 8** | Automation Registry (Timer/Event/Manual) | ✅ Completed |
| **Phase 9** | Artifact-Driven Regression Loop | ✅ Completed |
| **Phase 10** | Pattern Promotion (Continuous Learning) | ✅ Completed |
| **Phase 11** | Execution Engine & Hybrid Orchestration | ✅ Completed |

### Enhancement Summary
All kanban-fix branch enhancements have been integrated:
- **Backend Robustness**: Thread-safe StateManager, atomic writes, Pydantic validation
- **UI Reliability**: React ErrorBoundary, loading/error states, optimistic updates
- **UX Improvements**: Username persistence, source selection, empty-state placeholders
- **Repo Hygiene**: Removed `node_modules` from git, centralized `apiUrl` config

---

## ⚙️ Setup & Configuration

### 1. Environment Setup
- Ensure Python 3.12 and Node.js 18+ are installed
- Install Python dependencies: `./venv/bin/python -m pip install -r requirements.txt` (add `-r requirements-dev.txt` for tests)
- Setup frontend: `cd ui && npm install`

### 2. Running the System

#### Option A: Docker (Recommended)

See [docker/README.md](docker/README.md) for detailed instructions.

```bash
# 1. Create config directory
mkdir -p ~/.antikythera

# 2. Create config file with your credentials
vim ~/.antikythera/.env

# 3. Create data directory
mkdir -p ~/antikythera-data

# 4. Start with Docker Compose
cd docker
docker-compose pull && docker-compose up
```

**Services:**
- Frontend UI: http://localhost:5173
- Backend API: http://localhost:8006
- API docs: disabled by default. Set `ANTIKYTHERA_ENABLE_DOCS=1` to serve Swagger at http://localhost:8006/docs

#### Option B: Local Development

- **Backend**: `./venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8006` (loopback only; see [Security and access](#-security-and-access))
- **Frontend**: `cd ui && npm run dev`

### 🔐 Security and access

Antikythera is a single-user tool for a trusted machine. Treat it as local software, not a public service.

**Current state (today):**
- The API has **no authentication yet**. Anything that can reach the port can call it.
- The local start script binds to `0.0.0.0`, the Docker compose files publish ports on all interfaces, and CORS allows all origins. These are being changed (see below).
- Integration secrets are masked in list responses, but are stored in `~/.antikythera/` or `automation-ideas/integrations.json` as plain text.
- Executor and Studio scripts run on the host. Only the terminal tool and SafeExecutor sandboxing are being tightened (see below).

**Planned access model (decided, implementation pending):**
- The backend listens on `127.0.0.1` by default. Publish it to other machines only on purpose.
- Every `/api/*` request must send `Authorization: Bearer <token>`. The token comes from `ANTIKYTHERA_API_TOKEN`. If that variable is unset, a random token is generated on first start, saved to `~/.antikythera/api_token` (mode `0600`), and logged with its location. Do not commit it.
- CORS is limited to the UI origin, set by `ANTIKYTHERA_CORS_ORIGINS` (default `http://localhost:5173`).
- Swagger/OpenAPI at `/docs` is off unless `ANTIKYTHERA_ENABLE_DOCS=1`.
- Until the token ships, run the backend on `127.0.0.1` and do not publish port 8006 to other machines. Note that `start_antikythera.sh` still binds `0.0.0.0` today; change it to `127.0.0.1` (or run uvicorn manually as shown in Option B).

**Your responsibilities:**
- Keep `~/.antikythera/` at mode `700` and its files at `600`. Do not commit `.env`, `.ai_env`, `api_token`, `automation-ideas/` or `registry/` data.
- Rotate any provider key that was ever pasted into a shared log, screen share or Docker image. Images published before commit `eac8428` contain a copy of the local data folder, including the vault key and integration records. Rebuild those images, rotate the secrets they held, and delete the old tags.
- Back up `automation-ideas/` with `scripts/backup_data.sh` (the archive is written with mode `0600`). Store the backup somewhere encrypted.
- The Docker compose files currently publish ports 8006 and 5173 on **all** host interfaces (`"8006:8006"`). Until authentication ships, change those entries to `"127.0.0.1:8006:8006"` and `"127.0.0.1:5173:5173"` so only this machine can reach them.

**Executor and automation safety (planned):**
- The executor's terminal tool will run only allowlisted programs without a shell. File writes will stay inside each item's folder.
- Studio and automation scripts will run in a subprocess with a time limit. Until then, treat them as trusted code.
- Templates that contain shell steps are rejected on save.

See [docs/decisions.md](docs/decisions.md) for the decisions behind this model and [docs/pending-items.md](docs/pending-items.md) for what is still open.

### 3. Key Directories
```
/
├── api/                          # Core backend logic and routers
│   ├── adapters/                 # Integration adapters (Jira, GitHub, etc.)
│   ├── managers/                 # State management hierarchy (BaseJSONManager+)
│   ├── models/                   # Pydantic data models
│   ├── services/                 # Service layer (AI engine config)
│   ├── executors/                # SafeExecutor for sandboxed execution
│   ├── routers/                  # Router subpackage (ai_engine_config only)
│   ├── board_router.py           # Kanban board endpoints
│   ├── pipeline_router.py        # Pipeline CRUD, runs, logs
│   ├── integrations_router.py    # Integration Hub endpoints
│   └── workflow_state_manager.py # Facade delegating to managers/
├── ui/                           # React frontend
│   ├── src/components/           # React components
│   └── src/types.ts              # TypeScript type definitions
├── agents/                       # Agent implementations
│   ├── orchestrator.py           # State machine and task dispatch
│   ├── refiner.py                # Requirements extraction
│   ├── architect.py              # Technical design
│   ├── tester.py                 # Validation and testing
│   └── memory.py                 # Pattern learning and brain updates
├── automation-ideas/             # Data store for state, templates, requirements
│   ├── ideas.md                  # Owner's intake file
│   ├── pipeline-state.json       # Single source of truth for pipeline state
│   ├── requirements/             # Per-itemspec.md`, `architecture.md`, `tests.md`
│   ├── audit/                    # Daily audit logs
│   └── brain/                    # Learned patterns and pending updates
├── design/                       # Design documents and specs
├── docs/                         # Technical documentation
└── tests/                        # Unit and integration tests
```

---

## 📚 Documentation Index

For detailed information, refer to these specialized documents:

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | **AI agent entry point** — Quick facts, actual directory structure, run/test commands, gotchas |
| `PROJECT_STATUS.md` | **Master reference** - Implementation roadmap, technical baseline, API mappings, remediation tasks |
| `AI.md` | **Dispatch table** - Directs agents to specialized briefings by domain |
| `docs/api-spec.md` | **API contract** — REST endpoint schemas and request/response formats |

### AI Agent Briefings
| Scope | Briefing File | Focus Area |
| :--- | :--- | :--- |
| **Agents** | `docs/agents/AI.md` | Pipeline stages, artifact specs, agent roster |
| **Backend/API** | `api/AI.md` | FastAPI, `StateManager`, API routes, adapters |
| **Workflows** | `api/workflow_AI.md` | Workflow engine, triggers, automation logic |
| **Frontend/UI** | `ui/AI.md` | React 19, Tailwind, Kanban board UX |

---

## 🔄 Core Operational Model

### The Dual-Track System
1. **Execution Track (Automation)**: Template-based step execution using integration adapters
2. **Collaboration Track (Orchestration)**: 7-stage phase-gated pipeline (Discovery → Handover)

### Atomic Transaction Model
Every significant change follows: **Proposal → Approval → Execution**

### Verification Methods
- **Automated Tests**: Playwright E2E or Pytest unit tests (must pass with 0 failures)
- **Log Audits**: Evidence in `audit/` or `pipeline-state.json`
- **Manual Checks**: Human verification documented in `PROJECT_STATUS.md`
- **Schema Validation**: JSON against Pydantic models

---
## ✨ Updated Features

- **Jira Integration Enhancements**: <br>  • Test Connection now performs a real request to `<JIRA_BASE_URL>/rest/api/3/myself` and reports precise HTTP status codes (e.g., 401, 403, 404). <br>  • Falls back to environment variables `JIRA_PAT` (or `JIRA_TOKEN`) and `JIRA_BASE_URL` (loaded from `~/.antikythera/.env` before the project `.env`). <br>  • Integration status (`connected`/`error`) is updated based on actual authentication success. <br>  • The API masks secret-looking keys (token, password, secret, key, auth and similar, including nested values and URL passwords) with `*****` in integration list responses, and the UI masks `jira_url` and `url` as well and removes the unused `test` flag from the JSON editor, preventing credential leakage.

- Delete model action with confirmation dialog.
- Provider‑based filter for model listings.
- API‑key edit modal and configurable keys overview.
- Fixed “Add Model” workflow with refreshable provider model list and searchable dropdown.
- OpenRouter provider support.
- Log‑tailing tab displaying the last 1 MiB of logs.
- UI refinements: status colors, hover effects, consistent button styling.

*Antikythera: Automating the mundane, empowering the human.*