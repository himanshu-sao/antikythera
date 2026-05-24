# Project Memory: Antikythera Multi-Agent Automation System
> Last Updated: 2026-05-14  
> Purpose: Shared reference document for system design decisions, architecture, and open items.

---

## 1. Vision

A **perpetual, human-in-the-loop, async multi-agent automation pipeline** powered by Antikythera (local), where:

- Ideas are captured as one-liners in a single markdown file
- Agents autonomously refine, validate, and test each idea
- The human reviews artifacts at their own pace via a Kanban UI
- Telegram is used for notifications and slash-command triggers (not inline feedback)
- All agents share a common "brain" that learns the owner's patterns over time
- The system runs twice daily (heartbeat) and never blocks on human availability

---

## 2. Entry Point

**File:** `automation-ideas/ideas.md`

Format:
```markdown
## TODO
- [ID-001] Shell script to auto assign and move vulnerability tickets | Priority: High
- [ID-002] Automatically restart pods daily | Priority: Medium

## In Progress
## Done
```

- The owner adds ideas here at any time
- IDs are manually assigned (e.g. `ID-001`, `ID-002`)
- Priority is inline: `High | Medium | Low`
- Moving between sections (TODO → In Progress → Done) is done via the Kanban UI or by the Orchestrator

---

## 3. Directory Structure

```
/
├── memory.md                            ← This file (system design reference)
├── PROJECT_STATUS.md
├── README.md
├── HERMES_PRODUCT_SPEC.md
│
├── automation-ideas/
│   ├── ideas.md                            ← Owner's intake file
│   ├── pipeline-state.json                 ← Single source of truth for all pipeline state
│   │
│   ├── requirements/
│   │   ├── ID-001/
│   │   │   ├── spec.md                     ← Refiner Agent output
│   │   │   ├── architecture.md             ← Architect Agent output
│   │   │   ├── tests.md                    ← Tester Agent output
│   │   │   └── review.md                   ← Owner's review comments (per stage)
│   │   └── ID-002/
│   │       └── ...
│   │
│   ├── audit/
│   │   └── YYYY-MM-DD.md                   ← Daily audit log (every agent action)
│   │
│   └── brain/
│       ├── patterns.md                     ← Learned owner patterns (secrets, PII, stack preferences)
│       ├── pending-updates.md              ← Brain update proposals awaiting owner review
│       └── history/
│           └── YYYY-MM-DD-update.md        ← Versioned history of brain updates
```

---

## 4. Pipeline Stages

Each idea moves through the following stages. These map 1:1 to Kanban columns.

```
INTAKE → REFINEMENT → REVIEW_SPEC → ARCHITECTURE → REVIEW_ARCH → TESTING → REVIEW_TEST → APPROVED → EXECUTING → DONE
```

| Stage | Owner Action Required | Agent Responsible |
|---|---|---|
| INTAKE | Add to ideas.md | — |
| REFINEMENT | — | Refiner Agent |
| REVIEW_SPEC | Review spec.md, write in review.md | — |
| ARCHITECTURE | — | Architect Agent |
| REVIEW_ARCH | Review architecture.md, write in review.md | — |
| TESTING | — | Tester Agent |
| REVIEW_TEST | Review tests.md, write in review.md | — |
| APPROVED | — | Orchestrator queues for execution |
| EXECUTING | — | Execution in sandbox |
| DONE | — | Orchestrator marks complete |

---

## 5. pipeline-state.json Schema

```json
{
  "last_heartbeat": "2026-05-14T02:00:00Z",
  "items": {
    "ID-001": {
      "title": "Shell script to auto assign and move vulnerability tickets",
      "priority": "High",
      "stage": "REVIEW_SPEC",
      "created_at": "2026-05-14T00:00:00Z",
      "updated_at": "2026-05-14T06:00:00Z",
      "assigned_agent": null,
      "confidence_score": 82,
      "blocked_reason": null,
      "review_status": "PENDING",
      "history": [
        { "stage": "INTAKE", "at": "2026-05-14T00:00:00Z" },
        { "stage": "REFINEMENT", "at": "2026-05-14T02:00:00Z", "agent": "refiner" },
        { "stage": "REVIEW_SPEC", "at": "2026-05-14T02:15:00Z" }
      ]
    }
  }
}
```

