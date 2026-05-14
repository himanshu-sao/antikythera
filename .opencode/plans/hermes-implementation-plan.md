# Hermes Multi-Agent Automation System — Implementation Plan

> Generated: 2026-05-14
> Source: `memory.md` (design document)

---

## Phase 0: Foundation — Directory Structure & Schema (IN PROGRESS)

**Goal:** Establish the filesystem skeleton, pipeline state schema, and ideas intake format.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 0.1 | Create `automation-ideas/requirements/` with ID-001 through ID-004 subdirectories | **in_progress** | None |
| 0.2 | Create `automation-ideas/audit/` directory | **in_progress** | None |
| 0.3 | Create `automation-ideas/brain/` with `history/` subdirectory | **in_progress** | None |
| 0.4 | Create `automation-ideas/pipeline-state.json` with full schema from memory.md §5 | **in_progress** | 0.1 |
| 0.5 | Verify `automation-ideas/ideas.md` matches format from memory.md §2 | **in_progress** | None |
| 0.6 | Create `.opencode/plans/` directory and this plan file | **done** | None |

**Deliverables:**
- Directory tree under `automation-ideas/`
- `pipeline-state.json` with initial state for ID-001 through ID-004
- Verified `ideas.md` format

---

## Phase 1: Core Pipeline — Orchestrator + Refiner + Heartbeat

**Goal:** The pipeline can intake ideas, refine them into specs, and run on a schedule.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 1.1 | Design Orchestrator Agent (Python) — main loop, state machine, agent dispatch | pending | Phase 0 |
| 1.2 | Implement `pipeline-state.json` read/write module | pending | 1.1 |
| 1.3 | Implement heartbeat scheduler (daily 10 PM, configurable) | pending | 1.1 |
| 1.4 | Implement Refiner Agent — reads `ideas.md` one-liner, writes `spec.md` | pending | 1.1 |
| 1.5 | Implement stage transition logic (INTAKE → REFINEMENT → REVIEW_SPEC) | pending | 1.2, 1.4 |
| 1.6 | Implement confidence scoring write from Refiner Agent | pending | 1.4 |
| 1.7 | Write unit tests for Orchestrator state machine | pending | 1.2 |
| 1.8 | Write unit tests for Refiner Agent | pending | 1.4 |
| 1.9 | Integration test: full INTAKE → REVIEW_SPEC flow | pending | 1.5, 1.7, 1.8 |

**Deliverables:**
- `agents/orchestrator.py` — main loop, state machine, heartbeat
- `agents/refiner.py` — spec generation from one-liner
- `agents/state.py` — pipeline-state.json read/write
- `agents/scheduler.py` — heartbeat scheduling
- `tests/` — unit + integration tests

---

## Phase 2: Full Agent Pipeline — Architect + Tester + Audit

**Goal:** All three dev pipeline agents (Refiner, Architect, Tester) plus passive Audit Agent.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 2.1 | Implement Architect Agent — reads `spec.md`, writes `architecture.md` | pending | Phase 1 |
| 2.2 | Implement Tester Agent — reads `architecture.md` + `spec.md`, writes `tests.md` | pending | 2.1 |
| 2.3 | Implement Audit Agent — appends structured entries to `audit/YYYY-MM-DD.md` | pending | Phase 1 |
| 2.4 | Wire Architect + Tester into Orchestrator stage transitions | pending | 2.1, 2.2 |
| 2.5 | Wire Audit Agent into Orchestrator (passive logging on every action) | pending | 2.3, 2.4 |
| 2.6 | Implement Docker sandbox provisioning for Tester Agent | pending | 2.2 |
| 2.7 | Write unit tests for Architect, Tester, Audit agents | pending | 2.1, 2.2, 2.3 |
| 2.8 | Integration test: full INTAKE → REVIEW_TEST flow | pending | 2.4, 2.7 |

**Deliverables:**
- `agents/architect.py` — architecture document generation
- `agents/tester.py` — test plan generation + Docker sandbox
- `agents/audit.py` — passive audit logging
- `docker/` — Docker Compose files for sandbox
- `tests/` — expanded test suite

---

## Phase 3: Telegram Integration — Notifications + Slash Commands

**Goal:** Owner receives Telegram notifications on stage transitions and can query/trigger via slash commands.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 3.1 | Implement Telegram notification module (stage transition alerts) | pending | Phase 2 |
| 3.2 | Implement `/status` slash command — full pipeline overview | pending | 3.1 |
| 3.3 | Implement `/run ID-XXX` slash command — manual pipeline trigger | pending | 3.1 |
| 3.4 | Implement `/approve ID-XXX` slash command — mark review as APPROVED | pending | 3.1 |
| 3.5 | Implement `/redo ID-XXX` slash command — mark review as NEEDS_REVISION | pending | 3.1 |
| 3.6 | Implement `/pause` / `/resume` — heartbeat control | pending | 3.1 |
| 3.7 | Wire Telegram module into Orchestrator | pending | 3.1, Phase 2 |
| 3.8 | Write tests for Telegram handlers | pending | 3.1–3.6 |

**Deliverables:**
- `agents/telegram.py` — notification + slash command handlers
- Integration with existing Hermes Telegram MCP server
- `tests/` — Telegram handler tests

---

## Phase 4: Memory Agent + Brain Loop

