# 🚀 Antikythera Cognitive Platform

Antikythera is a perpetual, human-in-the-loop, asynchronous multi-agent automation platform. It has evolved from a linear stage-based pipeline into a **Cognitive Orchestration System** that combines deterministic workflows with LLM-driven reasoning.

## 🌟 Vision
The goal of Antikythera is to provide a high-leverage platform where AI agents handle the "heavy lifting" of software engineering (refining requirements, designing architecture, writing tests) while allowing human operators to maintain absolute control through gated review stages and a high-fidelity Kanban UI.

## 🛠 Tech Stack
- **Agent Logic**: Python 3.9+ (FastAPI)
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
- **Secret Vault**: Encrypted storage for API keys and tokens (All integration secrets, including Jira credentials, are persisted here to survive system restarts)
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
| **Phase 3** | Telegram notifications + slash commands | ✅ Completed |
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
- Ensure Python 3.9+ and Node.js 18+ are installed
- Install Python dependencies: `pip install fastapi uvicorn cryptography apscheduler requests`
- Setup frontend: `cd ui && npm install`

### 2. Running the System
- **Backend**: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8006`
- **Frontend**: `npm run dev`

### 3. Key Directories
```
/
├── api/                          # Core backend logic and routers
│   ├── adapters/                 # Integration adapters (Jira, GitHub, etc.)
│   ├── models/                   # Pydantic data models
│   └── routers/                  # FastAPI route definitions
├── ui/                           # React frontend
│   ├── src/components/           # React components
│   └── src/types.ts              # TypeScript type definitions
├── agents/                       # Agent implementations
│   ├── orchestrator.py           # State machine and task dispatch
│   ├── refiner.py                # Requirements extraction
│   ├── architect.py              # Technical design
│   ├── tester.py                 # Validation and testing
│   └── memory.py                 | Pattern learning and brain updates
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
| `PROJECT_STATUS.md` | **Master reference** - Implementation roadmap, technical baseline, API mappings, remediation tasks |
| `VERIFICATION_CRITERIA.md` | **Definition of Done** - Phase-specific completion criteria |
| `execution.md` | **Granular task tracker** - Low-code compiler workflow with 6-stage loops |
| `AI.md` | **AI agent index** - Directs agents to specialized briefings |

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

- **Jira Integration Enhancements**: <br>  • Test Connection now performs a real request to `<JIRA_BASE_URL>/rest/api/3/myself` and reports precise HTTP status codes (e.g., 401, 403, 404). <br>  • Falls back to environment variables `JIRA_ISV_PERSONAL_ACCESS_TOKEN` and `JIRA_BASE_URL` (loaded from `~/.antikythera/.env` before the project `.env`). <br>  • Integration status (`connected`/`error`) is updated based on actual authentication success. <br>  • UI masks secret fields (`token`, `access_token`, `jira_url`, `url`) with `*****` and removes the unused `test` flag from the JSON editor, preventing credential leakage.

- Delete model action with confirmation dialog.
- Provider‑based filter for model listings.
- API‑key edit modal and configurable keys overview.
- Fixed “Add Model” workflow with refreshable provider model list and searchable dropdown.
- OpenRouter provider support.
- Log‑tailing tab displaying the last 1 MiB of logs.
- UI refinements: status colors, hover effects, consistent button styling.

*Antikythera: Automating the mundane, empowering the human.*