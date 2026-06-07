# Antikythera UI Architecture Mind Map

## 🏗️ Core Orchestrators
- `App.tsx`: Main entry point, manages global state and high-level routing/layout.

## 🧠 State & Logic (The Engine)
- `hooks/`
  - `usePipelineState.ts`: Centralized management of the multi-stage pipeline state.
- `utils/`
  - `boardAdapter.ts`: Transformation logic between backend data and UI board models.
- `types.ts`: Global TypeScript interfaces and type definitions.

## 📋 Board & Workflow (The Kanban)
- `components/`
  - `VirtualBoard.tsx`: Orchestrates the Kanban board view.
  - `SkeletonBoard.tsx`: Visual placeholder/empty state for the board.
  - `KanbanColumn.tsx`: Renders a single stage/column of the board.
    - *Sub-component*: `KanbanCard` (Logic for individual cards, priority, and confidence badges).
  - `WorkflowManager.tsx`: Manages workflow definitions and transitions.
  - `WorkflowBuilder.tsx`: UI for configuring/editing workflows.
  - `WorkflowDiagram.tsx`: Visual representation of the workflow.

## 🔍 Artifact & Detail Views (The Inspection)
- `components/ArtifactViewer.tsx` (MONOLITHIC - Target for Refactor)
  - **Internal Logic Modules**:
    - `fetchItemDetails`: Fetching item metadata.
    - `fetchArtifacts`: Fetching list of markdown files.
    - `saveContent` / `debouncedSave`: Persistence logic.
    - `getRelevantArtifacts`: Stage-to-file mapping logic.
  - **UI Sections**:
    - `Item Details Sidebar`: Priority, Confidence, Source, Blocking Error.
    - `Artifact Tabs`: Technical vs. Review selection.
    - `Artifact List`: Sidebar of clickable markdown files.
    - `Artifact Content Area`:
      - `ReviewForm`: Specialized UI for the 'review.md' artifact.
      - `Mermaid`: Rendering of mermaid diagrams.
      - `Timeline`: Visual history of the item.
      - `Markdown Viewer`: Renders content via `react-markdown`.
      - `Editor`: Textarea for manual edits.
- `components/artifacts/`
  - `Mermaid.tsx`: Mermaid chart rendering.
  - `Timeline.tsx`: Event history visualization.
  - `ReviewForm.tsx`: Structured form for review approvals/comments.

## ⚙️ System & Settings
- `components/BrainSettings.tsx`: Configuration for the AI engine.
- `components/IntegrationsManager.tsx`: Management of external tool connections.
- `components/modals/`
  - `CardEditor.tsx`: Modal for editing task/card details.

## 🛡️ Infrastructure
- `components/ErrorBoundary.tsx`: Error boundary wrapper.
- `main.tsx`: React DOM mounting.
- `index.css`: Global Tailwind styles.
