# AI Phase 2 — Workflow Builder and Template Authoring

## Goal

Define the UX, data rules, and implementation plan for creating reusable workflow templates in Hermes.

## Scope

This phase covers:
- template list view
- template detail view
- workflow builder interaction model
- template versioning expectations
- validation rules for authoring

## UX requirements

The workflow authoring experience should resemble the mockup direction:
- dedicated Workflows surface
- list of templates with summaries
- visible trigger definition
- ordered steps with clear type labels
- ability to represent approvals, waits, decisions, and actions

## Authoring model

A workflow template must include:
- name
- description
- trigger type
- trigger conditions
- step list
- step parameters
- optional approval gates
- success and failure handling
- owner metadata
- activation state

## Step design rules

Each step definition must include:
- stable step id
- human-readable name
- step type
- input contract
- output contract
- next-step behavior
- retry policy
- timeout policy where relevant

## Implementation instructions

1. Create the conceptual information architecture for the Workflows tab.
2. Define how a user creates a template from scratch.
3. Define how a template is duplicated and versioned.
4. Define how invalid templates are prevented from activation.
5. Define a minimal schema for serializing templates.

## Testing instructions

Test coverage for this phase should include:
- invalid trigger configuration
- missing required step fields
- invalid step ordering
- activation blocked for incomplete templates
- duplication preserves logic but creates new identity

## Acceptance criteria

This phase is complete when:
- a contributor can implement the Workflows authoring UI without guessing
- template validation rules are explicit
- step semantics are documented clearly enough for engine work in later phases
