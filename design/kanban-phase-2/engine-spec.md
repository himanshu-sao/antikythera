# Antikythera Execution Engine and Integrations Specification

This document defines the operational logic for the Antikythera Workflow Engine, describing how triggers are ingested, how runs are managed, and how external integrations are executed.

## 1. Trigger Ingestion & Run Creation
The engine is a reactive system that maps external events to `WorkflowTemplates`.

### 1.1 Ingestion Pathways & Trigger Classes
- **Webhooks**: An endpoint `/api/hooks/{template_id}` receives JSON payloads. The engine validates the payload against the template's trigger config.
- **Polling**: A background worker periodically executes "Pollers" (e.g., checking a Jira JQL query). If new items are found, a run is triggered for each.
- **Scheduled**: A cron-based scheduler triggers templates at defined intervals.
- **Manual**: A user manually triggers a run via the UI, providing the required `inputs`.

### 1.2 Idempotent Run Creation
To prevent duplicate executions (e.g., from a webhook retry), the engine uses a **Deduplication Key**:
- `dedup_key = hash(template_id + trigger_event_id + timestamp_window)`
- If a run with the same `dedup_key` was created within the window (e.g., last 5 minutes), the engine ignores the duplicate trigger.

---

## 2. Execution Engine Logic
The engine is a non-blocking orchestrator that moves a `WorkflowRun` through its steps.

### 2.1 Step Semantics & Contract
To enable deterministic execution, the engine enforces the following contracts for each step category:

| Step Category | Input Expectation | Output Expectation | Example Config |
| :--- | :--- | :--- | :--- |
| **TRIGGER** | Event Data | `run_context` | `{"event": "push", "repo": "..."}` |
| **FETCH** | Target ID | Resource Object | `{"api": "github", "endpoint": "issue"}` |
| **EVALUATE** | Resource/Context | Boolean/Value | `{"condition": "status == 'open'"}` |
| **ACTION** | Payload | Result Status | `{"cmd": "create_comment", "body": "..."}` |
| **WAIT** | Duration/Event | Timeout/Signal | `{"seconds": 3600}` |
| **APPROVAL** | Request Text | Decision (App/Rej) | `{"role": "Project-Lead"}` |
| **BRANCH** | Condition | Next Step ID | `{"if": "value > 10", "then": "step_b"}` |
| **FINALIZE** | Final Status | Workflow Result | `{"notify": "slack", "channel": "#ops"}` |

### 2.2 Step Execution Cycle
For each step in the `WorkflowTemplate`:
1. **Context Resolution**: Resolve all variables in the `config` (e.g., replacing `{{pr_id}}` with the actual value from the trigger or previous steps).
2. **Dispatch**: Send the resolved config to the appropriate **Action Adapter**.
3. **Await Result**:
    - **Synchronous**: The adapter returns a result immediately.
    - **Asynchronous/Wait**: The adapter returns a `WAITING` signal. The engine sets the run state to `WAITING` and pauses execution.
4. **Outcome Recording**: Write a `STEP_END` event to the timeline and update the `workflow_run_steps` table.
5. **Transition**: Determine the `next_step` based on the result and the template's branching logic.

### 2.3 Wait and Resume Semantics
When a run enters a `WAIT` or `NEEDS_APPROVAL` state:
- The engine persists the current state and frees up the execution thread.
- **Resume Trigger**: The run is re-activated when:
    - A polling check finds the condition is now met.
    - A webhook callback is received.
    - An operator provides an approval.
- Upon resume, the engine loads the `WorkflowRun` and picks up exactly where it left off.

---

## 3. Integration Adapter Contracts
To avoid tight coupling with external APIs, the engine uses **Adapters**.

### 3.1 Adapter Interface
Every adapter must implement:
- `validate_config(config)`: Ensures the adapter has all required parameters.
- `execute(run_id, config, context)`: Performs the actual API call and returns a standardized result.
- `check_status(run_id, config)`: (For async steps) Returns whether the action is still pending or completed.