`review_status` values: `PENDING` | `APPROVED` | `NEEDS_REVISION`

---

## 6. review.md Format (Per Idea)

The owner writes into this file at each review gate. The Orchestrator reads `review_status` to decide next action.

```markdown
## Review Log

### 2026-05-14 — Stage: REVIEW_SPEC
**review_status:** NEEDS_REVISION
**Comments:**
- Spec does not account for multi-cluster environments
- Secret management approach needs to follow internal pattern (see brain/patterns.md)

---

### 2026-05-15 — Stage: REVIEW_SPEC
**review_status:** APPROVED
**Comments:**
- Looks good. Proceed.
```

---

## 7. Agent Roster

### 7.1 Orchestrator Agent
- Runs on heartbeat schedule (twice daily, configurable)
- Reads `pipeline-state.json` and `ideas.md`
- Dispatches work to sub-agents for any item not blocked on owner review
- Updates `pipeline-state.json` after each action
- Sends Telegram notifications on stage transitions
- Never touches `brain/` directly — delegates to Memory Agent

### 7.2 Refiner Agent
- Input: one-liner from `ideas.md` + `brain/patterns.md`
- Output: `requirements/ID-XXX/spec.md`
- Produces: full requirements, scope, edge cases, constraints, PII/secret handling notes
- Writes confidence score to `pipeline-state.json`

### 7.3 Architect / Validator Agent
- Input: `spec.md` + `brain/patterns.md`
- Output: `requirements/ID-XXX/architecture.md`
- Produces: architecture diagram (Mermaid), dry-run notes, risk flags, tech stack decisions
- Runs in read-only/sandbox mode — no live system access

### 7.4 Tester Agent
- Input: `architecture.md` + `spec.md`
- Output: `requirements/ID-XXX/tests.md`
- Produces: test plan, test cases, validation checklist, expected outputs
- Optionally runs tests in Docker sandbox before writing results

### 7.5 Memory Agent *(separate loop, not part of dev pipeline)*
- Input: `audit/YYYY-MM-DD.md` + all `review.md` files + all agent outputs
- Output: proposed updates to `brain/patterns.md` written to `brain/pending-updates.md`
- Does NOT update `brain/patterns.md` directly — owner must approve first
- Runs nightly (separate from dev pipeline heartbeat)
- Notifies owner via Telegram with a summary of proposed changes and reasoning
- On owner approval: applies changes, versions the old state to `brain/history/`

### 7.6 Audit Agent *(passive, runs alongside all agents)*
- Appends a structured entry to `audit/YYYY-MM-DD.md` for every agent action
- Records: agent name, idea ID, stage, action taken, inputs used, outputs produced, timestamp
- No owner interaction required

---

## 8. Brain / Memory Loop

This is a **separate perpetual loop** from the dev pipeline.

```
Daily audit logs + review comments
        ↓
  Memory Agent (nightly)
        ↓
  brain/pending-updates.md
        ↓
  Telegram notification → Owner reviews
        ↓
  APPROVED → brain/patterns.md updated + versioned
  REJECTED → entry discarded, reason logged
```

### What brain/patterns.md tracks:
- Secret/credential management patterns (how the owner reads passwords, env vars, vaults)
- PII handling conventions
- Preferred tech stack per problem type
- Naming conventions, file structure preferences
- Recurring feedback themes from `review.md` files
- Deployment patterns (how things get pushed, what environments exist)

### brain/pending-updates.md format:
```markdown
## Pending Brain Update — 2026-05-15

### Proposed Change 1
**Pattern area:** Secret Management
**What to add:** Owner prefers secrets read from environment variables via `os.getenv()`,
never hardcoded. Vault integration uses internal `secrets-helper` wrapper.
**Evidence:** Seen in review comments on ID-001, ID-003 and audit log 2026-05-14
**Confidence:** High

**review_status:** PENDING
```

---

## 9. Trigger Mechanisms

### 9.1 Primary: Heartbeat (Twice Daily)
- Default: 2:00 AM and 2:00 PM (configurable)
- Orchestrator wakes up, scans `pipeline-state.json`
- Processes all items not blocked on `REVIEW_*` stages
- Memory Agent runs separately at 3:00 AM

