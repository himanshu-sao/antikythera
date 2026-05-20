# Hermes Kanban Remediation and AI Handoff

## Purpose

This document is a handoff package for an AI engineer that will continue work on the `himanshu-sao/hermes-himanshu` repository. The immediate objective is to fix the Kanban board experience first, before any broader platform or stack changes are considered.[cite:32][cite:17]

The current repo is public on GitHub, has `main` as the default branch, and has pull requests and projects enabled, so branch-based remediation work can proceed without repository visibility changes.[cite:32]

## Primary Goal

Stabilize and improve the Hermes Kanban board so that the following workflows work reliably in the existing product:

- Add a card.
- Edit a card.
- Comment on a card.
- Move a card across columns.
- Persist those changes consistently between frontend state and backend state.

The work should prioritize keeping the existing application direction aligned as much as possible, instead of replacing the entire product with a different project-management platform.[cite:32][cite:17][cite:31]

## Working Assumptions

The existing Hermes product appears to have a custom Kanban UI that is currently failing at basic board interactions. The user explicitly reported that cards cannot be added, edited, commented on, or moved reliably, which means the board is not meeting its minimum interaction contract.[cite:32]

Because the repository files were not directly available in the current environment, this handoff focuses on architecture choices, implementation strategy, acceptance criteria, and migration instructions rather than repo-specific line edits.[cite:32]

## Non-Goals

Do **not** begin by replacing Hermes with a full standalone project-management application unless the Kanban repair path is proven infeasible.[cite:22][cite:49]

Do **not** introduce a large stack migration as the first step if the current frontend can be repaired with a modern drag-and-drop foundation and targeted UI refactoring.[cite:17][cite:50]

## Research Findings

### Option 1: Atlassian Pragmatic Drag and Drop

Atlassian’s `pragmatic-drag-and-drop` is a low-level drag-and-drop toolchain designed to work with any view layer, including React, and it is already used in large production products including Trello, Jira, and Confluence.[cite:17]

The repository is actively maintained, with recent sync activity visible within days, and the project exposes a small core package plus optional packages so teams can use their own design system and stack rather than adopting Atlassian UI wholesale.[cite:17]

This makes it the strongest long-term foundation when the goal is to keep Hermes aligned with its existing React-based UI while replacing only the brittle interaction layer.[cite:17]

### Option 2: react-trello

`react-trello` is a pluggable React Kanban board library that supports drag-and-drop on cards and lanes, editable boards, add/delete card flows, inline lane title editing, event bus integration, and callbacks such as `onDataChange`, `onCardAdd`, `onCardClick`, `onCardDelete`, and `onCardMoveAcrossLanes`.[cite:31]

It is attractive for rapid stabilization because it provides an opinionated board component with the core board mechanics already implemented and exposes a simple `lanes[] -> cards[]` data contract.[cite:31]

However, the latest release listed is from June 2021 and the latest main branch commit shown is from about three years ago, so it is substantially less future-proof than newer low-level approaches.[cite:31]

### Option 3: Full Product Adoption - Kan

`kanbn/kan` is a full open-source Trello alternative built with Next.js, Tailwind CSS, tRPC, Drizzle ORM, and Better Auth.[cite:22]

It already includes board visibility, workspace members, Trello imports, labels and filters, comments, activity logs, and templates, which means it covers many of the capabilities the Hermes board may eventually want.[cite:22]

It is actively maintained, with recent commits within days, but it is licensed under AGPLv3 and represents a much larger architectural shift than a board-layer repair, so it should be treated as a strategic alternative rather than the first remediation move.[cite:22]

### Option 4: Full Product Adoption - Planka

Planka is another mature board product with collaborative boards, real-time updates, markdown support, and self-hosting options.[cite:49]

It is active, widely used, and feature-rich, but it is source-available under Planka’s community/commercial licensing model rather than a simple permissive OSS license, so legal and product-fit review would be required before deeper reuse.[cite:49]

