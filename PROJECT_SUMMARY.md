# Hermes System - Project Summary

## Purpose

This document is the canonical phase map for the Hermes Multi-Agent Automation System.

It serves four roles:

1. Summarize the current implementation state at the project level.
2. Define the official phased build plan.
3. Capture key implementation decisions that affect execution.
4. Maintain review-created remediation tasks that feed the Superpowers implementation and review loop.

This file should stay concise and execution-oriented. Long-form architectural intent, product behavior, and system design details belong in `memory.md`. Current implementation status belongs in `PROGRESS.md`. Completion rules belong in `VERIFICATION_CRITERIA.md`.

---

## Current Status

The Hermes system design is fully specified, and Phases 0–4 are currently marked as completed in `PROGRESS.md`, with Phase 5 in progress and Phases 6–7 pending. These statuses are operationally useful, but they are still subject to verification by the Superpowers review workflow and the rules in `REVIEW.md` and `VERIFICATION_CRITERIA.md`.

### Current Phase Status Snapshot

| Phase | Title | Current Status |
|---|---|---|
| **Phase 0** | Directory structure + `pipeline-state.json` schema + `ideas.md` format | Completed (subject to audit/review) |
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler | Completed (subject to audit/review) |
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent | Completed (subject to audit/review) |
| **Phase 3** | Telegram notifications + slash commands | Completed (subject to audit/review) |
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow | Completed (subject to audit/review) |
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) | Implemented, pending review | implemented drag-and-drop board and artifact viewer |
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) | Pending |
| **Phase 7** | File watcher / event-driven triggers | Pending |

### Current Execution Strategy

The project now follows this operating model:

1. Review historical phases (0–5) using `SUPERPOWER-REVIEW.prompt.md`, one phase at a time or in small batches.
2. Record any gaps, contradictions, missing verification, or implementation defects as remediation tasks in this file.
3. Implement remediation tasks or pending phases using `SUPERPOWER-IMPLEMENT.prompt.md`.
4. Re-run review after implementation.
5. Only treat work as fully verified when it satisfies `VERIFICATION_CRITERIA.md`.

---

## System Potential

The Hermes system is designed to provide a high-leverage, human-in-the-loop automation platform with the following strengths:

1. **Idea Refinement**: Convert simple idea descriptions into structured specs, architecture, and tests.
2. **Quality Gates**: Use staged review, confidence scoring, and verification to prevent unsafe or low-quality automation from proceeding unchecked.
3. **Continuous Learning**: Learn operator preferences and patterns over time through the brain/memory loop.
4. **Flexible Operation**: Support scheduled automation, review checkpoints, manual triggers, and eventually event-driven execution.
5. **Operational Visibility**: Surface pipeline state through Kanban, Telegram notifications, audit logs, and structured artifacts.

---

## Key Decisions

The following implementation decisions are currently considered resolved and should be treated as part of the working baseline unless changed deliberately.

### Technology Stack
- **Agent Logic**: Python
- **UI**: Node/React

### Docker Sandboxing
- **Tester Agent** uses Docker Compose for sandbox provisioning.

### Telegram Integration
- Use the existing Hermes Telegram integration.
- Telegram is used for notifications and slash commands, not for inline review comments.

### ID Management
- Idea IDs are auto-incremented by the Orchestrator based on existing ideas.
- The Orchestrator automatically creates new `ID-XXX/` directories as needed.

### Heartbeat Schedule
- Current baseline: daily at 10 PM.
- May increase later to up to 4 runs per day if needed.

### UI Hosting
- Local hosting only.

### Repository Strategy
- Single repo / single codebase for agents, orchestrator, UI, and brain tools.

---

## Source of Truth Hierarchy

When planning, implementing, or reviewing work, use the following precedence:

1. `memory.md` — product vision, architecture, constraints, behavior, and design intent
2. `PROJECT_SUMMARY.md` — phase map, implementation decisions, remediation tasks
3. `PROGRESS.md` — claimed implementation state and current focus
4. `VERIFICATION_CRITERIA.md` — Definition of Done and verification gate
5. `REVIEW.md` — review behavior, severity, and reporting rules

