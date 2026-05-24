# Antikythera Runtime Runs, Board Mapping, and Timeline Specification

This document defines the operational behavior of workflow executions, their integration with the generic Kanban board, and the mechanisms for observability and control.

## 1. Workflow Run Lifecycle

A `WorkflowRun` transitions through a finite set of states.

### 1.1 State Machine
- **PENDING**: The run is queued or waiting for trigger inputs to be fully resolved.
- **ACTIVE**: The engine is currently executing a step.
- **WAITING**: The run is paused (e.g., a `WAIT` step is active).
- **NEEDS_APPROVAL**: The run is halted at an `APPROVAL` step, awaiting human intervention.
- **BLOCKED**: A transient failure occurred, and the run is awaiting a retry or manual fix.
- **COMPLETED**: The run has successfully reached a `FINALIZE` step.
- **FAILED**: The run has encountered an unrecoverable error or exhausted retries.
- **CANCELED**: The run was manually terminated by an operator.

### 1.2 Lifecycle Transitions
- `Pending` $\rightarrow$ `Active`: Trigger fired and inputs validated.
- `Active` $\rightarrow$ `Active`: Successful completion of a step and transition to `next_step`.
- `Active` $\rightarrow$ `Waiting`: Entering a `WAIT` step.
- `Active` $\rightarrow$ `Needs_Approval`: Entering an `APPROVAL` step.
- `Active` $\rightarrow$ `Blocked`: Step failure (if retry policy allows).
- `Active` $\rightarrow$ `Completed`: Final step finished.
- `Any State` $\rightarrow$ `Canceled`: Operator action.

---

## 2. Board Mapping & Integration

To maintain the "Generic Board" rule, workflows act as **external controllers** of board items.

### 2.1 Card Generation & Binding
When a run begins, the engine determines the target card:
1. **Existing Binding**: If the trigger provides an `item_id`, the run binds to it.
2. **Auto-Generation**: If no binding exists, the engine calls `/api/items` to create a new card in the `INTAKE` stage.
3. **Binding Record**: A entry is created in `workflow_bindings` linking `run_id` $\leftrightarrow$ `item_id`.

### 2.2 State Projection to Board
The run projects its internal state onto the Kanban card using metadata and existing API endpoints:

| Run State | Board Stage | Card Metadata / Badge | Action Taken |
| :--- | :--- | :--- | :--- |
| **Active** | Mapped Stage | `[Running]` | `/api/move` to `board_mapping.stage` |
| **Waiting** | Mapped Stage | `[Waiting]` | Update `confidence_score` or add a comment |
| **Needs_Approval**| Mapped Stage | `[Approval Req]` | Add comment: "Approval required for step X" |
| **Blocked** | Mapped Stage | `[Blocked]` | Add comment: "Error in step X. Retrying..." |
| **Completed** | `DONE` | `[Workflow OK]` | `/api/move` to `DONE` |
| **Failed** | `INTAKE` or Current | `[Workflow Fail]` | Move back to `INTAKE` for triage or keep in place |

---

## 3. Execution Timeline & Eventing

The timeline is a chronological stream of `workflow_events` used for the Run Detail view.

### 3.1 Event Types & Payloads
- `STEP_START`: `{"step_id": "S1", "timestamp": "..."}`
- `STEP_END`: `{"step_id": "S1", "status": "success", "output": {...}}`
- `APPROVAL_REQUESTED`: `{"step_id": "S3", "approver_role": "Lead"}`
- `APPROVAL_GRANTED`: `{"step_id": "S3", "approver": "user_123", "decision": "APPROVED"}`
- `STATE_CHANGE`: `{"from": "ACTIVE", "to": "NEEDS_APPROVAL"}`
- `ERROR`: `{"step_id": "S2", "message": "API Timeout", "retry_count": 2}`

### 3.2 Timeline Rendering
The UI renders these events as a vertical feed.
- **Successes**: Green checkmarks.
- **Errors**: Red alerts with "View Log" links.
- **Human Actions**: Highlighted as "Operator Intervention".

---

## 4. Operator Controls

Operators can influence a running workflow through a set of audit-safe actions. Every action is recorded as a `workflow_event`.

### 4.1 Control Actions
- **Approve/Reject**: Resolves a `NEEDS_APPROVAL` state.
- **Retry**: Force-restarts the current `BLOCKED` step.
- **Skip**: Marks the current step as `SKIPPED` and moves to `next_step` (Use with caution).
- **Cancel**: Sets state to `CANCELED` and stops all execution.
- **Re-run from Step**: Rolls back the run state to a specific `step_id` and resumes.

### 4.2 Safety Constraints
- **Immutable History**: Events cannot be deleted or modified.
- **State Guard**: "Retry" is only available if the run is `BLOCKED` or `FAILED`.
- **Ownership**: Only users with `Operator` or `Admin` roles can trigger control actions.

---

## 5. Retry & Error Handling

### 5.1 Retry Policies
Defined in the `WorkflowTemplate` step config:
- **Immediate**: Retry up to $N$ times instantly.
- **Exponential Backoff**: Retry with increasing delays (e.g., 1m, 5m, 15m).
- **Manual**: Mark as `BLOCKED` and wait for operator "Retry" action.

### 5.2 Failure Paths
If all retries fail, the engine checks for an `on_failure` step ID in the `StepDefinition`.
- If `on_failure` exists: Jump to that step (e.g., a "Notify Admin" step).
- If no `on_failure`: Set run state to `FAILED` and move the bound board card to a triage stage.
