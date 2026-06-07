# 🤖 Antikythera UI Briefing

**Purpose**: Guidance for the React frontend and the Kanban operational surface.

---

## 🛠 Tech Stack
- **Framework**: React 19, Vite, TypeScript
- **Styling**: Tailwind CSS
|- **DND**: @dnd-kit/core
- **State**: Polling-based updates from the FastAPI backend.

## 📋 The Kanban Board (Operational Surface)
The board is a visual representation of the `PIPELINE_STAGES`.

### 1. Core Interactions
- **Inter-column Move**: Changes the `stage` of an item.
- **Intra-column Reorder**: Changes the `order` field (Persistence is critical).
- **Card Editor**: Modal for editing title, description, and adding comments.

### 2. UX Constraints
- **Generic Board Model**: The board must remain a generic pipeline. Do not hardcode workflow-specific columns.
- **Optimistic UI**: Moves and edits should reflect immediately in the UI before the API confirms.

## 🎨 Design Direction (`ui-enhancement`)
Current goal: Evolve the generic board into a structured multi-surface experience.

### Target Surfaces:
- **Pipeline**: The staged Kanban board (Default).
- **Workflows**: List and authoring of reusable templates.
- **Runs**: Runtime inspection of active/completed workflow executions.
- **Integrations**: Management of connected external systems.

### Visual Requirements:
- Stronger visual distinction for `WAITING`, `BLOCKED`, and `COMPLETED` states.
- Richer metadata badges on cards (e.g., confidence score, assigned agent).
- Clean header hierarchy and improved empty-state placeholders.
