# Antikythera System Model - Phase 2 Foundation

This document defines the canonical schema, architectural layers, and system model for the Antikythera workflow automation system.

## 1. Core Product Philosophy

### 1.1 The Generic Board Rule
The Kanban board remains a generic execution surface. 
- No workflow-specific columns.
- No GitHub-only or Jira-only stage models.
- Workflow-specific logic belongs to reusable definitions and runtime state, not to the base board structure.

### 1.2 The Three-Layer Architecture
The system operates across three distinct layers:
1. **Generic Pipeline Board**: The shared operational surface for all items.
2. **Workflow Template Authoring**: The design-time environment for creating reusable blueprints.
3. **Workflow Run Execution**: The runtime environment for executing and inspecting specific instances of a template.

---

## 2. Workflow Template Model
A `WorkflowTemplate` is a reusable blueprint for an automation process.

### 2.1 Schema: `workflow_templates`
- `template_id`: (String, PK) Unique identifier (e.g., "PR-RELEASE-FLOW").
- `name`: (String) Human-readable name.
- `description`: (String) Detailed purpose of the workflow.
- `version`: (String) SemVer version of the template.
- `trigger`: (Object)
    - `type`: (Enum: "SCHEDULE", "WEBHOOK", "POLLING", "MANUAL")
    - `config`: (JSON) Trigger-specific parameters (e.g., cron expression, URL).
- `inputs`: (List[Object]) Required input parameters.
    - `key`: (String) Input key.
    - `type`: (Enum: "STRING", "INTEGER", "BOOLEAN")
    - `required`: (Boolean)
- `steps`: (List[StepDefinition]) Ordered list of steps.
- `created_at`: (ISO8601 Timestamp)
- `updated_at`: (ISO8601 Timestamp)

### 2.2 Schema: `workflow_steps` (StepDefinition)
- `step_id`: (String, PK) Unique ID within the template.
- `name`: (String) Step name.
- `category`: (Enum: "TRIGGER", "FETCH", "EVALUATE", "ACTION", "WAIT", "APPROVAL", "BRANCH", "FINALIZE")
- `config`: (JSON) Implementation details for the step.
- `next_step`: (String, Optional) ID of the next step in the linear path.
- `on_failure`: (String, Optional) Step ID to jump to on error.
- `board_mapping`: (Object, Optional)
    - `stage`: (String) Which Kanban stage this step represents.
    - `visual_label`: (String) Label to show on the card.

### 2.3 Authoring & Validation Rules
A template must be `Validated` before it can be set to `Active`.
- **Trigger Validation**: Cron expressions must be valid; Webhooks must have endpoint URLs.
- **Sequence Validation**: Exactly one entry point; no orphaned steps; must be a Directed Acyclic Graph (DAG) unless explicit loop-termination is defined.
- **Contract Validation**: Required step inputs must be provided by global template inputs or previous step outputs.

---

## 3. Workflow Run Model
A `WorkflowRun` is a specific instance of a `WorkflowTemplate` execution.

### 3.1 Run Lifecycle & State Machine
- **PENDING**: Queued or awaiting trigger input resolution.
- **ACTIVE**: Engine is currently executing a step.
- **WAITING**: Paused (e.g., a `WAIT` step is active).
- **NEEDS_APPROVAL**: Halted at an `APPROVAL` step, awaiting human intervention.
- **BLOCKED**: Transient failure occurred, awaiting retry or manual fix.
- **COMPLETED**: Successfully reached a `FINALIZE` step.
- **FAILED**: Unrecoverable error or exhausted retries.
- **CANCELED**: Manually terminated by an operator.

### 3.2 Schema: `workflow_runs`
- `run_id`: (String, PK) Unique execution ID.
- `template_id`: (String, FK) Reference to the template.
- `template_version`: (String) Version used for this run.
- `status`: (Enum: "PENDING", "RUNNING", "WAITING_FOR_APPROVAL", "COMPLETED", "FAILED", "CANCELLED")
- `current_step_id`: (String) The step currently being executed.
- `inputs`: (JSON) The actual values provided for this specific run.
- `started_at`: (ISO8601 Timestamp)
- `completed_at`: (ISO8601 Timestamp, Optional)
- `error`: (String, Optional) Final error message if failed.

