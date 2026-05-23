# 🤖 Hermes AI Context & Briefing

**Purpose**: This file provides a high-density, token-efficient briefing for AI agents to understand the Hermes project, its architecture, and its operational constraints.

---

## 🎯 Core Identity
Hermes is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It transforms simple ideas into technical specifications, architectures, and verified code through a gated, stage-based workflow.

## 📚 Hierarchy of Truth (Precedence)
When information conflicts, follow this order:
1.  **`memory.md`**: Foundational patterns and learned behaviors.
2.  **`PROJECT_STATUS.md`**: The current implementation roadmap and technical baseline.
3.  **`PROGRESS.md`**: Real-time status of completed/pending tasks.
4.  **`VERIFICATION_CRITERIA.md`**: The absolute "Definition of Done".

## 🏗 Mental Model

### 1. The Pipeline (Linear Flow)
`INTAKE` $\rightarrow$ `REFINEMENT` $\rightarrow$ `REVIEW_SPEC` $\rightarrow$ `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH` $\rightarrow$ `TESTING` $\rightarrow$ `REVIEW_TEST` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `DONE`

### 2. The Agent Roster
- **Orchestrator**: State machine, agent dispatcher, and trigger manager.
- **Refiner**: Idea $\rightarrow$ `spec.md`.
- **Architect**: `spec.md` $\rightarrow$ `architecture.md`.
- **Tester**: `architecture.md` $\rightarrow$ `tests.md` (runs in Docker).
- **Memory**: Analyzes logs $\rightarrow$ evolves `brain/patterns.md`.
- **Audit**: Passive observer; logs all actions to `audit/`.

## 🛠 Technical Constraints (Non-Negotiable)
- **ID Normalization**: All Idea IDs (e.g., `ID-001`) MUST be **UPPERCASE**.
- **State Integrity**: Never write to `pipeline-state.json` directly. Use the `StateManager` or the API.
- **Atomic Operations**: All file writes must be atomic (use `os.replace`).
- **Secret Management**: Never hardcode secrets. Use `.env` files and environment variables.
- **Idempotency**: Every agent action must be idempotent; re-running a stage should not corrupt the state.

## 🗺️ Critical File Map
- `automation-ideas/ideas.md`: Primary input for new ideas.
- `automation-ideas/pipeline-state.json`: Single source of truth for task stages.
- `automation-ideas/brain/patterns.md`: The system's learned architectural patterns.
- `registry/automation_registry.json`: Database for recurring/event-driven tasks.
- `automation-ideas/requirements/{ID}/`: Contains all artifacts (`spec.md`, `architecture.md`, `tests.md`) for a specific task.

## 🔄 Standard Operating Procedures (SOPs)

### **Task Execution**
1. Check `pipeline-state.json` to determine the current stage.
2. Read the required input artifact (e.g., `spec.md` for the Architect).
3. Generate the output artifact.
4. Update the state via the Orchestrator/API to transition to the next stage or `REVIEW_*`.

### **Refinement Loop (HITL)**
If a technical artifact (e.g., `spec.md`) is manually edited by a user, the Orchestrator will detect the change and **regress the task stage** (e.g., from `ARCHITECTURE` back to `REFINEMENT`) to ensure consistency.

### **Pattern Promotion (Continuous Learning)**
Successful technical artifacts (specs, architectures, tests) can be analyzed and promoted to a global pattern library to improve future automation quality.

--- HERMES_PRODUCT_SPEC.md ---
# 🚀 Hermes Product Specification

## 1. Vision & Purpose
Hermes is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It converts simple idea descriptions into structured specifications, architecture, and verified tests, allowing a human operator to review and approve progress via a Kanban UI.

## 2. System Architecture

### 2.1 Pipeline Workflow
Ideas move through a linear sequence of stages:
`INTAKE` → `REFINEMENT` → `REVIEW_SPEC` → `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH` $\rightarrow$ `TESTING` $\rightarrow$ `REVIEW_TEST` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `DONE`

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
| TODO-01 | ✅ Resolved | `node_modules` directory is committed to the repo — massively inflates repo size and diff. Must be removed and added to `.gitignore`. | `ui/node_modules/` | Completed |

