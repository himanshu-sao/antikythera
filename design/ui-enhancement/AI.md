# Antikythera — UI Enhancement Branch Guidance

Branch name: `ui-enhancement`
Base branch: `kanban-fix`
Purpose: Improve the current generic pipeline UI without changing the underlying product model. The goal of this branch is documentation-first guidance for the next UI build phase, not immediate feature implementation.

## Core product rule

The Antikythera board must remain a generic pipeline. The existing stage-based Kanban is the canonical operational surface for all work. New UX should improve clarity, navigation, and extensibility without converting the core board into a hardcoded workflow-specific product.

## Design intent

This branch introduces a more structured multi-surface experience inspired by the attached HTML mockup.

Target top-level navigation:
- Pipeline
- Workflows
- Runs
- Integrations

This navigation is a UX framing device. In this branch, the generic pipeline remains the source of truth. Workflow-specific behavior is only visually anticipated here, not fully implemented.

## Required visual references

The following files are required design references for any future implementation work in this branch:
- `docs/mockups/antikythera-workflow-mockup.html`
- `docs/mockups/screenshots/pipeline-board-reference.png`
- `docs/mockups/screenshots/workflow-builder-reference.png`
- `docs/mockups/screenshots/run-detail-reference.png`

If screenshot assets do not yet exist, they should be created from the mockup and committed before UI implementation begins.

## UX principles

1. Preserve the generic board model.
- The board continues to represent shared lifecycle stages.
- Cards remain generic work items.
- UI may label cards as workflow-backed, but must not introduce workflow-specific columns.

2. Improve navigational clarity.
- Current UI should evolve toward clearly separated surfaces for board operations, workflow definition, and runtime inspection.
- The user should understand within one screen whether they are managing the pipeline, authoring workflow templates, or inspecting a workflow run.

3. Keep the board as the operational center.
- Pipeline remains the default landing view.
- Workflow and run views should support the board rather than replace it.

4. Follow the mockup layout style.
- Keep a cleaner header hierarchy.
- Use stronger card grouping and visual labeling.
- Provide consistent badges for workflow-backed cards, approvals, waiting states, and completion states.

5. Avoid over-committing to backend assumptions.
- This branch is UI-direction only.
- Controls may anticipate future entities such as workflow templates and runs, but should not assume finished backend support.

## Visual structure requirements

### Pipeline view

The Pipeline view should remain the generic staged board. It should be visually enhanced to support:
- clear stage headers
- better card grouping
- richer metadata badges
- better empty states
- improved filters and toolbar layout
- stronger visual distinction for waiting, blocked, and completed states

### Workflows view

The Workflows view should present future reusable templates at a conceptual level.
Expected content:
- list of workflow templates
- summary description of each template
- indication of trigger source
- high-level step count
- draft/active status

This view may initially be static or placeholder-driven.

### Runs view

The Runs view should preview the future runtime execution model.
Expected content:
- active and completed runs
- latest execution state
- linked pipeline items
- status timeline or recent events

This view may initially be static or placeholder-driven.

### Integrations view

The Integrations view should act as a future-ready shell for GitHub, Jira, CI, and related systems.
Initial implementation may be non-functional, but the information architecture should be anticipated here.

## Mockup alignment rules

Any future UI work on this branch should be compared directly against the HTML mockup and its derived screenshots.

Alignment criteria:
- top-level navigation resembles the mockup structure
- board remains generic
- workflow-backed items are visually distinguishable
- side panels or detail zones are more legible than the current layout
- visual polish improves without introducing unnecessary complexity

## Implementation guardrails

This branch must not:
- redefine the core pipeline stages
- convert the product into a workflow-specific board
- hardcode GitHub/Jira-only terminology into the main board
- require backend workflow execution to land before UI improvements

## Deliverables for this branch

Required deliverables:
- updated `AI.md` with this guidance
- HTML mockup committed under `docs/mockups/`
- screenshot references committed under `docs/mockups/screenshots/`
- optional notes in README or docs linking to these design references

## Acceptance criteria

This branch is complete when:
- the UI direction is documented clearly enough for a later implementation pass
- the mockup is committed and easy to review
- future contributors can understand how to improve the UI while preserving the generic board model
- all naming uses corrected spelling and consistent terminology
