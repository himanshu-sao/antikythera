# Antikythera UI Briefing

**Purpose**: Technical context for the React frontend.

---

## Tech Stack
- **React 19** + **TypeScript** + **Vite** + **Tailwind CSS**
- **Testing**: Vitest + Testing Library (unit), Playwright (E2E)
- **State**: Server-driven via API polling; local optimistic updates

## UI Surfaces (Tab Navigation)
The app uses a tabbed navigation with four primary surfaces:

| Tab | Component | Purpose |
|---|---|---|
| **Pipeline** | `VirtualBoard.tsx` | Universal Kanban triage board for all items |
| **Workflows** | `WorkflowManager.tsx` + `AutomationStudio.tsx` | Workflow template management and step builder |
| **Runs** | `PipelineDashboard.tsx` + `RunDetail.tsx` | Execution monitoring and audit trail |
| **Integrations** | `IntegrationsManager.tsx` | External system connections (Jira, GitHub, etc.) |

Additional panels available via sidebar:
- **AI Engine** (`AIEngineSettings.tsx` + `AIEngineOverview.tsx`): Multi-provider model management
- **Workflow Architect** (`WorkflowArchitect.tsx`): Natural-language blueprint generator
- **Brain Settings** (`BrainSettings.tsx`): Learning/pattern configuration

## Key Design Decisions
1. **Generic Board Model**: The Kanban board is stage-agnostic. Stages come from the backend's `pipeline-state.json`; the UI does not hardcode column names.
2. **Optimistic UI**: Drag-and-drop and inline edits apply immediately in the UI, with rollback on API error.
3. **Status Indicators**: `WAITING`, `BLOCKED`, and `COMPLETED` states have distinct visual indicators (colors, badges, icons).
4. **Artifact Rendering**: Markdown via `react-markdown`, Mermaid diagrams via `mermaid` library, with a review form for `review.md`.
5. **Error Boundary**: Global `ErrorBoundary` wraps the app with a user-friendly fallback.
6. **App Shell**: Left sidebar with navigation icons, top bar with tabs and theme toggle.

## Component Organization
See `docs/ui/architecture_map.md` for a full component tree.

## Development
```bash
cd ui && npm install       # Install dependencies
cd ui && npm run dev       # Start dev server (port 5173, proxies /api → :8006)
cd ui && npx vitest run    # Run unit tests
cd ui && npx vitest --watch  # Run tests in watch mode
```