**Goal:** The system learns from owner feedback and audit logs, proposing pattern updates.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 4.1 | Implement Memory Agent — reads audit logs + review.md files | pending | Phase 2 |
| 4.2 | Implement pattern extraction logic → writes to `brain/pending-updates.md` | pending | 4.1 |
| 4.3 | Implement brain update versioning (`brain/history/YYYY-MM-DD-update.md`) | pending | 4.1 |
| 4.4 | Implement owner approval flow (Telegram notification → apply/reject) | pending | 4.2, Phase 3 |
| 4.5 | Wire Memory Agent into nightly scheduler (separate from dev pipeline) | pending | 4.2 |
| 4.6 | Write tests for Memory Agent | pending | 4.1–4.3 |

**Deliverables:**
- `agents/memory.py` — brain loop agent
- `brain/pending-updates.md` — auto-populated
- `brain/history/` — versioned updates
- Nightly scheduler integration

---

## Phase 5: Kanban UI (Phase 1) — Read + Drag/Drop

**Goal:** Web-based Kanban board showing pipeline state with drag-and-drop stage transitions.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 5.1 | Scaffold React/Next.js project for Kanban UI | pending | Phase 2 |
| 5.2 | Implement API endpoints in Orchestrator (read pipeline state, list artifacts) | pending | 5.1 |
| 5.3 | Build Kanban board component — columns = pipeline stages | pending | 5.2 |
| 5.4 | Build card component — ID, title, priority, confidence, stage, timestamp | pending | 5.3 |
| 5.5 | Implement drag-and-drop stage transitions (updates `pipeline-state.json`) | pending | 5.3 |
| 5.6 | Implement detail view — shows spec.md, architecture.md, tests.md, review.md | pending | 5.3 |
| 5.7 | Implement inline review.md editor in detail view | pending | 5.6 |
| 5.8 | Write UI tests (component + integration) | pending | 5.3–5.7 |

**Deliverables:**
- `ui/` — React/Next.js project
- Kanban board with all pipeline columns
- Detail view with artifact display
- Drag-and-drop stage transitions
- Inline review.md editor

---

## Phase 6: Kanban UI (Phase 2) — Real-Time + Deep Links

**Goal:** Enhanced UI with real-time updates, Telegram deep links, and multi-tab layout.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 6.1 | Implement WebSocket or polling for real-time agent progress updates | pending | Phase 5 |
| 6.2 | Implement Telegram deep-link buttons → open specific card in UI | pending | 6.1, Phase 3 |
| 6.3 | Build multi-tab layout: Kanban | Brain/Patterns | Audit Log | Settings | pending | Phase 5 |
| 6.4 | Implement Brain/Patterns tab — view `brain/patterns.md` | pending | 6.3 |
| 6.5 | Implement Audit Log tab — view/search `audit/` logs | pending | 6.3 |
| 6.6 | Implement Settings tab — heartbeat config, Telegram config | pending | 6.3 |
| 6.7 | Write UI tests for new features | pending | 6.1–6.6 |

**Deliverables:**
- Real-time UI updates
- Telegram deep-link integration
- Multi-tab layout
- Settings management UI

---

## Phase 7: Event-Driven Triggers — File Watcher

**Goal:** The system reacts instantly to file changes (ideas.md, review.md) without waiting for heartbeat.

| # | Task | Status | Dependencies |
|---|------|--------|-------------|
| 7.1 | Implement file watcher on `automation-ideas/` directory | pending | Phase 2 |
| 7.2 | Wire file watcher events to Orchestrator (new idea → auto-trigger pipeline) | pending | 7.1 |
| 7.3 | Wire file watcher events for review.md changes → auto-advance stage | pending | 7.1 |
| 7.4 | Implement debounce/throttle to prevent rapid re-triggers | pending | 7.1 |
| 7.5 | Write tests for file watcher | pending | 7.1–7.4 |

**Deliverables:**
- `agents/watcher.py` — file system watcher
- Event-driven pipeline triggers
- Debounce/throttle mechanism

---

## Dependency Graph (Summary)

```
Phase 0 (Foundation)
    ↓
Phase 1 (Orchestrator + Refiner + Heartbeat)
    ↓
Phase 2 (Architect + Tester + Audit)
    ↓
Phase 3 (Telegram) ──→ Phase 4 (Memory/Brain)
    ↓                         ↓
Phase 5 (Kanban UI v1) ←─────┘
    ↓
Phase 6 (Kanban UI v2)
    ↓
Phase 7 (File Watcher)
```

---

## Directory Structure (Target)

```
automation-ideas/
├── ideas.md
├── pipeline-state.json
├── requirements/
│   ├── ID-001/
│   │   ├── spec.md
│   │   ├── architecture.md
│   │   ├── tests.md
│   │   └── review.md
│   ├── ID-002/
│   │   └── ...
│   ├── ID-003/
│   │   └── ...
│   └── ID-004/
│       └── ...
├── audit/
│   └── YYYY-MM-DD.md
└── brain/
    ├── memory.md
    ├── patterns.md
    ├── pending-updates.md
    └── history/
        └── YYYY-MM-DD-update.md

agents/
├── orchestrator.py
├── refiner.py
├── architect.py
├── tester.py
├── audit.py
├── memory.py
├── telegram.py
├── state.py
├── scheduler.py
└── watcher.py

ui/
├── (React/Next.js project)

docker/
├── docker-compose.yml
└── (sandbox configs)

tests/
├── test_orchestrator.py
├── test_refiner.py
├── test_architect.py
├── test_tester.py
├── test_audit.py
├── test_memory.py
├── test_telegram.py
└── test_watcher.py
```