Like Kan, it is better treated as a platform-replacement option than a first-line fix for Hermes.[cite:49]

## Recommendation

### Recommended Path

The recommended path is to keep Hermes on its current application direction and replace only the Kanban interaction foundation first, not the whole product.[cite:17][cite:31]

Use Atlassian Pragmatic Drag and Drop as the preferred long-term implementation foundation if the current board is custom and salvageable, because it is current, React-compatible, design-system-friendly, and proven in Trello/Jira-scale interfaces.[cite:17]

If the team needs a fast recovery spike or fallback prototype to validate interaction flows, use `react-trello` as a short-lived benchmark or temporary baseline for behavior and data mapping, but avoid making it the permanent dependency unless maintainability concerns are explicitly accepted.[cite:31]

### Why This Path Fits Hermes

The user explicitly asked to keep things aligned as much as possible, which favors a board-layer refactor over a product replacement.[cite:32]

A low-level DnD foundation preserves the current UI architecture, current backend API shape, and Hermes-specific workflow semantics while fixing the parts users actually touch: create, edit, comment, and move interactions.[cite:17]

## Decision Matrix

| Option | Type | Best Use | Pros | Risks | Recommendation |
|---|---|---|---|---|---|
| Atlassian Pragmatic Drag and Drop | Low-level drag-and-drop foundation | Long-term board refactor in existing app | Active, proven in Trello/Jira/Confluence, works with React and custom design systems.[cite:17] | Requires more implementation work than plug-and-play board libs; mixing with `react-dnd` in same area can cause conflicts unless isolated.[cite:21] | **Primary recommendation**.[cite:17] |
| react-trello | React board component | Fast prototype or temporary stabilization | Built-in board mechanics, add/delete, drag/drop, event bus, callbacks, editable board mode.[cite:31] | Old releases and slower maintenance profile.[cite:31] | Use only as fallback or prototype.[cite:31] |
| Kan | Full Trello alternative | Strategic product replacement | Comments, labels, activity log, templates, modern TypeScript stack, active development.[cite:22] | AGPLv3, major architecture shift, larger migration cost.[cite:22] | Not first move.[cite:22] |
| Planka | Full board platform | Strategic product replacement | Mature product, real-time collaboration, markdown, self-hostable, active releases.[cite:49] | Different licensing model, large migration scope.[cite:49] | Not first move.[cite:49] |

## Implementation Strategy for the Next AI

### Phase 0: Branch and Tracking

1. Create a new branch named `kanban-fix` from `main`.[cite:32]
2. Locate the project progress tracker file, such as `PROJECT_SUMMARY.md`, `PROGRESS.md`, `STATUS.md`, or equivalent, and update it before and after implementation to reflect the current Kanban remediation effort.[cite:32]
3. Add a short worklog entry capturing:
   - Problem statement.
   - Chosen technical direction.
   - In-progress tasks.
   - Validation results.

### Phase 1: Codebase Discovery

The next AI should inspect the repository and identify the following:

- Frontend app location, likely `ui/`, `frontend/`, or `app/`.
- Board rendering component.
- Card component.
- Card modal or detail drawer, if present.
- State management layer for board data.
- API calls for create/update/move/comment actions.
- Any existing drag-and-drop library already in use.
- Any progress-tracking document or status file.[cite:32]

Important: before introducing Pragmatic Drag and Drop, confirm whether the existing board uses `react-dnd`, `@hello-pangea/dnd`, `react-beautiful-dnd`, `sortablejs`, `dnd-kit`, or browser-native drag events. Pragmatic Drag and Drop should not be co-mingled with `react-dnd` in the same drag area without careful root isolation because the two systems can conflict over draggable ownership.[cite:21]

### Phase 2: Define the Board Contract

Standardize a canonical board data model in frontend code, even if an adapter is required for the backend. The board should at minimum map to:

```ts
interface BoardColumn {
  id: string;
  title: string;
  order: number;
  cards: BoardCard[];
}

interface BoardCard {
  id: string;
  title: string;
  description?: string;
  comments?: CardComment[];
  metadata?: Record<string, unknown>;
  status: string;
  order: number;
}

interface CardComment {
  id: string;
  author?: string;
  body: string;
  createdAt: string;
}
```

Keep server models and UI models decoupled with adapter functions if needed. This makes later library swaps much easier and avoids board behavior being spread across API response shapes.

### Phase 3: Repair Interaction Flows in This Order

#### 1. Read and render board state

Before fixing drag-and-drop, ensure board state renders from one single source of truth and that each card and column has stable IDs. Most drag bugs trace back to unstable keys, transient IDs, or optimistic updates that never reconcile.

#### 2. Add card

Implement or repair a clear add-card flow per column. The action should:

- Open a lightweight form or inline editor.
- Validate required fields.
- Create optimistic UI state.
- Persist to the backend.
- Reconcile with server response.
- Roll back cleanly on failure.

If a faster baseline is needed, `react-trello` already models editable boards and `onCardAdd`, which can be used as behavioral reference when building the custom implementation.[cite:31]

#### 3. Edit card

Clicking a card should open a dedicated edit surface such as a modal or side drawer. That surface should separate card title, description, metadata, and comments into predictable sections.

The board must not depend on inline contenteditable hacks for primary editing if those hacks are the source of state desynchronization.

#### 4. Comment on card

Comments should be attached to the card detail view rather than embedded directly in the board tile. The flow should:

- Load existing comments when opening card detail.
- Submit new comments via explicit action.
- Render pending/saved/error states.
- Preserve comments in the canonical card detail store.

If the backend does not yet support comments robustly, create a placeholder adapter layer and mark backend persistence as a separate follow-up item in the progress tracker.

#### 5. Move cards

Only after the core state model is stable should the AI replace or repair drag-and-drop. The move flow should:

- Support intra-column reorder.
- Support inter-column move.
- Update UI optimistically.
- Persist source column, target column, and target index.
- Roll back or re-fetch on error.

With Pragmatic Drag and Drop, implement move behavior explicitly in application state. With `react-trello`, the equivalent move hooks include `handleDragEnd`, `onDataChange`, and `onCardMoveAcrossLanes`, which can serve as a reference for the callback contract.[cite:31]

### Phase 4: Introduce Pragmatic Drag and Drop

If adopting Pragmatic Drag and Drop, do the following:

1. Remove or isolate any conflicting existing DnD provider in the Kanban region.[cite:21]
2. Register columns as drop targets and cards as draggable elements.
3. Keep drag metadata minimal: `cardId`, `sourceColumnId`, and possibly `currentIndex`.
4. Compute reorder intent in application state, not DOM order.
5. Use clear visual affordances for drop indicators and dragging states.
6. Avoid coupling drag behavior to fragile nested DOM assumptions.

Pragmatic Drag and Drop is intentionally low-level, so the AI must build the board semantics itself rather than expecting a full Kanban widget out of the box.[cite:17]

### Phase 5: Persistence and Error Handling

Every mutating action should follow one of two consistent patterns:

- Optimistic update -> persist -> reconcile -> rollback on failure.
- Persist first -> refresh canonical state -> render final state.

Do **not** mix both patterns unpredictably across add/edit/comment/move flows, or the board will feel inconsistent and buggy.

Add visible error handling for failed operations. Silent failures are especially harmful in Kanban boards because the UI appears interactive while data is actually lost.

### Phase 6: Progress File Update

Update the repo’s progress file with a dedicated section such as:

```md
## Kanban Fix

### Done
- Audited existing board implementation.
- Selected drag-and-drop remediation path.
- Stabilized card rendering IDs.
- Fixed add card flow.
- Fixed edit card modal.
- Fixed move-card persistence.

### Remaining
- Comment persistence polish.
- Keyboard accessibility for card movement.
- Empty/error state improvements.
- Regression tests.
```

