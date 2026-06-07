# 🚀 Antikythera Master Execution Document

This is the **single source of truth** for the Antikythera Cognitive Platform. It consolidates the project roadmap, technical baseline, verification criteria, and detailed execution workflow into one reference.

---

## 🗺️ Project Roadmap & Phase Status

| Phase | Title | Status | Notes |
|-------|-------|--------|-------|
| **Phase 0** | Directory structure + state schema + `ideas.md` format | ✅ Completed | Foundation files established |
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler | ✅ Completed | Core loop functional |
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent | ✅ Completed | Artifact generation functional |
| **Phase 3** | Telegram notifications + slash commands | ✅ Completed | Remote monitoring enabled |
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow | ✅ Completed | System evolution enabled |
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) | ✅ Completed | Local management surface |
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) | ✅ Completed | Primary operational surface |
| **Phase 7** | File watcher / event-driven triggers | ✅ Completed | Real-time responsiveness |
| **Phase 8** | Automation Registry (Timer/Event/Manual) | ✅ Completed | Set-it-and-forget-it mode |
| **Phase 9** | Artifact-Driven Regression Loop | ✅ Completed | HITL technical steering |
| **Phase 10** | Pattern Promotion (Continuous Learning) | ✅ Completed | Turn successful specs into reusable patterns |
| **Phase 11** | Execution Engine & Hybrid Orchestration | ✅ Completed | Automated runs with HITL escalation bridge |

### Execution Strategy
1. **Design**: Follow the 6-stage loop (Design → Code → Unit Test → Integration Test → Sign Off → Commit).
2. **Remediate**: Record gaps as remediation tasks in this document.
3. **Implement**: Fix tasks using `docs/prompts/SUPERPOWER-IMPLEMENT.prompt.md`.
4. **Verify**: Treat work as done only when it satisfies the **Verification Criteria** section below.

---

## 🛠️ Technical Baseline & Architecture

### Technology Stack
- **Agent Logic**: Python (FastAPI)
- **UI**: Node/React (Vite, Tailwind CSS, TypeScript)
- **State**: JSON-based `pipeline-state.json` with thread-safe locking (`filelock`)
- **Integrations**: Hybrid (MCP Servers + Native Python Adapters)
- **Scheduling**: `APScheduler` for background polling and webhooks

### Key Architectural Decisions
- **Hybrid Orchestration**: Unified 7-stage pipeline (Discovery → Handover) for Human-Agent collaboration
- **Atomic Transactions**: All significant changes follow Proposal → Approval → Execution
- **The Hybrid Bridge**: `ExecutionEngine` → `EscalationManager` → `LifecycleOrchestrator` → `ResumeRun` loop
- **Sandboxing**: Tester Agent uses Docker Compose for isolated provisioning
- **Communication**: Telegram for notifications/commands; Local UI for deep review/editing
- **ID Management**: Auto-incremented IDs (`ID-XXX`) with uppercase normalization
- **State Persistence**: Thread-safe `StateManager` with atomic writes (`os.replace`)
- **UI Hosting**: Local hosting only
- **Repo Strategy**: Monorepo for agents, orchestrator, UI, and brain tools

### System Architecture Overview

#### 1. The Cognitive Pipeline
- **Generic Pipeline**: Linear flow (`INTAKE` → `DONE`) for high-level idea refinement
- **Cognitive Workflows**: Reusable blueprints with Triggers, Steps, and Context (`RunContext`)

#### 2. The Integration Hub
- **Secret Vault**: Encrypted storage for API keys and tokens
- **MCP Servers**: Plug-and-play discovery of tools
- **Native Adapters**: Custom Python glue code for complex tasks
- **Shell Sandbox**: Secure execution of whitelisted scripts

#### 3. The Learning Loop
- **Blocked State**: AI cannot decide → `BLOCKED`
- **Human Correction**: Operator provides resolution
- **Pattern Promotion**: Correction saved to `PatternStore`
- **Future Application**: AI uses patterns for similar cases

#### 4. The Operational Surface (UI)
- **Global Pipeline**: Universal triage board
- **Virtual Boards**: Template-specific filtered views
- **Workflow Architect**: Visual builder for blueprints
- **Cognitive Timeline**: Event stream of AI reasoning

