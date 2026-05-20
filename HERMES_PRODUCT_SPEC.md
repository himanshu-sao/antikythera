# 🚀 Hermes Product Specification

## 1. Vision & Purpose
Hermes is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It converts simple idea descriptions into structured specifications, architecture, and verified tests, allowing a human operator to review and approve progress via a Kanban UI.

## 2. System Architecture

### 2.1 Pipeline Workflow
Ideas move through a linear sequence of stages:
`INTAKE` → `REFINEMENT` → `REVIEW_SPEC` → `ARCHITECTURE` → `REVIEW_ARCH` → `TESTING` → `REVIEW_TEST` → `APPROVED` → `EXECUTING` → `DONE`

### 2.2 Agent Roster
- **Orchestrator**: Manages pipeline state and dispatches work.
- **Refiner Agent**: Creates `spec.md`.
- **Architect Agent**: Creates `architecture.md`.
- **Tester Agent**: Creates `tests.md` and validates implementation.
- **Memory Agent**: Evolves system `patterns.md`.
- **Audit Agent**: Logs agent actions to daily audit files.

### 2.3 Tech Stack
- **Backend**: FastAPI (Python 3.x)
- **Frontend**: React 19, Vite, Tailwind CSS, TypeScript
- **Drag & Drop**: Atlassian Pragmatic Drag and Drop
- **State**: File-based (`pipeline-state.json`)

## 3. Kanban Board Requirements

### 3.1 Core Interactions
- **Add Card**: Create a new idea in the `INTAKE` stage with a unique ID and title.
- **Edit Card**: Modify card title, description, priority, and confidence score via a modal.
- **Commenting**: Attach discussions to cards, persisted in the state file.
- **Movement**:
  - Inter-column: Move cards between stages.
  - Intra-column: Reorder cards within a stage (Persistence via `order` field).

### 3.2 Acceptance Criteria
- [x] Stable and unique IDs.
- [x] Optimistic UI updates for creation and movement.
- [x] Persisted state across page refreshes.
- [x] Error handling for failed API calls.
- [x] Clear visual affordances for drag-and-drop.

## 4. Verification Matrix
| Feature | Test Case | Expected Result |
|---|---|---|
| Add Card | Enter ID/Title → Create | Card appears instantly in INTAKE, persists on refresh. |
| Edit Card | Open Modal → Change Title → Save | Title updates immediately, persists on refresh. |
| Comment | Enter Text → Post | Comment appears in card detail, persists on refresh. |
| Move Card | Drag card from A → B | Card moves to new column, state updates on backend. |
| Reorder | Drag card above another in same col | Card order changes, persists on refresh. |

## 5. Known Issues & Pending TODOs

### 5.1 Critical (Should fix before merging to `main`)

| ID | Severity | Issue | Location | Status |
|---|---|---|---|---|
| TODO-01 | 🔴 Critical | `node_modules` directory is committed to the repo — massively inflates repo size and diff. Must be removed and added to `.gitignore`. | `ui/node_modules/` | ⏳ Pending |

### 5.2 High Priority

| ID | Severity | Issue | Location | Status |
|---|---|---|---|---|
| TODO-02 | 🟡 Medium | All API base URLs are hardcoded as `http://localhost:8000` throughout the frontend. Should be extracted to a `VITE_API_URL` environment variable for portability. | `ui/src/App.tsx` | ⏳ Pending |
| TODO-03 | 🟡 Medium | Card `order` is hardcoded to `0` in the drag-move handler. Cards move between columns correctly but intra-column reorder order does not persist to the backend after a drag. | `ui/src/App.tsx` (`onPerformOperation`) | ⏳ Pending |
| TODO-04 | 🟡 Medium | `StateManager` performs plain file I/O with no locking mechanism. Concurrent writes (e.g. from the scheduler and API simultaneously) can cause race conditions and corrupt `pipeline-state.json`. | `api/state_manager.py` | ⏳ Pending |

### 5.3 Low Priority

| ID | Severity | Issue | Location | Status |
|---|---|---|---|---|
| TODO-05 | 🟢 Low | Module-level `orchestrator_instance = Orchestrator()` is instantiated at import time. If `Orchestrator.__init__` performs file I/O or side effects, this may cause issues during testing or cold-start. Should be verified or lazily initialized. | `agents/orchestrator.py` | ⏳ Pending |

### 5.4 Remediation Task Template
When adding new remediation tasks, follow this format:
1. **Status**: Pending / Implemented / Verified
2. **Issue**: Gap description
3. **Source**: Audit/Review finding
4. **Expected Fix**: Description of the required change
5. **Verification**: Required tests/checks to close the task
