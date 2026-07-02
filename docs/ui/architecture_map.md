# Antikythera UI Architecture Mind Map

## 🏗️ Core Orchestrators
- `App.tsx`: Main entry point, manages global state, tab-based navigation, and layout.
- `components/layout/`: App shell layout (sidebar, top nav, theme toggle).

## 🧠 State & Logic (The Engine)
- `hooks/`
  - `usePipelineState.ts`: Centralized management of the multi-stage pipeline state.
- `utils/`
  - `boardAdapter.ts`: Transformation logic between backend data and UI board models.
  - `constants.ts`: Centralized UI constants and configuration.
- `types.ts`: Global TypeScript interfaces and type definitions.

## 📋 Board & Workflow (The Kanban)
- `components/`
  - `VirtualBoard.tsx`: Orchestrates the Kanban board view.
  - `SkeletonBoard.tsx`: Visual placeholder/empty state for the board.
  - `KanbanColumn.tsx`: Renders a single stage/column of the board.
    - *Sub-component*: `KanbanCard` (Logic for individual cards, priority, and confidence badges).
  - `components/kanban/`: Kanban-specific sub-components.
  - `PipelineDashboard.tsx`: Pipeline metrics, run status, and execution monitoring.
  - `PipelineFlowchart.tsx`: Visual flowchart of pipeline stages.
  - `WorkflowManager.tsx`: Manages workflow definitions and transitions.
  - `WorkflowBuilder.tsx`: UI for configuring/editing workflows.
  - `WorkflowArchitect.tsx`: Natural-language blueprint builder.
  - `WorkflowDiagram.tsx`: Visual representation of the workflow.
  - `AutomationStudio.tsx`: Step-by-step workflow construction with triggers.

## 🔍 Artifact & Detail Views (The Inspection)
- `components/ArtifactViewer.tsx` (Refactored — modular sub-components)
  - `components/artifacts/`
    - `Mermaid.tsx`: Mermaid chart rendering.
    - `Timeline.tsx`: Event history visualization.
    - `ReviewForm.tsx`: Structured form for review approvals/comments.
  - `components/artifact/`: Additional artifact display components.
  - `components/editor/`: Code/markdown editing components.
- `RunDetail.tsx`: Detailed view of a single workflow run.
- `CardEditor.tsx`: Modal for editing task/card details (in `modals/`).
- `CommentSection.tsx`: Discussion thread for items.

## ⚙️ System & Settings
- `components/AIEngineOverview.tsx`: Overview dashboard for AI provider/model management.
- `components/AIEngineSettings.tsx`: Configuration panel for AI models, providers, and API keys.
- `components/BrainSettings.tsx`: Configuration for the learning/brain system.
- `components/IntegrationsManager.tsx`: Management of external tool connections (Jira, GitHub, etc.).
- `components/TransactionPanel.tsx`: Atomic transaction proposal/approval UI.
- `components/ExecutionAuditLog.tsx`: Execution history and audit trail viewer.
- `components/ExecutionHistory.tsx`: Run history display.

## 🧱 UI Foundation
- `components/base/`: Reusable base/primitive components.
- `components/ui/`: Shared UI components (buttons, inputs, etc.).
- `components/modals/`: Modal dialogs.
- `components/modals/TextHighlighter.tsx`: Text highlighting component.

## 🛡️ Infrastructure
- `components/ErrorBoundary.tsx`: Error boundary wrapper.
- `main.tsx`: React DOM mounting.
- `index.css`: Global Tailwind styles.