### 5.2 High Priority

| ID | Severity | Issue | Location | Status |
|---|---|---|---|---|
| TODO-02 | ✅ Resolved | All API base URLs are hardcoded as `http://localhost:8000` throughout the frontend. Should be extracted to a `VITE_API_URL` environment variable for portability. | `ui/src/App.tsx` | Completed |
| TODO-03 | ✅ Resolved | Card `order` is hardcoded to `0` in the drag-move handler. Cards move between columns correctly but intra-column reorder order does not persist to the backend after a drag. | `ui/src/App.tsx` (`onPerformOperation`) | Completed |
| TODO-04 | 🟡 Medium | `StateManager` performs plain file I/O with no locking mechanism. | `api/state_manager.py` | ✅ Fixed |

### 5.3 Low Priority

| ID | Severity | Issue | Location | Status |
|---|---|---|---|---|
| TODO-05 | ✅ Resolved | Module-level `orchestrator_instance = Orchestrator()` is instantiated at import time. If `Orchestrator.__init__` performs file I/O or side effects, this may cause issues during testing or cold-start. Should be verified or lazily initialized. | `agents/orchestrator.py` | Completed |

### 5.4 Remediation Task Template
When adding new remediation tasks, follow this format:
1. **Status**: Pending / Implemented / Verified
2. **Issue**: Gap description
3. **Source**: Audit/Review finding
4. **Expected Fix**: Description of the required change
5. **Verification**: Required tests/checks to close the task


---

## 6. Proposed Enhancements

> These enhancements were identified during the deep-dive review of the `kanban-fix` branch source code. They go beyond the existing bug/TODO items and represent new capabilities or structural improvements to the Kanban system.

### 6.1 Backend — API & State Layer

#### ENH-01: Add `DELETE /api/item/{item_id}` endpoint
- **Area**: `api/main.py`, `api/state_manager.py`
- **Description**: There is currently no way to delete a card. The backend has no `DELETE` endpoint and `StateManager` has no `delete_item` method. A soft-delete approach (setting `stage: "ARCHIVED"`) would preserve history; a hard-delete would remove the item entirely from `pipeline-state.json`.
- **Suggested Implementation**:
  - Add `StateManager.delete_item(item_id)` that removes the key from `items` dict and calls `save_state`.
  - Add `DELETE /api/item/{item_id}` in `main.py`.
  - On the frontend, add a delete button (with confirmation dialog) in the `CardEditor` modal.
- **Impact**: Allows the board to be kept clean of stale/cancelled ideas.