### 3.2 Targeted Integrations
The system is designed to support:
- **GitHub Adapter**: Handles PRs, Issues, and Commit status.
- **Jira Adapter**: Handles Ticket creation, transition, and JQL polling.
- **HTTP Adapter**: A generic adapter for calling any REST API with custom headers/payloads.
- **Internal Adapter**: For interacting with the Antikythera Kanban API (e.g., moving cards).

---

## 4. Failure Handling & Idempotency

### 4.1 Failure Classification
The engine distinguishes between different failure types to determine the recovery path:

| Failure Type | Classification | Engine Action |
| :--- | :--- | :--- |
| **Transient** | `RETRYABLE` | Trigger retry policy (Exponential Backoff). |
| **Permanent** | `FATAL` | Stop immediately $\rightarrow$ `FAILED` state $\rightarrow$ `on_failure` path. |
| **Auth Error** | `CRITICAL` | Mark as `BLOCKED` $\rightarrow$ Notify operator to update credentials. |
| **Timeout** | `RETRYABLE` | Retry once $\rightarrow$ if fail $\rightarrow$ `BLOCKED`. |

### 4.2 Retry Strategy
The engine implements the policy defined in the `WorkflowTemplate`:
- **Max Retries**: Total attempts allowed before marking as `FAILED`.
- **Backoff**: $delay = base \times (multiplier^{attempt})$.
- **Idempotency**: Every Action Adapter must include a `run_step_id` in its external API calls (where supported) to ensure that retrying a step doesn't create duplicate external resources.

---

## 5. Credential Management
Rotation: Changing a secret in the connection table immediately affects all subsequent runs without needing to edit the templates.

---

## 6. Observability & Operator Controls

### 6.1 Execution Timeline & Eventing
The timeline is a chronological stream of `workflow_events` used for the Run Detail view.
- `STEP_START`: `{"step_id": "S1", "timestamp": "..."}`
- `STEP_END`: `{"step_id": "S1", "status": "success", "output": {...}}`
- `APPROVAL_REQUESTED`: `{"step_id": "S3", "approver_role": "Lead"}`
- `APPROVAL_GRANTED`: `{"step_id": "S3", "approver": "user_123", "decision": "APPROVED"}`
- `STATE_CHANGE`: `{"from": "ACTIVE", "to": "NEEDS_APPROVAL"}`
- `ERROR`: `{"step_id": "S2", "message": "API Timeout", "retry_count": 2}`

### 6.2 Operator Control Actions
Operators can influence a running workflow through a set of audit-safe actions:
- **Approve/Reject**: Resolves a `NEEDS_APPROVAL` state.
- **Retry**: Force-restarts the current `BLOCKED` step.
- **Skip**: Marks the current step as `SKIPPED` and moves to `next_step`.
- **Cancel**: Sets state to `CANCELED` and stops all execution.
- **Re-run from Step**: Rolls back the run state to a specific `step_id` and resumes.

---

## 7. Orchestrator Integration (Human-in-the-Loop)

### 7.1 The Orchestrator Bridge
The engine can transition a `WorkflowRun` into an `OrchestratorTask` in two ways:

1. **Planned HITL Step**: A template step with `type: ORCHESTRATOR_TASK`.
    - **Action**: The engine pauses the run and creates a new item in the Kanban board with a `LifecyclePhase` set to `DISCOVERY`.
    - **Requirement**: The run enters a `WAITING_FOR_HUMAN` state.

2. **Escalated Failure**: A `CRITICAL` or `FATAL` error occurs that the retry policy cannot resolve.
    - **Action**: Instead of marking the run as `FAILED`, the engine spawns an Orchestrator task titled `Recovery: [Step Name] - [Error Message]`.
    - **Goal**: The agent must resolve the blocker (e.g., fix a broken API key) and mark the task as `DONE`.

### 7.2 The Resume Mechanism
Once the associated `OrchestratorTask` reaches the **Handover** phase and is marked as `DONE`:
1. **Signal**: The Orchestrator sends a `RESUME_RUN` event to the Execution Engine.
2. **Re-Validation**: The engine re-runs the `validate_config` check for the failed step.
3. **Execution**: If valid, the engine resumes execution from the last successful step.