### API Endpoints Mapping
| UI Action | HTTP Method | Endpoint | Backend Handler |
|-----------|-------------|----------|-----------------|
| Load board | GET | `/api/state` | `get_state()` |
| Move item | POST | `/api/move` | `move_item()` |
| Update item | PATCH | `/api/item/{id}` | `update_item()` |
| Create item | POST | `/api/items` | `create_item()` |
| Add comment | POST | `/api/item/{id}/comment` | `add_comment()` |
| Health check | GET | `/health` | `health_check()` |
| Delete item | DELETE | `/api/item/{id}` | `delete_item()` |
| Start run | POST | `/api/engine/start` | `ExecutionEngine.start_run()` |
| Transition phase | POST | `/api/orchestrator/transition` | `orchestrator_router.transition_phase()` |

### Data Model Consistency
| Field | Frontend Type | Backend Type | Notes |
|-------|--------------|--------------|-------|
| `id` | string | string | Normalized to uppercase |
| `title` | string | string | |
| `stage` | string | string | Validated against `VALID_STAGES` |
| `priority` | string | string | lowercase |
| `confidence_score` | number | number | 0-100 |
| `description` | string? | string | Optional, defaults to "" |
| `created_at` | string | string | ISO 8601 format |
| `updated_at` | string | string | ISO 8601 format |

---

## ✅ Verification Criteria (Definition of Done)

### Global Verification Standards
All implementation work must meet these baseline standards:
- **ID Normalization**: All Idea IDs (e.g., `ID-001`) must be coerced to uppercase across the entire stack.
- **Type Safety**: No `any` types in TypeScript; Pydantic models used for all API request/response bodies in Python.
- **Error Handling**: No swallowed exceptions. All API errors must return a structured JSON response with a `detail` field.
- **State Integrity**: No direct file writes to `pipeline-state.json` outside of the `StateManager` class.
- **Logging**: All agent actions must be recorded via the Audit Agent; no silent failures.
- **Clean Code**: No `console.log` or `print` statements left in production code.

### Phase-Specific Criteria

#### Phase 0: Foundation
- [ ] **Directory Structure**: All folders (`automation-ideas/`, `requirements/`, `audit/`, `brain/`) exist.
- [ ] **State Schema**: `pipeline-state.json` initializes with valid `last_heartbeat` and empty `items`.
- [ ] **Intake Format**: `ideas.md` accepts `- [ID-XXX] Title | Priority: X` format.

#### Phase 1: Core Loop
- [ ] **Orchestrator Trigger**: Heartbeat scheduler triggers Orchestrator at configured intervals.
- [ ] **Refinement Flow**: Orchestrator → Refiner Agent → `requirements/ID-XXX/spec.md` produced.
- [ ] **State Update**: `pipeline-state.json` updated to `REVIEW_SPEC` after `spec.md` written.
- [ ] **Confidence Scoring**: `confidence_score` (0-100) written by Refiner.

#### Phase 2: Artifact Generation
- [ ] **Architecture Flow**: `spec.md` → Architect Agent → `architecture.md` produced.
- [ ] **Testing Flow**: `architecture.md` → Tester Agent → `tests.md` produced.
- [ ] **Audit Trail**: Every transition logged in `audit/YYYY-MM-DD.md`.
- [ ] **Sandbox Validation**: Tester verifies `tests.md` based on successful Docker sandbox dry-run.

#### Phase 3: Remote Monitoring (Telegram)
- [ ] **Notifications**: Telegram message sent on stage transition.
- [ ] **Slash Commands**: `/status` returns correct summary; `/run ID-XXX` forces processing.

#### Phase 4: The Brain Loop (Learning)
- [ ] **Pattern Extraction**: Memory Agent identifies recurring themes → `brain/pending-updates.md`.
- [ ] **Human-in-the-Loop**: `patterns.md` updated only after `review_status: APPROVED`.
- [ ] **Versioning**: Previous `patterns.md` archived in `brain/history/`.

#### Phase 5: Kanban UI (Basic)
- [ ] **State Sync**: UI renders columns/cards based on `pipeline-state.json`.
- [ ] **Drag-and-Drop**: Moving card triggers `POST /api/move` and updates backend.
- [ ] **Optimistic UI**: Cards move instantly; snap back on failure.
- [ ] **Persistence**: Page refresh preserves positions/new items.