If these files conflict, resolve the conflict explicitly rather than silently assuming one is correct.

---

## Phased Build Plan

This is the official build plan for Hermes.

| Phase | What to Build |
|---|---|
| **Phase 0** | Directory structure + `pipeline-state.json` schema + `ideas.md` format |
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler |
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent |
| **Phase 3** | Telegram notifications + slash commands |
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow |
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) |
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) |
| **Phase 7** | File watcher / event-driven triggers |

---

## Phase Details

### Phase 0 — Foundation Files and Structure
Scope:
- Create the repository/directory structure for automation ideas and pipeline state.
- Define the `pipeline-state.json` schema.
- Define the `ideas.md` format and intake model.

Expected outcome:
- A stable file/folder foundation for all subsequent pipeline work.

### Phase 1 — Orchestrator and Refiner
Scope:
- Implement the Orchestrator.
- Implement the Refiner Agent.
- Implement the heartbeat scheduler.

Expected outcome:
- Ideas can be detected, queued, refined, and advanced automatically when not blocked on review.

### Phase 2 — Core Agent Expansion
Scope:
- Implement the Architect Agent.
- Implement the Tester Agent.
- Implement the Audit Agent.

Expected outcome:
- The system can generate architecture and testing artifacts and maintain a structured audit trail.

### Phase 3 — Telegram Integration
Scope:
- Implement Telegram notifications.
- Implement slash commands for pipeline interaction.

Expected outcome:
- The owner can monitor the system and trigger actions through Telegram without using it for inline document review.

### Phase 4 — Memory and Brain Loop
Scope:
- Implement the Memory Agent.
- Implement the nightly brain loop.
- Implement the pending-updates review flow.

Expected outcome:
- The system can observe recurring patterns, propose updates, and evolve with owner approval.

### Phase 5 — Kanban UI (Phase 1)
Scope:
- Build a Kanban board with columns matching pipeline stages.
- Show cards with key metadata (ID, title, priority, confidence score, stage, timestamps).
- Support drag/drop stage movement.
- Provide a detail view for artifacts and review files.

Expected outcome:
- The owner can inspect and manage pipeline state through a local UI.

### Phase 6 — Kanban UI (Phase 2)
Scope:
- Add inline review editing.
- Add real-time updates for agent progress.
- Add richer UI navigation and linked workflow affordances.

Implementation:
- Added `POST /api/item/.../content` endpoint with atomic writes and strict validation.
- Integrated debounced textarea editor in `ArtifactViewer.tsx` for `review.md`.
- Implemented 10s polling in `App.tsx` with Page Visibility API integration.


Expected outcome:
- The UI becomes the primary operational surface for human review and monitoring.

### Phase 7 — Event-Driven Triggers
Scope:
- Add file watcher or event-driven execution triggers.
- React to Kanban actions or file changes without waiting for the next heartbeat.

Expected outcome:
- The system gains faster responsiveness while preserving safety and review controls.

### Phase 7 Remediation Tasks
### R7.1 — Implement file watcher on `automation-ideas/` directory
- **Status**: Verified
- **Issue**: No file watcher implementation exists for the automation-ideas directory
- **Source**: Phase 7 implementation.
- **Expected Fix**: Implement file system monitoring for the automation-ideas directory to detect file changes.
- **Verification**: File watcher should detect creation, modification, and deletion events in the directory.
- **Implementation**: Implemented using `watchdog` library in `agents/watcher.py`. Verified with `tests/test_watcher.py`.

### R7.2 — Wire file watcher events to Orchestrator
- **Status**: Implemented, pending review
- **Issue**: File watcher events need to be integrated with the Orchestrator to trigger pipeline actions
- **Source**: Phase 7 implementation.
- **Expected Fix**: Connect file watcher events to the Orchestrator to automatically trigger pipeline when new ideas are added or review files are updated.
- **Verification**: File events should trigger appropriate pipeline execution.
- **Implementation**: Refactored `Orchestrator` into a class and integrated `handle_new_idea` and `handle_review_update` methods. Verified with `tests/test_watcher.py`.

