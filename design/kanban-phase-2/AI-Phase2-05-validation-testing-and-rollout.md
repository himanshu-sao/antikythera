# AI Phase 2 — Validation, Testing, and Rollout

## Goal

Define the validation strategy, test layers, and rollout plan for introducing workflow templates and workflow runs into Hermes without destabilizing the generic board.

## Scope

This phase covers:
- test strategy
- acceptance criteria
- migration and rollout sequencing
- operator readiness
- documentation completeness checks

## Testing layers

The full system should eventually support:
- schema validation tests
- workflow template validation tests
- run lifecycle tests
- engine unit tests
- integration adapter tests
- UI state rendering tests
- end-to-end operator scenario tests

## Example scenarios

Mandatory reference scenarios:
- GitHub PR merged, build triggered, tests fail, human review required
- Jira issue appears via JQL, triage run created, issue assigned and commented successfully
- webhook duplicated, run deduplicated safely
- approval required but not granted, workflow pauses correctly

## Rollout strategy

Recommended sequence:
1. finalize docs and shared vocabulary
2. ship non-functional UI shells
3. add template persistence
4. add run model and timeline
5. add one integration end-to-end
6. expand to additional integrations

## Documentation requirements

Before implementation begins, validate that:
- `AI.md` aligns with the mockup direction
- every Phase 2 markdown file uses consistent terminology
- each phase has explicit scope and acceptance criteria
- no phase silently redefines the product model

## Implementation instructions

1. Create a test matrix for each phase.
2. Define demo scenarios for manual verification.
3. Define release gates for introducing workflow features incrementally.
4. Define fallback behavior if integrations are unavailable.

## Acceptance criteria

This phase is complete when:
- rollout can happen incrementally
- testing expectations are explicit
- contributors know how to validate each layer of the system before merging
