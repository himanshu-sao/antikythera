# AI Phase 2 — Engine, Triggers, Automation, and Integrations

## Goal

Define how workflow templates are executed by an engine that responds to triggers, invokes actions, waits for external systems, and records outcomes safely.

## Scope

This phase covers:
- trigger handling
- polling and webhooks
- action execution model
- external integration contracts
- idempotency and retry strategy
- secrets and connection expectations

## Supported trigger classes

Future trigger support should account for:
- webhook triggers
- polling triggers
- manual triggers
- scheduled triggers

## Integration targets

Initial design should anticipate:
- GitHub
- Jira
- CI/build systems
- internal HTTP APIs

## Execution rules

The engine must:
- evaluate triggers safely
- create workflow runs idempotently
- execute steps deterministically
- record every significant event
- support wait and resume behavior
- support retry with clear policy boundaries

## Failure handling

The system must distinguish:
- transient failure
- permanent failure
- external timeout
- invalid workflow definition
- approval timeout
- integration authentication error

## Implementation instructions

1. Define trigger ingestion pathways.
2. Define run creation semantics.
3. Define action adapter contracts.
4. Define wait/resume semantics.
5. Define retry and backoff rules.
6. Define integration credential boundaries.

## Testing instructions

Coverage should include:
- duplicate webhook delivery
- flaky external API behavior
- resumed wait steps
- failed credentials
- action retries exceeding policy
- safe handling of malformed external payloads

## Acceptance criteria

This phase is complete when:
- engine behavior is documented sufficiently for backend implementation
- trigger and integration boundaries are explicit
- failure handling and idempotency are specified clearly