#### Phase 6: Kanban UI (Advanced)
- [ ] **Inline Review**: Editing `review.md` in UI updates file and `review_status`.
- [ ] **Real-time Polling**: UI reflects agent progress without manual refresh.
- [ ] **Search & Filter**: Filtering by Priority/Stage/Search works without reload.

#### Phase 7: Event-Driven Triggers
- [ ] **File Watcher**: Modifying `ideas.md` triggers Orchestrator within < 5s.
- [ ] **Debounce**: Rapid saves result in only one trigger.
- [ ] **Trigger Validation**: System correctly identifies new IDs to process.

#### Phase 8: Automation Registry
- [ ] **Registry Persistence**: Tasks saved to `registry/automation_registry.json`.
- [ ] **Trigger Support**: Handles `TIMER`, `EVENT`, `MANUAL` modes.
- [ ] **Task Management**: CLI/Skill supports full CRUD on automations.

#### Phase 9: Artifact-Driven Regression Loop
- [ ] **Change Detection**: System detects modifications to `spec.md`, `architecture.md`, `tests.md`.
- [ ] **Stage Regression**: Modifications regress task to appropriate stage (e.g., `REFINEMENT`).
- [ ] **UI Synchronization**: Kanban UI allows direct editing of artifacts with auto-save.

#### Phase 10: Pattern Promotion
- [ ] **Extraction**: Memory Agent proposes updates to `patterns.md`.
- [ ] **Approval**: Brain update only occurs after human `APPROVED` status.

#### Phase 11: Hybrid Execution Engine
- [ ] **Run Loop**: `start_run` triggers step sequence; logs `RUN_STARTED` → `RUN_COMPLETED`.
- [ ] **Context Resolution**: Placeholders like `{{input_val}}` replaced with runtime data.
- [ ] **The Hybrid Bridge**: Critical failure → `EscalationManager` → `OrchestratorTask` in INTAKE.
- [ ] **Resume Flow**: Recovery task DONE → `RESUME_RUN` signal fired.
- [ ] **Template Validation**: `save_template` rejects `ORCHESTRATOR_TASK` steps without `target_lifecycle_phase`.

### Verification Methods
| Method | Description | Requirement |
|--------|-------------|-------------|
| **Automated Test** | Playwright E2E or Pytest unit test | Must pass with 0 failures. |
| **Log Audit** | Checking `audit/` or `pipeline-state.json` | Evidence of action must exist. |
| **Manual Check** | Human operator verifies UI/File behavior | Documented as "Verified" here. |
| **Schema Check** | Validating JSON against a spec | Must be valid JSON and match Pydantic models. |

---

## 🚀 Enhancements & Remediation Tasks

### Completed Enhancements (Kanban-Fix Branch)
- **Backend Robustness**: Thread-safe StateManager, atomic writes, Pydantic validation.
- **UI Reliability**: React ErrorBoundary, loading/error states, optimistic updates.
- **UX Improvements**: Username persistence, source selection, empty-state placeholders.
- **Repo Hygiene**: Removed `node_modules` from git, centralized `apiUrl` config.

### Phase 3.5 Completion Summary
All tasks in Phase 3.5 (Execution Splitting & Dashboard) completed:
- **3.5.1** Design: Parent-Child Execution & Data Model ✅
- **3.5.2** Code: Update Execution Engine ✅
- **3.5.3** Code: Dashboard Child View ✅
- **3.5.4** Code: Audit & Structured Data UI ✅
- **3.5.5** Unit Test: Split Logic & Data Extraction ✅
- **3.5.6** Integration: Dashboard Visualization ✅
- **3.5.7** Sign Off: Split UX Review ✅

**Key Implementations:** Loop execution creates child executions with `parent_run_id`; Parsing skills auto-extract structured fields; Dashboard shows parent with expandable children displaying extracted fields.

### Deferred Enhancements (Backlog)
| ID | Category | Title | Priority |
|----|----------|-------|----------|
| ENH-10 | Frontend | Due date support | Medium |
| ENH-11 | Frontend | Item priority visual indicators | Low |
| ENH-13 | Frontend | Persist intra-column reordering | Low |