#### ENH-02: Add CORS middleware to FastAPI app
- **Area**: `api/main.py`
- **Description**: The API has no CORS configuration. While it currently runs only locally, adding `CORSMiddleware` ensures the frontend can communicate with the backend without browser errors when served on different ports, and makes the system ready for any future non-local deployment.
- **Suggested Implementation**:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
  ```
- **Impact**: Low risk, prevents potential browser CORS blocks.

#### ENH-03: Add atomic writes to `StateManager` using a temp file + rename pattern
- **Area**: `api/state_manager.py`
- **Description**: `save_state` writes directly to `pipeline-state.json`. If the process crashes mid-write, the file will be corrupted. Using an atomic write pattern (write to a `.tmp` file, then `os.replace()`) prevents data loss.
- **Suggested Implementation**:
  ```python
  def save_state(self, state):
      tmp_path = self.state_path + ".tmp"
      with open(tmp_path, "w") as f:
          json.dump(state, f, indent=2)
      os.replace(tmp_path, self.state_path)
  ```
- **Impact**: Prevents state file corruption on crash.

#### ENH-04: Add `DELETE /api/item/{item_id}/comment/{comment_id}` endpoint
- **Area**: `api/main.py`, `api/state_manager.py`
- **Description**: Once a comment is posted, it cannot be removed. A delete endpoint for comments would round out the commenting workflow.
- **Suggested Implementation**: Filter `items[item_id]["comments"]` to exclude the given `comment_id` and save state.
- **Impact**: Improves comment UX, avoids permanent bloat from test/mistake comments.

#### ENH-05: Add `POST /api/items/reorder` endpoint for bulk intra-column reordering
- **Area**: `api/main.py`, `api/state_manager.py`
- **Description**: The current move endpoint updates `stage` and a single `order` value. A dedicated reorder endpoint that accepts an ordered list of item IDs for a given stage would allow the frontend to send the full updated sequence after a drag, making intra-column ordering fully persistent.
- **Suggested Implementation**:
  ```python
  class ReorderRequest(BaseModel):
      stage: str
      ordered_ids: list[str]

  @app.post("/api/items/reorder")
  async def reorder_items(request: ReorderRequest): ...
  ```
- **Impact**: Directly fixes TODO-03 (hardcoded `order: 0` in drag-move handler).

---

### 6.2 Frontend — Components & UX

#### ENH-06: Replace hardcoded `'Current User'` author with a configurable user identity
- **Area**: `ui/src/components/CommentSection.tsx`
- **Description**: The comment author is hardcoded as `'Current User'` in `handleSubmit`. This should be driven by a configurable value — even a simple `localStorage`-persisted username set on first use would be a significant improvement.
- **Suggested Implementation**: Add a `useLocalStorage('hermes_username', 'Operator')` hook and pass it as the author in the comment payload.
- **Impact**: Improves auditability of comments.

#### ENH-07: Add delete card button to `CardEditor` with confirmation
- **Area**: `ui/src/components/CardEditor.tsx`, `ui/src/App.tsx`
- **Description**: There is no way to delete a card from the UI. The `CardEditor` modal is the natural place to add a "Delete Card" button, behind a confirmation prompt.
- **Suggested Implementation**: Add a destructive `Delete` button in the modal footer. On click, show a `window.confirm()` or inline confirmation, then call a new `onDelete(itemId)` prop that triggers the `DELETE /api/item/{item_id}` endpoint (ENH-01).
- **Impact**: Completes the full CRUD lifecycle on the board.

#### ENH-08: Add toast notifications instead of `alert()` for user feedback
- **Area**: `ui/src/App.tsx`, `ui/src/components/CommentSection.tsx`, `ui/src/components/CardEditor.tsx`
- **Description**: Error and success feedback currently uses native `alert()` and `console.error()`. These are blocking and do not match the visual style of the app. A lightweight toast system (e.g., `react-hot-toast` or a custom implementation) would provide non-blocking, styled feedback.
- **Suggested Implementation**: Install `react-hot-toast`, wrap app in `<Toaster />`, and replace all `alert(...)` calls with `toast.error(...)` / `toast.success(...)`.
- **Impact**: Major UX improvement with minimal effort.

#### ENH-09: Add visual empty-state placeholder to `KanbanColumn`
- **Area**: `ui/src/components/KanbanColumn.tsx`
- **Description**: When a column has no cards, it shows an empty white box with no affordance. A subtle empty-state message (e.g., "No items in this stage") with a dashed border improves discoverability and drop-target clarity.
- **Suggested Implementation**: Conditionally render a placeholder `div` when `items.length === 0`.
- **Impact**: Improves UX, especially for the initial empty board state.

#### ENH-10: Add stage history timeline to card detail view
- **Area**: `ui/src/components/CardEditor.tsx`, `ui/src/types.ts`
- **Description**: The `PipelineItem` type already has a `history: Array<{ stage, at, agent? }>` field, but the `CardEditor` modal does not display it. Rendering this as a simple timeline in the editor would give operators full visibility into a card's progression.
- **Suggested Implementation**: Add a collapsible "History" section at the bottom of the `CardEditor` modal that maps over `initialData.history` (passed via `PipelineItem`).
- **Impact**: Provides valuable audit trail visibility directly in the UI.

#### ENH-11: Show card `updated_at` / `created_at` relative timestamps on the card
- **Area**: `ui/src/components/KanbanColumn.tsx` (`KanbanCard`)
- **Description**: Cards currently show ID, title, priority badge, and confidence score, but no timestamps. Showing "Updated 2 hours ago" on the card body improves at-a-glance freshness awareness.
- **Suggested Implementation**: Pass `updated_at` from `PipelineItem` through `BoardCard` and render it using a `formatDistanceToNow` helper (from `date-fns` or a small custom util).
- **Impact**: Low effort, high visibility improvement.

#### ENH-12: Debounce polling when tab is active to reduce unnecessary requests
- **Area**: `ui/src/App.tsx`
- **Description**: Polling fires every 10 seconds regardless of user activity. Adding a debounce or back-off on error (e.g., slow down to 30s after 3 consecutive failures) would reduce noise during backend downtime.
- **Suggested Implementation**: Track a `consecutiveErrors` ref; if it exceeds 3, switch interval to 30s. Reset on success.
- **Impact**: Makes the frontend more resilient during backend restarts.

---

### 6.3 Code Quality & Architecture

#### ENH-13: Extract API base URL to a shared constant / env variable
- **Area**: `ui/src/App.tsx`, `ui/src/components/CommentSection.tsx`
- **Description**: `http://localhost:8000` is referenced in at least 5 places across two files. A single `API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'` constant in a `ui/src/config.ts` module would fix TODO-02 and reduce future maintenance effort.
- **Impact**: Directly resolves TODO-02 from the known issues list.

