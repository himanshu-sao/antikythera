# AI Phase 2 — Runtime Runs, Board Mapping, and Timeline

## Goal

Define how workflow runs appear in the system, how they map to the generic pipeline board, and how users inspect execution timelines.

## Scope

This phase covers:
- workflow run lifecycle
- board card generation or binding
- run detail page or panel
- timeline and event rendering
- operator controls such as retry, approve, skip, and cancel

## Board mapping rules

Workflow runs must not create custom workflow columns.
Instead, they should:
- create cards in existing board stages
- update card metadata to reflect workflow state
- use badges for waiting, approval, blocked, retry, and completed status
- support links from a board card to the run detail view

## Run detail requirements

The run detail surface should include:
- run summary
- current step
- template name and version
- linked cards
- event timeline
- last successful action
- latest error if any
- available operator actions

## Execution states

Suggested high-level run states:
- pending
- active
- waiting
- needs_approval
- blocked
- failed
- completed
- canceled

## Implementation instructions

1. Define the run lifecycle model.
2. Define how a run updates pipeline cards.
3. Define timeline event types.
4. Define audit-safe operator actions.
5. Define how retries are surfaced to the user.

## Testing instructions

Validate:
- runs can be represented on the board without breaking generic semantics
- waiting and approval states are visible and understandable
- timeline events are sufficient for debugging and audit
- operator actions are constrained and explicit

## Acceptance criteria

This phase is complete when:
- runtime behavior is understandable from the docs alone
- the board-to-run relationship is clearly specified
- a future implementation can build run detail UI and event handling without ambiguity