### 9.2 Secondary: Telegram Slash Commands
- `/status` — summary of all items and their current stage
- `/run ID-001` — manually trigger pipeline for a specific idea
- `/approve ID-001` — mark current review stage as APPROVED (future phase)
- `/redo ID-001` — mark current review stage as NEEDS_REVISION (future phase)
- `/pause` / `/resume` — pause or resume heartbeat processing

> Note: Inline Telegram feedback (replying with comments) is out of scope for now.  
> All detailed review is done via `review.md` files.

### 9.3 Future: Event-Driven (File Watcher)
- To be added when UI is ready
- Drag-drop on Kanban → instant agent trigger
- Uses `watchdog` (Python) or `chokidar` (Node)

---

## 10. UI (Kanban Board)

### Phase 1 (Target)
- Web-based Kanban with columns matching pipeline stages
- Cards show: ID, title, priority, confidence score, current stage, last updated
- Owner can drag cards between stages (triggers review_status update)
- Each card opens a detail view showing all artifacts (spec, architecture, tests, review)
- Owner can write/edit `review.md` inline in the UI

### Phase 2 (Future)
- Real-time updates when agents complete work
- Telegram deep-link buttons that open the relevant card
- Multi-tab layout: Kanban | Brain/Patterns | Audit Log | Settings

---

## 11. Confidence Scoring

Every agent writes a `confidence_score` (0–100) to `pipeline-state.json`.

| Score | Meaning | Action |
|---|---|---|
| 80–100 | High confidence | Proceeds normally |
| 50–79 | Medium confidence | Flagged in Telegram notification |
| 0–49 | Low confidence | Automatically paused for owner review, regardless of stage |

---

## 12. Sandbox / Dry-Run Policy

- All agents operate in **read-only mode** on live systems
- Tester Agent runs in a **Docker sandbox** before writing `tests.md`
- Execution stage (EXECUTING) runs in an **isolated VM or container**
- No production access until stage = `APPROVED` and explicitly triggered

---

## 13. Implementation Approach

- **Single codebase** within Antikythera (local)
- **Single repo** — all agents, orchestrator, UI, and brain tools live together
- This enables the Memory Agent to learn cross-cutting patterns (secrets, PII, stack) that apply to the codebase itself
- Language: Python for agent logic; Node/React for UI
- Antikythera integration: local MCP server already running with Telegram

---

## 14. Phased Build Plan

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

## 15. Open Questions / Decisions Pending

- [x] Primary language for agent codebase (Python vs Node)?
- [x] How are Docker sandboxes provisioned for the Tester Agent?
- [x] Telegram bot token and notification formatting (to be configured)
- [x] Heartbeat times — confirm 2AM / 2PM or adjust
- [x] Who assigns IDs — manual by owner, or auto-incremented by Orchestrator?
- [x] Should the Orchestrator be able to create new `ID-XXX/` directories automatically?
- [x] UI hosting — local only, or accessible remotely?

---

## 17. Resolved Implementation Decisions

### Language Stack
- **Agent Logic**: Python (preferred for automation and AI integration)
- **UI**: Node/React (for responsive web interface)

### Docker Sandbox Provisioning
- **Tester Agent**: Docker Compose for on-demand sandbox provisioning

### Telegram Integration
- **Bot Configuration**: Using existing Antikythera Telegram integration
- **Heartbeat Times**: Daily at 10 PM (adjustable to 4 times/day later)

### ID Management
- **Assignment**: Auto-incremented by Orchestrator based on existing ideas count
- **Directory Creation**: Orchestrator will automatically create new `ID-XXX/` directories

### UI Hosting
- **Access**: Local hosting only for security and simplicity

### Implementation Approach
- **Single codebase** within Antikythera (local)
- **Single repo** — all agents, orchestrator, UI, and brain tools live together
- This enables the Memory Agent to learn cross-cutting patterns (secrets, PII, stack) that apply to the codebase itself
- Language: Python for agent logic; Node/React for UI
- Antikythera integration: local MCP server already running with Telegram

---

## 16. Sample Notification (Telegram)

```
🔔 [Antikythera Pipeline] ID-001 ready for review

Stage: REVIEW_SPEC
Title: Shell script to auto assign vulnerability tickets
Confidence: 82/100

📄 spec.md has been written.
Please review: automation-ideas/requirements/ID-001/review.md

Use /status for full pipeline overview.
```

---

*This document is the living reference for the system. Update it as decisions are made.*