#### ENH-14: Add `PipelineItem` missing fields to `BoardCard` type
- **Area**: `ui/src/types.ts`
- **Description**: `PipelineItem` has `history`, `blocked_reason`, `assigned_agent`, `review_status`, and `created_at` fields that are not present in `BoardCard`. This means they are silently dropped in `boardAdapter.ts` and unavailable to components. Extending `BoardCard` (or making it extend `PipelineItem`) would make all item data available without extra API calls.
- **Impact**: Unlocks ENH-10 and ENH-11 without API changes.

#### ENH-15: Add loading skeleton UI instead of plain "Loading..." text
- **Area**: `ui/src/App.tsx`
- **Description**: The initial load state shows a plain `Loading...` centered div. A skeleton column layout (greyed-out placeholder cards) would provide a better perceived performance experience.
- **Suggested Implementation**: Render `STAGES.map(() => <SkeletonColumn />)` while `loading === true`.
- **Impact**: Low effort, improves perceived load time.



---

### 6.4 Pattern Promotion (Continuous Learning)

#### ENH-16: Implement Pattern Promotion logic
- **Area**: `api/main.py`, `api/state_manager.py`, `ui/src/components/ArtifactViewer.tsx`
- **Description**: Add an endpoint to promote a successful technical artifact to the global pattern library.
- **Suggested Implementation**:
  - Add `POST /api/item/{id}/promote-pattern` in `main.py`.
  - Implementation should extract key insights/patterns from the artifact and write to `automation-ideas/brain/patterns.md`.
- **Impact**: Enables the system to learn from successful agent runs and user approvals.

---

## 7. Implementation Approach

- **Single codebase** within Hermes (local)
- **Single repo** — all agents, orchestrator, UI, and brain tools live together
- This enables the Memory Agent to learn cross-cutting patterns (secrets, PII, stack) that apply to the codebase itself
- Language: Python for agent logic; Node/React for UI
- Hermes integration: local MCP server already running with Telegram

---

## 8. Sample Notification (Telegram)

```
🔔 [Hermes Pipeline] ID-001 ready for review

Stage: REVIEW_SPEC
Title: Shell script to auto assign vulnerability tickets
Confidence: 82/100

📄 spec.md has been written.
Please review: automation-ideas/requirements/ID-001/review.md

Use /status for full pipeline overview.
```

---

*This document is the living reference for the system. Update it as decisions are made.*



--- README.md ---
# 🚀 Hermes Multi-Agent Automation System

Hermes is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It converts simple idea descriptions into structured specifications, architecture, and verified tests, allowing a human operator to review and approve progress via a Kanban UI and Telegram.

