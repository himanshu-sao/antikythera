# Antikythera Project Status & Execution Map

This document is the consolidated source of truth for the implementation state, build plan, and technical baseline of the Antikythera Multi-Agent Automation System.

## 🗺️ Project Roadmap & Phase Map

The Antikythera system follows a phased build approach. Phases 0–10 are the core foundation.

|| Phase | Title | Status | Notes ||
|---|---|---|---|
| **Phase 0** | Directory structure + state schema + `ideas.md` format | ✅ Completed | Foundation files established ||
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler | ✅ Completed | Core loop functional ||
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent | ✅ Completed | Artifact generation functional ||
| **Phase 3** | Telegram notifications + slash commands | ✅ Completed | Remote monitoring enabled ||
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow | ✅ Completed | System evolution enabled ||
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) | ✅ Completed | Local management surface ||
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) | ✅ Completed | Primary operational surface ||
| **Phase 7** | File watcher / event-driven triggers | ✅ Completed | Real-time responsiveness ||
| **Phase 8** | Automation Registry (Timer/Event/Manual) | ✅ Completed | Set-it-and-forget-it mode ||
|| **Phase 9** | Artifact-Driven Regression Loop | ✅ Completed | HITL technical steering ||
|| **Phase 10** | Pattern Promotion (Continuous Learning) | ✅ Completed | Turn successful specs into reusable patterns ||
|| **Phase 11** | Execution Engine & Hybrid Orchestration | ✅ Completed | Automated runs with HITL escalation bridge ||

### Execution Strategy
...

...

2. **Remediate**: Record gaps as remediation tasks in this file.
3. **Implement**: Fix tasks using `docs/prompts/SUPERPOWER-IMPLEMENT.prompt.md`.
4. **Verify**: Treat work as done only when it satisfies `VERIFICATION_CRITERIA.md`.

---

## 🛠️ Technical Baseline & Key Decisions

### Technology Stack
- **Agent Logic**: Python (FastAPI)
- **UI**: Node/React (Vite)
- **State**: JSON-based `pipeline-state.json` with thread-safe locking.

### Key Architectural Decisions
|- **Hybrid Orchestration**: Unified 7-stage pipeline (Discovery $\rightarrow$ Handover) for Human-Agent collaboration.
|- **Atomic Transactions**: All significant changes follow Proposal $\rightarrow$ Approval $\rightarrow$ Execution.
|- **The Hybrid Bridge**: Automated `ExecutionEngine` $\rightarrow$ `EscalationManager` $\rightarrow$ `LifecycleOrchestrator` $\rightarrow$ `ResumeRun` loop.
|- **Sandboxing**: Tester Agent uses Docker Compose for isolated provisioning.
|- **Communication**: Telegram for notifications/commands; Local UI for deep review/editing.
|- **ID Management**: Auto-incremented IDs (`ID-XXX`) with uppercase normalization.
|- **State Persistence**: Thread-safe `StateManager` with atomic writes (`os.replace`).
|- **UI Hosting**: Local hosting only.
|- **Repo Strategy**: Monorepo for agents, orchestrator, UI, and brain tools.

### Technical Integration (API & Data)
The following mapping defines the contract between the UI and the Backend.

**API Endpoints Mapping**
|| UI Action | HTTP Method | Endpoint | Backend Handler |
||-----------|-------------|----------|-----------------|
|| Load board | GET | `/api/state` | `get_state()` |
|| Move item | POST | `/api/move` | `move_item()` |
|| Update item | PATCH | `/api/item/{id}` | `update_item()` |
|| Create item | POST | `/api/items` | `create_item()` |
|| Add comment | POST | `/api/item/{id}/comment` | `add_comment()` |
|| Health check | GET | `/health` | `health_check()` |
|| Delete item | DELETE | `/api/item/{id}` | `delete_item()` |
|| Start run | POST | `/api/engine/start` | `ExecutionEngine.start_run()` |
|| Transition phase | POST | `/api/orchestrator/transition` | `orchestrator_router.transition_phase()` |

**Data Model Consistency**
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

## 🚀 Enhancements & Future Work

### Completed Enhancements (Kanban-Fix Branch)
The following high-priority improvements were integrated during the `kanban-fix` cycle:
- **Backend Robustness**: Thread-safe StateManager, atomic writes, Pydantic validation.
- **UI Reliability**: React ErrorBoundary, loading/error states, optimistic updates.
- **UX Improvements**: Username persistence, source selection (URL/Directory), empty-state placeholders.
- **Repo Hygiene**: Removed `node_modules` from git, centralized `apiUrl` config.