### 3.3 Schema: `workflow_run_steps`
- `run_step_id`: (String, PK)
- `run_id`: (String, FK)
- `step_id`: (String, FK)
- `status`: (Enum: "PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED")
- `started_at`: (ISO8601 Timestamp)
- `finished_at`: (ISO8601 Timestamp, Optional)
- `output`: (JSON, Optional) Result of the step execution.

---

## 4. Board Integration & Bindings
Workflows act as **external controllers** of board items to maintain the Generic Board rule.

### 4.1 Card Generation & Binding
When a run begins, the engine determines the target card:
1. **Existing Binding**: If the trigger provides an `item_id`, the run binds to it.
2. **Auto-Generation**: If no binding exists, the engine calls `/api/items` to create a new card in the `INTAKE` stage.
3. **Binding Record**: A entry is created in `workflow_bindings` linking `run_id` $\leftrightarrow$ `item_id`.

### 4.2 State Projection to Board
The run projects its internal state onto the Kanban card:

| Run State | Board Stage | Card Metadata / Badge | Action Taken |
| :--- | :--- | :--- | :--- |
| **Active** | Mapped Stage | `[Running]` | `/api/move` to `board_mapping.stage` |
| **Waiting** | Mapped Stage | `[Waiting]` | Update `confidence_score` or add a comment |
| **Needs_Approval**| Mapped Stage | `[Approval Req]` | Add comment: "Approval required for step X" |
| **Blocked** | Mapped Stage | `[Blocked]` | Add comment: "Error in step X. Retrying..." |
| **Completed** | `DONE` | `[Workflow OK]` | `/api/move` to `DONE` |
| **Failed** | `INTAKE` or Current | `[Workflow Fail]` | Move back to `INTAKE` for triage or keep in place |

### 4.3 Schema: `workflow_bindings`
- `binding_id`: (String, PK)
- `run_id`: (String, FK)
- `item_id`: (String, FK) Reference to the Antikythera Kanban item.
- `binding_type`: (Enum: "PRIMARY", "RELATED")
- `created_at`: (ISO8601 Timestamp)

---

## 5. Event Logging & Auditing
The Event Log is an append-only record for timeline rendering and debugging.

### 5.1 Schema: `workflow_events`
- `event_id`: (String, PK)
- `run_id`: (String, FK)
- `timestamp`: (ISO8601 Timestamp)
- `event_type`: (Enum: "STEP_START", "STEP_END", "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "STATE_CHANGE", "ERROR")
- `payload`: (JSON) Event-specific data (e.g., `{"from": "INTAKE", "to": "REFINEMENT"}`).
- `actor`: (String) The agent or human who triggered the event.

---

## 6. Approvals & Connections

### 6.1 Schema: `approval_records`
- `approval_id`: (String, PK)
- `run_id`: (String, FK)
- `step_id`: (String, FK)
- `approver`: (String) User ID of the person who approved.
- `decision`: (Enum: "APPROVED", "REJECTED")
- `comment`: (String)
- `timestamp`: (ISO8601 Timestamp)

### 6.2 Schema: `integration_connections`
- `connection_id`: (String, PK)
- `provider`: (Enum: "GITHUB", "JIRA", "SLACK", "CUSTOM")
- `config`: (Encrypted JSON) Auth tokens, API keys, base URLs.
- `status`: (Enum: "ACTIVE", "EXPIRED", "DISABLED")

---

## 7. Validation & Rollout Strategy

### 7.1 Test Matrix
- **Layer 1 (Unit/Schema)**: Template validation (cycle detection), JSON integrity, Adapter mocks.
- **Layer 2 (Lifecycle)**: State transition tests (`ACTIVE` $\rightarrow$ `NEEDS_APPROVAL`), Deduplication checks, Exponential backoff verification.
- **Layer 3 (E2E Scenarios)**: "Golden Path" verification (e.g., GitHub PR $\rightarrow$ Card Move $\rightarrow$ Analysis $\rightarrow$ PR Comment).

### 7.2 Rollout Sequence
1. **Wave 1 (Foundation)**: Implement persistence (`templates`, `runs`, `bindings`).
2. **Wave 2 (Observability)**: Implement Run Detail UI and Event Timeline.
3. **Wave 3 (First Live Pipeline)**: Enable Execution Engine + one integration (GitHub).
4. **Wave 4 (Scaling)**: Enable Polling, Webhooks, and multi-integration support.
