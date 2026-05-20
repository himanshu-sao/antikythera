# 🚀 Hermes Product Specification

## 1. Vision & Purpose
Hermes is a perpetual, human-in-the-loop, asynchronous multi-agent automation pipeline. It converts simple idea descriptions into structured specifications, architecture, and verified tests, allowing a human operator to review and approve progress via a Kanban UI.

## 2. System Architecture

### 2.1 Pipeline Workflow
Ideas move through a linear sequence of stages:
`INTAKE` $\rightarrow$ `REFINEMENT` $\rightarrow$ `REVIEW_SPEC` $\rightarrow$ `ARCHITECTURE` $\rightarrow$ `REVIEW_ARCH` $\rightarrow$ `TESTING` $\rightarrow$ `REVIEW_TEST` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTING` $\rightarrow$ `DONE`

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
| Add Card | Enter ID/Title $\rightarrow$ Create | Card appears instantly in INTAKE, persists on refresh. |
| Edit Card | Open Modal $\rightarrow$ Change Title $\rightarrow$ Save | Title updates immediately, persists on refresh. |
| Comment | Enter Text $\rightarrow$ Post | Comment appears in card detail, persists on refresh. |
| Move Card | Drag card from A $\rightarrow$ B | Card moves to new column, state updates on backend. |
| Reorder | Drag card above another in same col | Card order changes, persists on refresh. |