## 🌟 Vision
The goal of Hermes is to provide a high-leverage platform where AI agents handle the "heavy lifting" of software engineering (refining requirements, designing architecture, writing tests), while the human maintains absolute control through gated review stages.

## 🛠 Tech Stack
- **Agent Logic**: Python 3.x
- **UI**: React, Vite, Tailwind CSS, TypeScript
- **State Management**: File-based (`pipeline-state.json`)
- **Notifications**: Telegram Bot API
- **Sandbox**: Docker (used by the Tester Agent for isolated validation)

---
## 🏗 System Architecture

### 1. The Pipeline Workflow

Ideas move through a linear sequence of stages. Each stage is mapped to a column on the Kanban board.

`INTAKE` $\rightarrow$ `REFINEMENT` $\rightarrow$ `REVIEW_SPEC` $\rightarrow$ `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH` $\rightarrow$ `TESTING` $\rightarrow$ `REVIEW_TEST` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `DONE`

### 2. The Agent Roster
|- **Orchestrator**: The "brain" of the operation. It manages the pipeline state, dispatches work to other agents, and handles triggers.
|- **Refiner Agent**: Transforms one-line ideas into detailed `spec.md` files.
|- **Architect Agent**: Designs the technical solution and creates `architecture.md`.
|- **Tester Agent**: Develops a test plan (`tests.md`) and validates implementations in a Docker sandbox.
|- **Memory Agent**: A separate loop that analyzes audit logs and reviews to evolve the system's `patterns.md`.
|- **Audit Agent**: A passive observer that logs every agent action to daily audit files.

### 3. Core Components
|- **`automation-ideas/ideas.md`**: Primary input for new ideas.
|- **`automation-ideas/pipeline-state.json`**: Single source of truth for all task stages.
|- **`automation-ideas/brain/patterns.md`**: The system's learned architectural patterns.
|- **`registry/automation_registry.json`**: Database for recurring/event-driven tasks.
|- **`automation-ideas/requirements/{ID}/`**: Contains all artifacts (`spec.md`, `architecture.md`, `tests.md`) for a specific task.

---

## 🗺️ Project Roadmap

### Phase 1: Foundation & Core Loop
- [x] Directory structure and schema established.
- [x] Orchestrator and Refiner Agent functional.
- [x] Heartbeat scheduler implemented.

### Phase 2: Artifact Generation & Monitoring
- [x] Architect and Tester Agents functional.
- [x] Telegram notifications and slash commands enabled.
- [x] Audit Agent active.

### Phase 3: Memory & Evolution
- [x] Memory Agent and Brain loop operational.
- [x] Patterns learned and versioned.

### Phase 4: Kanban UI (Operational Surface)
- [x] Kanban board with drag-and-drop.
- [x] Inline review and real-time polling.
- [x] File watcher/event-driven triggers.

### Phase 5: Continuous Learning
- [ ] Pattern Promotion (Continuous Learning) - Implement mechanism to promote successful technical artifacts to the global pattern library.

---

## ⚙️ Setup & Configuration

1. **Environment Setup**:
   - Ensure Python 3.9+ and Node.js 18+ are installed.
   - Create a `.env` file in the project root with `TELEGRAM_BOT_TOKEN` and other necessary secrets.

2. **Backend**:
   - `pip install -r requirements.txt`
   - `python api/main.py`

3. **Frontend**:
   - `cd ui && npm install`
   - `npm run dev`

4. **Docker**:
   - Ensure Docker is running for the Tester Agent sandbox.

---

## 🛠 Development Workflow

- **Adding a New Idea**: Append a new entry to `automation-ideas/ideas.md` following the established format.
- **Developing Agents**: Implement new agent logic in `agents/` and register them with the `Orchestrator`.
- **Updating UI**: All frontend changes should be made within the `ui/` directory.
- **Verification**: Before marking a phase as complete, ensure all criteria in `VERIFICATION_CRITERIA.md` are met.

---

*Hermes: Automating the mundane, empowering the human.*
