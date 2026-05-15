# Hermes System - Project Summary

## Purpose

This document is the canonical phase map for the Hermes Multi-Agent Automation System.

It serves four roles:

1. Summarize the current implementation state at the project level.
2. Define the official phased build plan.
3. Capture key implementation decisions that affect execution.
4. Maintain review-created remediation tasks that feed the Superpowers implementation and review loop.

This file should stay concise and execution-oriented. Long-form architectural intent, product behavior, and system design details belong in `memory.md`. Current implementation status belongs in `PROGRESS.md`. Completion rules belong in `VERIFICATION_CRITERIA.md`.

---

## Current Status

The Hermes system design is fully specified, and Phases 0–4 are currently marked as completed in `PROGRESS.md`, with Phase 5 in progress and Phases 6–7 pending. These statuses are operationally useful, but they are still subject to verification by the Superpowers review workflow and the rules in `REVIEW.md` and `VERIFICATION_CRITERIA.md`.

### Current Phase Status Snapshot

| Phase | Title | Current Status |
|---|---|---|
| **Phase 0** | Directory structure + `pipeline-state.json` schema + `ideas.md` format | Completed (subject to audit/review) |
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler | Completed (subject to audit/review) |
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent | Completed (subject to audit/review) |
| **Phase 3** | Telegram notifications + slash commands | Completed (subject to audit/review) |
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow | Completed (subject to audit/review) |
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) | In Progress |
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) | Pending |
| **Phase 7** | File watcher / event-driven triggers | Pending |

### Current Execution Strategy

The project now follows this operating model:

1. Review historical phases (0–5) using `SUPERPOWER-REVIEW.prompt.md`, one phase at a time or in small batches.
2. Record any gaps, contradictions, missing verification, or implementation defects as remediation tasks in this file.
3. Implement remediation tasks or pending phases using `SUPERPOWER-IMPLEMENT.prompt.md`.
4. Re-run review after implementation.
5. Only treat work as fully verified when it satisfies `VERIFICATION_CRITERIA.md`.

---

## System Potential

The Hermes system is designed to provide a high-leverage, human-in-the-loop automation platform with the following strengths:

1. **Idea Refinement**: Convert simple idea descriptions into structured specs, architecture, and tests.
2. **Quality Gates**: Use staged review, confidence scoring, and verification to prevent unsafe or low-quality automation from proceeding unchecked.
3. **Continuous Learning**: Learn operator preferences and patterns over time through the brain/memory loop.
4. **Flexible Operation**: Support scheduled automation, review checkpoints, manual triggers, and eventually event-driven execution.
5. **Operational Visibility**: Surface pipeline state through Kanban, Telegram notifications, audit logs, and structured artifacts.

---

## Key Decisions

The following implementation decisions are currently considered resolved and should be treated as part of the working baseline unless changed deliberately.

### Technology Stack
- **Agent Logic**: Python
- **UI**: Node/React

### Docker Sandboxing
- **Tester Agent** uses Docker Compose for sandbox provisioning.

### Telegram Integration
- Use the existing Hermes Telegram integration.
- Telegram is used for notifications and slash commands, not for inline review comments.

### ID Management
- Idea IDs are auto-incremented by the Orchestrator based on existing ideas.
- The Orchestrator automatically creates new `ID-XXX/` directories as needed.

### Heartbeat Schedule
- Current baseline: daily at 10 PM.
- May increase later to up to 4 runs per day if needed.

### UI Hosting
- Local hosting only.

### Repository Strategy
- Single repo / single codebase for agents, orchestrator, UI, and brain tools.

---

## Source of Truth Hierarchy

When planning, implementing, or reviewing work, use the following precedence:

1. `memory.md` — product vision, architecture, constraints, behavior, and design intent
2. `PROJECT_SUMMARY.md` — phase map, implementation decisions, remediation tasks
3. `PROGRESS.md` — claimed implementation state and current focus
4. `VERIFICATION_CRITERIA.md` — Definition of Done and verification gate
5. `REVIEW.md` — review behavior, severity, and reporting rules

If these files conflict, resolve the conflict explicitly rather than silently assuming one is correct.

---

## Phased Build Plan

This is the official build plan for Hermes.

| Phase | What to Build |
|---|---|
| **Phase 0** | Directory structure + `pipeline-state.json` schema + `ideas.md` format |
| **Phase 1** | Orchestrator + Refiner Agent + heartbeat scheduler |
| **Phase 2** | Architect Agent + Tester Agent + Audit Agent |
| **Phase 3** | Telegram notifications + slash commands |
| **Phase 4** | Memory Agent + brain loop + pending-updates review flow |
| **Phase 5** | Kanban UI (Phase 1: read + drag/drop) |
| **Phase 6** | Kanban UI (Phase 2: inline review, real-time updates) |
| **Phase 7** | File watcher / event-driven triggers |

---

## Phase Details

### Phase 0 — Foundation Files and Structure
Scope:
- Create the repository/directory structure for automation ideas and pipeline state.
- Define the `pipeline-state.json` schema.
- Define the `ideas.md` format and intake model.

Expected outcome:
- A stable file/folder foundation for all subsequent pipeline work.

### Phase 1 — Orchestrator and Refiner
Scope:
- Implement the Orchestrator.
- Implement the Refiner Agent.
- Implement the heartbeat scheduler.

Expected outcome:
- Ideas can be detected, queued, refined, and advanced automatically when not blocked on review.

