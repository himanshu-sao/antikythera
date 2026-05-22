# 🏁 Hermes Verification Criteria (Definition of Done)

This document serves as the absolute completion gate for the Hermes Multi-Agent Automation System. No phase, remediation task, or feature is considered "Verified" until it satisfies the criteria listed here.

## 🛠 Global Verification Standards
Regardless of the phase, all implementation work must meet these baseline standards:
- **ID Normalization**: All Idea IDs (e.g., `ID-001`) must be coerced to uppercase across the entire stack.
- **Type Safety**: No `any` types in TypeScript; Pydantic models used for all API request/response bodies in Python.
- **Error Handling**: No swallowed exceptions. All API errors must return a structured JSON response with a `detail` field.
- **State Integrity**: No direct file writes to `pipeline-state.json` outside of the `StateManager` class.
- **Logging**: All agent actions must be recorded via the Audit Agent; no silent failures.
- **Clean Code**: No `console.log` or `print` statements left in production code.

---

## 📋 Phase-Specific Criteria

### Phase 0: Foundation
- [ ] **Directory Structure**: All folders defined in `memory.md` (`automation-ideas/`, `requirements/`, `audit/`, `brain/`) exist.
- [ ] **State Schema**: `pipeline-state.json` initializes with a valid `last_heartbeat` and empty `items` object.
- [ ] **Intake Format**: `ideas.md` successfully accepts the `- [ID-XXX] Title | Priority: X` format.

### Phase 1: Core Loop
- [ ] **Orchestrator Trigger**: The heartbeat scheduler triggers the Orchestrator at the configured intervals.
- [ ] **Refinement Flow**: Orchestrator $\rightarrow$ Refiner Agent $\rightarrow$ `requirements/ID-XXX/spec.md` produced.
- [ ] **State Update**: `pipeline-state.json` is updated to `REVIEW_SPEC` after `spec.md` is written.
- [ ] **Confidence Scoring**: A `confidence_score` (0-100) is written to the state file by the Refiner.

### Phase 2: Artifact Generation
- [ ] **Architecture Flow**: `spec.md` $\rightarrow$ Architect Agent $\rightarrow$ `requirements/ID-XXX/architecture.md` produced.
- [ ] **Testing Flow**: `architecture.md` $\rightarrow$ Tester Agent $\rightarrow$ `requirements/ID-XXX/tests.md` produced.
- [ ] **Audit Trail**: Every transition in Phase 1 & 2 has a corresponding entry in `audit/YYYY-MM-DD.md`.
- [ ] **Sandbox Validation**: Tester Agent verifies that `tests.md` is based on a successful dry-run in the Docker sandbox.

### Phase 3: Remote Monitoring (Telegram)
- [ ] **Notifications**: A Telegram message is sent immediately upon any stage transition (e.g., `REFINEMENT` $\rightarrow$ `REVIEW_SPEC`).
- [ ] **Slash Commands**: `/status` returns a correct summary of all items in `pipeline-state.json`.
- [ ] **Manual Trigger**: `/run ID-XXX` successfully forces the pipeline to process a specific item.

### Phase 4: The Brain Loop (Learning)
- [ ] **Pattern Extraction**: Memory Agent identifies a recurring theme from `review.md` and writes it to `brain/pending-updates.md`.
- [ ] **Human-in-the-Loop**: Updating `patterns.md` only occurs AFTER the owner sets `review_status: APPROVED` in `pending-updates.md`.
- [ ] **Versioning**: The previous version of `patterns.md` is archived in `brain/history/` before an update.

### Phase 5: Kanban UI (Basic)
- [ ] **State Sync**: UI correctly renders columns and cards based on `pipeline-state.json`.
- [ ] **Drag-and-Drop**: Moving a card between columns triggers a `POST /api/move` and updates the backend state.
- [ ] **Optimistic UI**: Cards move instantly in the UI; if the API fails, the card snaps back to its original position.
- [ ] **Persistence**: Page refresh does not lose card positions or new items.

### Phase 6: Kanban UI (Advanced)
- [ ] **Inline Review**: Editing `review.md` in the UI updates the file on disk and updates `review_status` in the state file.
- [ ] **Real-time Polling**: The UI reflects agent progress (e.g., a card moving from `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH`) without a manual refresh.
- [ ] **Search & Filter**: Filtering by Priority, Stage, or Search Text correctly hides/shows cards without page reloads.

### Phase 7: Event-Driven Triggers
- [ ] **File Watcher**: Modifying `automation-ideas/ideas.md` triggers the Orchestrator within $< 5$ seconds.
- [ ] **Debounce**: Rapid sequential saves to `ideas.md` result in only one Orchestrator trigger.
- [ ] **Trigger Validation**: The system correctly identifies which new IDs were added and only processes those.

### Kanban-Fix & UX Enhancements
- [ ] **Card Deletion**: Using the "Delete" button in `CardEditor` removes the item from `pipeline-state.json` and returns a 200 OK from `DELETE /api/item/{id}`.
- [ ] **Toast Notifications**: All native `alert()` calls are replaced by `react-hot-toast` notifications for both success and error states.
- [ ] **API Portability**: The frontend uses `VITE_API_URL` (with a localhost fallback) instead of hardcoded strings.
- [ ] **State Robustness**: Concurrent API requests do not corrupt `pipeline-state.json` (verified via lock-file or atomic `os.replace` check).
- [ ] **User Identity**: Comment authors are persisted via `localStorage` rather than hardcoded as 'Current User'.

---

## 🧪 Verification Methods

| Method | Description | Requirement |
|---|---|---|
| **Automated Test** | Playwright E2E or Pytest unit test | Must pass with 0 failures. |
| **Log Audit** | Checking `audit/` or `pipeline-state.json` | Evidence of action must exist. |
| **Manual Check** | Human operator verifies UI/File behavior | Documented as "Verified" in `PROJECT_STATUS.md`. |
| **Schema Check** | Validating JSON against a spec | Must be valid JSON and match Pydantic models. |