### Open Remediation Tasks
*Currently, no open remediation tasks are tracked. All items from `kanban-fix` and previous phases have been verified.*

### Remediation Template
**### R<phase>.<index> — Short Task Title**
- **Status**: Pending / Implemented / Verified
- **Issue**: Description of gap/defect.
- **Source**: Review finding/spec mismatch.
- **Expected Fix**: Description of required change.
- **Verification**: Required tests/checks to close.

---

## 🛠️ Granular Execution Workflow (Low-Code Compiler Implementation)

This section details the 6-stage loop for implementing features (Design → Code → Unit Test → Integration Test → Sign Off → Commit).

### 🔄 Workflow Rules
1. **Sequential Flow**: Tasks MUST be completed in order.
2. **Session Continuity**: In new sessions, execute the first `PENDING` task.
3. **Atomic Updates**: After success, update status to `COMPLETED`.
4. **No Skip**: A task moves to `COMPLETED` only after **Stage 5 (Sign Off)**.

### Completed Phases in Workflow

#### Phase 1: The Foundation (Deterministic Core)
**Goal**: Build data models and adapter-based execution engine.
- **1.1** Data Schema ✅ (COMPLETED)
- **1.2** Adapter Layer ✅ (COMPLETED)
- **1.3** Operator Registry ✅ (COMPLETED)
- **1.4** Sandbox State ✅ (COMPLETED)

#### Phase 1.5: Core Redesign
- **1.5.0** Design: Safe Executor, Dynamic Install & Model ✅
- **1.5.1 - 1.5.6** Code, Test, Integration ✅
- **1.5.7** Sign Off ✅

#### Phase 2: The "Compiler" (AI → Logic Bridge)
- **2.1** The Proposal Loop ✅
- **2.2** Skill Brainstormer ✅
- **2.5.1** Design: Script Sandboxing & Proposal UI ✅
- **2.5.2 - 2.5.6** Code, Test, Integration, Sign Off ✅

#### Phase 3: The WYSIWYG Builder
- **3.1** Interactive Studio ✅
- **3.2** Step Recorder ✅
- **3.3** Highlighter UI ✅
- **3.5.1 - 3.5.7** Execution Splitting & Dashboard (All stages ✅)

#### Phase 4: Pipeline Orchestration
- **4.1** Promotion Logic ✅
- **4.2** Flowchart View ✅
- **4.3** Execution History ✅
- **4.5.1 - 4.5.7** Global Skills & Credential Prompt (All stages ✅)

#### Phase 5: Home Page Integration
- **5.1** Tabbed Navigation ✅
- **5.2** Pipeline Dashboards ✅
- **5.3** E2E Validation ✅
- **5.5.1 - 5.5.2** Final E2E Validation (Jira Use Case) ✅

**Note**: All granular implementation tasks for Phases 1–5 are complete. Future work will follow this same 6-stage pattern.

---

## 📝 Kanban Implementation Notes

### Best Practices Applied
- **Optimistic Updates**: UI updates immediately before backend confirmation.
- **Visual Feedback**: Drag opacity and hover states.
- **Error Boundaries**: Localized recovery for component failures.
- **Thread Safety**: Backend locking prevents state corruption during concurrent access.

### UI/UX Design Decisions
- **Empty States**: Columns show "No items yet" when empty.
- **Confirmations**: Destructive actions (like delete) require confirmation modal.
- **ID Normalization**: All IDs coerced to uppercase to prevent filesystem mismatches.

---

## 📚 Reference Documents
- `README.md` - Project overview and setup
- `AI.md` - AI agent index with specialized briefings
- `docs/agents/AI.md` - Agent roster and artifact specs
- `api/AI.md` - Backend/API technical context
- `ui/AI.md` - Frontend/UI guidance
- `api/workflow_AI.md` - Workflow engine and triggers

---

## 🗑️ Consolidated Files
The following files have been merged into this document and removed:
- `PROGRESS.md`
- `memory.md`
- `ANTIKYTHERA_PRODUCT_SPEC.md`
- `PHASE_3_5_COMPLETION.md`
- `VERIFICATION_SUMMARY.md`
- `FIXES.md`
- `ANTIKYTHERA_SYSTEM_DOCS.md`
- `VERIFICATION_CRITERIA.md`
- `execution.md`