### Deferred Enhancements (Backlog)
| ID | Category | Title | Priority | Notes |
|---|---|---|---|---|
| ENH-07 | Frontend | Delete card button with confirmation | ✅ Completed | Implemented in CardEditor with window.confirm and backend DELETE call. |
| ENH-08 | Frontend | Toast notifications instead of alert() | ✅ Completed | Replaced all native alert calls with react-hot-toast. |
| ENH-10 | Frontend | Due date support | Medium | Requires data model update |
| ENH-11 | Frontend | Item priority visual indicators | Low | Basic priority field added in ENH-02 |
| ENH-12 | Frontend | Search/filter functionality | ✅ Completed | Implemented search, priority, and stage filters. |
| ENH-13 | Frontend | Persist intra-column reordering | Low | Identified regression in E2E tests; deferred to next maintenance cycle. |

---

## 📝 Kanban Implementation Notes

### Best Practices Applied
- **Optimistic Updates**: UI updates immediately before backend confirmation.
- **Visual Feedback**: Drag opacity and hover states.
- **Error Boundaries**: Localized recovery for component failures.
- **Thread Safety**: Backend locking prevents state corruption during concurrent access.

### UI/UX Design Decisions
- **Empty States**: Columns show "No items yet" when empty.
- **Confirmations**: Destructive actions (like delete) require a confirmation modal.
- **ID Normalization**: All IDs are coerced to uppercase to prevent filesystem mismatches.

---

## 🚩 Remediation Tasks

### Phase 7 Remediation (Verified)
- **R7.1**: Implement file watcher on `automation-ideas/` directory $\rightarrow$ ✅ Verified
- **R7.2**: Wire file watcher events to Orchestrator $\rightarrow$ ✅ Verified
- **R7.3**: Implement debounce/throttle mechanism $\rightarrow$ ✅ Verified
- **R7.4**: Write tests for file watcher $\rightarrow$ ✅ Verified

### Phase 5 Remediation (Verified)
- **R5.1**: Frontend unit/integration tests for Kanban UI $\rightarrow$ ✅ Verified
- **R5.6**: Fix ArtifactViewer fetch logic and tests $\rightarrow$ ✅ Verified
- **R5.2**: Fix Path Traversal in Artifact API $\rightarrow$ ✅ Verified
- **R5.3**: ID Case-Sensitivity Normalization $\rightarrow$ ✅ Verified
- **R5.4**: Fix Kanban drag-and-drop stage lookup $\rightarrow$ ✅ Verified
- **R5.5**: UI Type Safety and Permission Optimization $\rightarrow$ ✅ Verified

### Phase 6 Remediation (Verified)
- **R6.1**: Frontend tests for inline review editing $\rightarrow$ ✅ Verified
- **R6.2**: Frontend tests for real-time polling $\rightarrow$ ✅ Verified
- **R-UI-01**: Refactor E2E tests to avoid over-mocking reordering persistence $\rightarrow$ ✅ Verified

### Kanban-Fix Branch Remediation (Verified)
- **R-KF-01**: Remove `node_modules` from repository $\rightarrow$ ✅ Verified
- **R-KF-02**: Extract hardcoded API base URL to environment variable $\rightarrow$ ✅ Verified
- **R-KF-03**: Fix hardcoded `order: 0` in drag-move handler $\rightarrow$ ✅ Verified
- **R-KF-04**: Add file locking to `StateManager` to prevent race conditions $\rightarrow$ ✅ Verified
- **R-KF-05**: Verify module-level `Orchestrator()` instantiation at import time $\rightarrow$ ✅ Verified

### Remediation Template
Use this format when adding a new remediation item:
**### R<phase>.<index> — Short Task Title**
- **Status**: Pending
- **Issue**: Description of gap/defect.
- **Source**: Review finding/spec mismatch.
- **Expected Fix**: Required change.
- **Verification**: Required tests/checks.

---

## 📅 Planned Next Steps
1. Audit remaining phases using `SUPERPOWER-REVIEW.prompt.md`.
2. Fix any identified remediation tasks.
3. la Implement deferred enhancements from the backlog.
4. Finalize project documentation.