### R7.3 — Implement debounce/throttle mechanism
- **Status**: Verified
- **Issue**: Rapid file events should be debounced to prevent multiple triggers
- **Source**: Phase 7 implementation.
- **Expected Fix**: Implement a debounce mechanism to prevent rapid re-triggers from file system events.
- **Verification**: Multiple rapid file changes should be properly debounced.
- **Implementation**: Added per-file timestamp tracking in `HermesFileHandler` to enforce a 2-second debounce interval. Verified with `tests/test_watcher.py`.

### R7.4 — Write tests for file watcher
- **Status**: Verified
- **Issue**: File watcher needs comprehensive unit and integration tests
- **Source**: Phase 7 implementation.
- **Expected Fix**: Write tests covering file creation, modification, and deletion events.
- **Verification**: All file watcher tests should pass.
- **Implementation**: Implemented unit tests in `tests/test_watcher.py` and integration tests in `tests/test_watcher_integration.py`. All tests pass.

### Phase 1 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 2 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 3 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 4 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 5 Remediation Tasks
### R5.1 — Add frontend unit/integration tests for Kanban UI
- **Status**: Verified
- **Issue**: The Kanban UI now has automated tests for drag-and-drop logic and artifact loading.
- **Source**: Phase 5 review.
- **Expected Fix**: Tests have been implemented using Vitest/React Testing Library for `KanbanBoard` and `ArtifactViewer`.
- **Verification**: Test suite passes for card movement and artifact fetching. All 16 tests across KanbanColumn and ArtifactViewer components pass successfully.
- **Implementation**: Created 16 tests across KanbanColumn and ArtifactViewer components. All tests pass.

### R5.6 — Fix ArtifactViewer fetch logic and tests
- **Status**: Verified
- **Issue**: `ArtifactViewer` fails tests due to mock mismatch (expects `json` instead of `text`). Additionally, if all artifact fetches fail, the component renders the "No artifacts" state instead of the "Error" state because errors are caught inside the loop.
- **Source**: Phase 5 review.
- **Expected Fix**: 
  1. Update `ArtifactViewer.test.tsx` to use `res.text()` and match expected content.
  2. Update `ArtifactViewer.tsx` to track if any fatal error occurred during the batch fetch to trigger the error UI.
- **Verification**: All `ArtifactViewer.test.tsx` tests pass.
- **Implementation**: Updated `ArtifactViewer.tsx` to track `hasError` during batch fetch and throw if no artifacts are found while errors occurred. Fixed all mocks in `ArtifactViewer.test.tsx` to use `Response` objects and `res.text()`. All 8 tests pass.

### R5.2 — Fix Path Traversal in Artifact API
- **Status**: Verified
- **Issue**: `item_id` is used directly in `os.path.join` in the artifact endpoint, allowing potential directory traversal.
- **Source**: Exhaustive security review.
- **Expected Fix**: Sanitize `item_id` to ensure it contains no path separators or use a strictly validated alphanumeric pattern.
- **Verification**: Attempt to fetch a file outside the `requirements/` directory using `../` and verify a 400/404 response.
- **Implementation**: Replaced blacklist-based sanitization (`..`, `/`, `\\` checks) with strict whitelist regex `^[A-Z0-9-]+$` in `get_artifact` endpoint. Added 7 new tests covering path traversal attempts, special characters, dots, spaces, null bytes, lowercase normalization, and valid artifact retrieval. All 144 tests pass.

### R5.3 — ID Case-Sensitivity Normalization
- **Status**: Verified
- **Issue**: IDs are not normalized (e.g., `ID-001` vs `id-001`), which could lead to state mismatches or duplicate entries on different filesystems.
- **Source**: Verification criteria audit.
- **Expected Fix**: Normalize all `item_id` inputs to uppercase (or consistent case) before filesystem access or state lookups.
- **Verification**: Verify that requesting `id-001` via API correctly maps to `ID-001` in the state.
- **Implementation**: Added `item_id.upper()` normalization at all entry points: `agents/state.py` (get_item, update_item, add_history_entry, create_item_directory, get_next_id), `api/main.py` (move_item endpoint), `agents/telegram.py` (_cmd_run, _cmd_approve, _cmd_redo). Added 8 new tests covering lowercase, mixed-case, and case-insensitive directory creation. All 152 tests pass.