### Phase 2 — Core Agent Expansion
Scope:
- Implement the Architect Agent.
- Implement the Tester Agent.
- Implement the Audit Agent.

Expected outcome:
- The system can generate architecture and testing artifacts and maintain a structured audit trail.

### Phase 3 — Telegram Integration
Scope:
- Implement Telegram notifications.
- Implement slash commands for pipeline interaction.

Expected outcome:
- The owner can monitor the system and trigger actions through Telegram without using it for inline document review.

### Phase 4 — Memory and Brain Loop
Scope:
- Implement the Memory Agent.
- Implement the nightly brain loop.
- Implement the pending-updates review flow.

Expected outcome:
- The system can observe recurring patterns, propose updates, and evolve with owner approval.

### Phase 5 — Kanban UI (Phase 1)
Scope:
- Build a Kanban board with columns matching pipeline stages.
- Show cards with key metadata (ID, title, priority, confidence score, stage, timestamps).
- Support drag/drop stage movement.
- Provide a detail view for artifacts and review files.

Expected outcome:
- The owner can inspect and manage pipeline state through a local UI.

### Phase 6 — Kanban UI (Phase 2)
Scope:
- Add inline review editing.
- Add real-time updates for agent progress.
- Add richer UI navigation and linked workflow affordances.

Expected outcome:
- The UI becomes the primary operational surface for human review and monitoring.

### Phase 7 — Event-Driven Triggers
Scope:
- Add file watcher or event-driven execution triggers.
- React to Kanban actions or file changes without waiting for the next heartbeat.

Expected outcome:
- The system gains faster responsiveness while preserving safety and review controls.

---

## Superpowers Workflow Contract

This project uses Superpowers in two complementary modes:

### Review Mode
Driven by `SUPERPOWER-REVIEW.prompt.md`.

Responsibilities:
- Review one phase or remediation task group at a time.
- Compare implementation against `memory.md`, this file, `PROGRESS.md`, `REVIEW.md`, and `VERIFICATION_CRITERIA.md`.
- Identify gaps, contradictions, missing verification, and inaccurate progress claims.
- Create or refine remediation tasks in the section below.
- Recommend updates to `PROGRESS.md`.

### Implementation Mode
Driven by `SUPERPOWER-IMPLEMENT.prompt.md`.

Responsibilities:
- Select one pending phase or remediation task group.
- Break it into small, verifiable tasks.
- Implement the work with tests and validation steps.
- Update `PROGRESS.md` and, if needed, refine remediation task details in this file.
- Leave final “Verified” decisions to review mode.

---

## Review-Created Remediation Tasks

This section is the canonical place to record gaps discovered during audit or review.

Rules:
- Superpowers review is allowed to create remediation tasks here.
- Superpowers implementation is allowed to refine task wording, split tasks into smaller items, or update task status notes here.
- Remediation tasks should be small, specific, and verifiable.
- Use IDs like `R<phase>.<index>` such as `R0.1`, `R2.3`, `R5.2`.
- A remediation task should include:
  - status
  - issue summary
  - why it exists
  - expected fix
  - verification expectation

### Status Vocabulary
Use one of the following values:
- `Pending`
- `In Progress`
- `Implemented, pending review`
- `Verified`
- `Deferred`
- `Blocked`

### Phase 0 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 1 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 2 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 3 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 4 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 5 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 6 Remediation Tasks
- No remediation tasks recorded yet.

### Phase 7 Remediation Tasks
- No remediation tasks recorded yet.

---

## Remediation Task Template

Use this format when adding a new remediation item:

### R<phase>.<index> — Short Task Title
- **Status**: Pending
- **Issue**: Clear description of the observed gap, contradiction, missing behavior, or verification failure.
- **Source**: Review finding, spec mismatch, verification failure, regression, or documentation gap.
- **Expected Fix**: What must change in code, tests, or documentation.
- **Verification**: Exact tests, checks, or manual validation needed before this can be marked verified.

Example:

### R5.1 — Kanban drag/drop does not persist stage changes
- **Status**: Pending
- **Issue**: Cards can be moved visually, but the new stage is not persisted to pipeline state.
- **Source**: Phase 5 audit review.
- **Expected Fix**: Update the UI and backend integration so drag/drop writes the correct stage to `pipeline-state.json` or the backing API.
- **Verification**: Automated test for stage update behavior plus manual UI check confirming that a moved card remains in the new column after refresh.

---

## Planned Next Steps

Unless review changes priorities, the expected sequence is:

1. Audit Phases 0–5 using `SUPERPOWER-REVIEW.prompt.md`.
2. Record remediation tasks in this file for any gaps found.
3. Fix remediation tasks and complete remaining Phase 5 work using `SUPERPOWER-IMPLEMENT.prompt.md`.
4. Re-review all fixes until Phases 0–5 are verified.
5. Proceed to Phase 6 and Phase 7 using the same implementation-review loop.

---

## Maintenance Rules

Keep this file concise and structured.

Update this file when:
- a phase definition changes,
- a key implementation decision changes,
- review creates new remediation tasks,
- remediation tasks are split, refined, deferred, or verified,
- the planned next steps materially change.

Do not use this file for:
- long architectural deep-dives,
- detailed progress logs,
- exhaustive review reports,
- transient debugging notes.

Those belong in `memory.md`, `PROGRESS.md`, or review output artifacts.

---

*This document is the canonical project execution map for Hermes. It should remain stable, operational, and easy for Superpowers to parse and update.*