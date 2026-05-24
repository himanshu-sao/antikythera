# AI Phase 2 — Foundation and System Model

Branch name: `kanban-phase-2`
Base branch: `kanban-fix`
Purpose: Define the target product model that evolves Hermes from a generic staged pipeline into a generic pipeline plus reusable workflow automation system.

## Goal

Preserve the existing generic pipeline as the shared execution board while introducing the system model required for reusable workflow templates, runtime workflow runs, step execution, and external integrations.

## Product rule

The board remains generic.
- No workflow-specific columns.
- No GitHub-only or Jira-only stage model.
- Workflow-specific logic belongs to reusable definitions and runtime state, not to the base board structure.

## Desired end state

The Hermes product should support three layers:
1. Generic pipeline board.
2. Workflow template authoring.
3. Workflow run execution and inspection.

The user must be able to define detailed workflows such as:
- PR merge to release process.
- Jira triage from JQL polling.
- Future custom operational automation.

## System concepts

### Workflow template
A reusable definition that describes:
- trigger source
- required inputs
- ordered or branching steps
- human approval gates
- success and failure paths
- mapping to visible board behavior

### Workflow run
A single live execution of a workflow template.
It stores:
- current status
- active step
- history of completed steps
- errors, retries, and approvals
- linked board items

### Workflow step
A single unit of execution inside a workflow.
Supported future categories:
- trigger
- fetch
- evaluate
- action
- wait
- approval
- branch
- finalize

### Event log
The append-only system record for each run.
Used for:
- auditability
- timeline rendering
- debugging
- retry decisions

## Required data model

At minimum, the target system should introduce:
- workflow_templates
- workflow_template_versions
- workflow_steps
- workflow_runs
- workflow_run_steps
- workflow_events
- workflow_bindings
- integration_connections
- approval_records

## UI reference alignment

All Phase 2 work should remain visually aligned with the UI direction established in:
- `docs/mockups/hermes-workflow-mockup.html`
- the mockup screenshot references

## Implementation requirements

1. Define a canonical schema for templates and runs.
2. Define how workflow runs create or bind to board cards.
3. Define how waiting states and approvals appear on the board.
4. Define event logging structure before engine behavior is implemented.
5. Define versioning rules for templates.

## Non-goals

This file does not require:
- full engine implementation
- finished integrations
- final production UI code

## Testing instructions

Validation for this phase should confirm:
- all new concepts are clearly defined
- no part of the design breaks the generic board model
- future phases can implement against the agreed concepts without ambiguity

## Acceptance criteria

This phase is complete when:
- the core system model is documented
- all future phases have a stable vocabulary
- the board/workflow/run separation is explicit and non-contradictory