This update matters because the user explicitly asked for progress tracking to show what has been done and what still needs to be done.[cite:32]

## Acceptance Criteria

The Kanban fix is complete only when all of the following are true:

### Functional Criteria

- A user can create a card in any valid column.
- A user can open a card and edit its title/description.
- A user can add a comment to a card and see it persist.
- A user can move a card between columns.
- A user can reorder a card within a column.
- Refreshing the page preserves the final server state.

### UX Criteria

- No duplicate cards appear after create or move.
- No “snap back” occurs after a successful drop.
- Errors are shown to users when persistence fails.
- Loading and empty states are explicit.
- Card click and drag affordances do not conflict.

### Engineering Criteria

- IDs are stable and unique.
- Board state uses a single canonical client model.
- Drag logic is isolated from presentation.
- Add/edit/comment/move actions have tests or at least reproducible manual validation notes.
- Progress file is updated in the repo.[cite:32]

## Suggested Technical Patterns

### Board State Adapter

Create a `boardAdapter.ts` or equivalent module with functions like:

```ts
export function apiToBoardModel(apiData: unknown): BoardColumn[] {}
export function boardMovePayload(input: {
  cardId: string;
  fromColumnId: string;
  toColumnId: string;
  toIndex: number;
}) {}
export function boardCreatePayload(input: Partial<BoardCard>) {}
export function boardUpdatePayload(input: BoardCard) {}
```

This avoids leaking server-specific formats throughout the UI.

### Modal-Based Editing

Use modal or drawer editing instead of making the tile itself carry full editing responsibility. This reduces click/drag conflicts and makes comments and metadata easier to manage.

### Test Priority

At minimum, add tests for:

- Card creation reducer or action.
- Card move reducer or action.
- Adapter correctness for column/card IDs.
- API payload generation for moves.

If the codebase has browser E2E tooling, add one happy-path board flow covering create -> edit -> move -> comment.

## Risks and Guardrails

### Risk 1: Mixing Drag Libraries

Do not partially introduce Pragmatic Drag and Drop into a region still controlled by `react-dnd` unless root ownership is isolated; Atlassian explicitly notes ownership conflicts in shared draggable regions.[cite:21]

### Risk 2: Adopting Stale UI Libraries as Permanent Core

`react-trello` is useful as a benchmark or temporary fallback, but its slower maintenance profile makes it a weaker permanent foundation for a product that will continue evolving.[cite:31]

### Risk 3: Overcorrecting Into Full Product Migration

Kan and Planka are powerful alternatives, but replacing Hermes with them would introduce licensing, architectural, authentication, and workflow migration complexity far beyond the immediate board remediation need.[cite:22][cite:49]

## Explicit Instructions for the Next AI

Follow these instructions in order:

1. Check out a new branch named `kanban-fix`.
2. Locate the frontend and progress/status files.
3. Audit the existing Kanban implementation and identify the current drag library and state model.
4. Choose the lowest-risk path:
   - If the board UI is mostly custom, migrate the interaction layer to Pragmatic Drag and Drop.[cite:17]
   - If the board is severely broken and a fast stabilizing prototype is required, use `react-trello` only as a temporary reference or scaffold.[cite:31]
5. Repair in this order: render stability -> add card -> edit card -> comments -> move/reorder -> persistence.
6. Update the progress file with “done” and “remaining” items.
7. Validate manually and, where possible, with tests.
8. Keep the rest of Hermes unchanged unless required for the Kanban fix.

## Final Recommendation

The highest-confidence path is: **do not replace Hermes, do not start with Kan or Planka, and do not make `react-trello` the permanent core.** Instead, refactor the current board around a stable client-side board model and adopt Atlassian Pragmatic Drag and Drop as the long-term board interaction foundation.[cite:17][cite:31][cite:22][cite:49]

That approach is the best fit for the user’s requirement to fix the Kanban board first while keeping the current product aligned as much as possible.[cite:32]