### R5.4 — Fix Kanban drag-and-drop stage lookup
- **Status**: Verified
- **Issue**: `handleDragEnd` in `App.tsx` incorrectly tries to find the stage of the target item using `i.id`, which does not exist on the raw state items.
- **Source**: Logic audit.
- **Expected Fix**: Update the lookup to use `state.items[overId]?.stage`.
- **Verification**: Manually verify that dragging a card onto another card in a different column correctly moves the dragged card to that column.
- **Implementation**: The `handleDragEnd` function already correctly uses `state.items[overId]` for card-to-card stage lookup (lines 80-84). Added 7 new tests in `ui/src/App.test.tsx` covering: column drop, card-to-card drop, same-stage no-op, null over guard, nonexistent item guard, and explicit card-to-card stage resolution. All 23 UI tests pass.

### R5.5 — UI Type Safety and Permission Optimization
- **Status**: Verified
- **Issue**: `App.tsx` uses `any` for pipeline items, and `.claude/settings.json` needs updating for new API paths.
- **Source**: Clean Code & Verification Criteria audit.
- **Expected Fix**: Define a `PipelineItem` interface and update `.claude/settings.json` using `fewer-permission-prompts`.
- **Verification**: No TS errors in `App.tsx` and reduced permission prompts during UI interaction.
- **Implementation**: Created `ui/src/types.ts` with `PipelineItem`, `PipelineState`, `KanbanCardData`, and `DragEndHandler` types. Updated `App.tsx` to use `PipelineState` instead of inline type. Updated `KanbanColumn.tsx` to use shared `KanbanCardData` type. Removed all `any` types from `App.test.tsx` (7 mocks + 7 test functions). Updated `.claude/settings.local.json` with expanded allowlist for npm, npx, uv, python, docker, curl, mkdir, ls, cp, rm commands. All 23 UI tests pass.


### Phase 6 Remediation Tasks
### R6.1 — Add frontend tests for inline review editing
- **Status**: Verified
- **Issue**: Tests have been implemented in ui/src/components/ArtifactViewer.edit.test.tsx
- **Source**: Phase 6 review and implementation.
- **Expected Fix**: Tests already implemented and verified.
- **Verification**: All 3 tests in ArtifactViewer.edit.test.tsx pass for editing, debouncing, and saving states.

### R6.2 — Add frontend tests for real-time polling
- **Status**: Verified
- **Issue**: The 10s polling and Page Visibility API logic in `App.tsx` is not covered by tests.
- **Source**: Phase 6 review.
- **Expected Fix**: Add tests to verify `fetchState` is called periodically and stops when `document.visibilityState === 'hidden'`.
- **Verification**: Test suite confirms polling behavior and visibility-based pausing.

### Phase 7 Remediation Tasks
- No remediation tasks recorded yet.

---

## Remediation Task Template

Use this format when adding a new remediation item:

### R<phase>.<index> — Short Task Title
- **Status**: Pending
- **Issue**: Clear description of the observed gap, contradiction, missing behavior, or verification failure.
- **Source**: Review finding, spec mismatch, verification failure, regression, or documentation gap.
- **Expected Fix**: What must change in code, tests, or documentation.
- **Verification**: Exact tests, checks, or manual validation needed before this can be marked verified.

Example:

### R5.1 — Kanban drag/drop does not persist stage changes
- **Status**: Pending
- **Issue**: Cards can be moved visually, but the new stage is not persisted to pipeline state.
- **Source**: Phase 5 audit review.
- **Expected Fix**: Update the UI and backend integration so drag/drop writes the correct stage to `pipeline-state.json` or the backing API.
- **Verification**: Automated test for stage update behavior plus manual UI check confirming that a moved card remains in the new column after refresh.

---

## Planned Next Steps

Unless review changes priorities, the expected sequence is:

1. Audit Phases 0–5 using `SUPERPOWER-REVIEW.prompt.md`.
2. Record remediation tasks in this file for any gaps found.
3. Fix remediation tasks and complete remaining Phase 5 work using `SUPERPOWER-IMPLEMENT.prompt.md`.
4. Re-review all fixes until Phases 0–5 are verified.
5. Proceed to Phase 6 and Phase 7 using the same implementation-review loop.

---

## Maintenance Rules

Keep this file concise and structured.

Update this file when:
- a phase definition changes,
- a key implementation decision changes,
- review creates new remediation tasks,
- remediation tasks are split, refined, deferred, or verified,
- the planned next steps materially change.

Do not use this file for:
- long architectural deep-dives,
- detailed progress logs,
- exhaustive review reports,
- transient debugging notes.

Those belong in `memory.md`, `PROGRESS.md`, or review output artifacts.

---

*This document is the canonical project execution map for Hermes. It should remain stable, operational, and easy for Superpowers to parse and update.*

---

## Kanban-Fix Branch Remediation Tasks

> These tasks were identified during the `kanban-fix` branch review (May 20, 2026). They must be resolved before merging to `main`.

### R-KF-01 — Remove `node_modules` from repository
- **Status**: Pending
- **Issue**: The `node_modules` directory was accidentally committed in commit `99ca130`, bloating the repo by ~541k lines. This is a critical repo hygiene issue.
- **Source**: kanban-fix branch review.
- **Expected Fix**: Add `ui/node_modules/` to `.gitignore`, then remove the directory from git history using `git rm -r --cached ui/node_modules`.
- **Verification**: Confirm `ui/node_modules/` is listed in `.gitignore` and no longer tracked by git. Repo size should drop significantly.

### R-KF-02 — Extract hardcoded API base URL to environment variable
- **Status**: Pending
- **Issue**: All fetch calls in `ui/src/App.tsx` are hardcoded to `http://localhost:8000`. This prevents the UI from working in any non-local environment.
- **Source**: kanban-fix branch review.
- **Expected Fix**: Introduce a `VITE_API_URL` env variable (default `http://localhost:8000`) and replace all hardcoded URLs with `import.meta.env.VITE_API_URL`.
- **Verification**: UI works with a custom `VITE_API_URL` set in `.env.local`. No raw `localhost:8000` strings remain in source.

### R-KF-03 — Fix hardcoded `order: 0` in drag-move handler
- **Status**: Pending
- **Issue**: The `onPerformOperation` handler in `ui/src/App.tsx` sends `order: 0` to the backend during a drag-move. Intra-column card reordering is therefore not persisted correctly.
- **Source**: kanban-fix branch review (TODO comment present in code).
- **Expected Fix**: Calculate the correct target index from the drop destination and pass it as `order` in the move payload. The backend `move_item` should persist this value.
- **Verification**: Drag a card within a column, refresh the page — card remains in the new position.

### R-KF-04 — Add file locking to `StateManager` to prevent race conditions
- **Status**: Pending
- **Issue**: `api/state_manager.py` uses plain `open()` for reads and writes with no locking. Concurrent requests (e.g., scheduler + API) can cause lost writes or corrupted `pipeline-state.json`.
- **Source**: kanban-fix branch review.
- **Expected Fix**: Use `filelock` (or Python's `threading.Lock`) to serialize access to `pipeline-state.json` in `load_state` / `save_state`.
- **Verification**: Concurrent API calls do not result in corrupted state. A stress test with simultaneous writes should pass.

### R-KF-05 — Verify module-level `Orchestrator()` instantiation at import time
- **Status**: Pending
- **Issue**: `agents/orchestrator.py` instantiates `orchestrator_instance = Orchestrator()` at module import time. If `__init__` has side effects (file I/O, network), this can cause issues during testing or startup.
- **Source**: kanban-fix branch review.
- **Expected Fix**: Audit `Orchestrator.__init__` for side effects. If found, convert to lazy initialization (e.g., a `get_orchestrator()` singleton factory).
- **Verification**: Importing `agents.orchestrator` in a test environment does not cause file I/O or errors. Existing tests continue to pass.
