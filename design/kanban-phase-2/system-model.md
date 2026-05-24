# Antikythera System Model - Phase 2 Foundation

This document defines the canonical schema and system model for the Antikythera workflow automation system.

## 1. Workflow Template Model
A `WorkflowTemplate` is a reusable blueprint for an automation process.

### Schema: `workflow_templates`
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

### Schema: `workflow_steps` (StepDefinition)
- `step_id`: (String, PK) Unique ID within the template.
- `name`: (String) Step name.
- `category`: (Enum: "TRIGGER", "FETCH", "EVALUATE", "ACTION", "WAIT", "APPROVAL", "BRANCH", "FINALIZE")
- `config`: (JSON) Implementation details for the step.
- `next_step`: (String, Optional) ID of the next step in the linear path.
- `on_failure`: (String, Optional) Step ID to jump to on error.
- `board_mapping`: (Object, Optional)
    - `stage`: (String) Which Kanban stage this step represents.
    - `visual_label`: (String) Label to show on the card.

---

## 2. Workflow Run Model
A `WorkflowRun` is a specific instance of a `WorkflowTemplate` execution.

### Schema: `workflow_runs`
- `run_id`: (String, PK) Unique execution ID.
- `template_id`: (String, FK) Reference to the template.
- `template_version`: (String) Version used for this run.
- `status`: (Enum: "PENDING", "RUNNING", "WAITING_FOR_APPROVAL", "COMPLETED", "FAILED", "CANCELLED")
- `current_step_id`: (String) The step currently being executed.
- `inputs`: (JSON) The actual values provided for this specific run.
- `started_at`: (ISO8601 Timestamp)
- `completed_at`: (ISO8601 Timestamp, Optional)
- `error`: (String, Optional) Final error message if failed.

### Schema: `workflow_run_steps`
- `run_step_id`: (String, PK)
- `run_id`: (String, FK)
- `step_id`: (String, FK)
- `status`: (Enum: "PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED")
- `started_at`: (ISO8601 Timestamp)
- `finished_at`: (ISO8601 Timestamp, Optional)
- `output`: (JSON, Optional) Result of the step execution.

---

## 3. Board Integration & Bindings
The "Generic Board" rule ensures that the board doesn't know about workflows, but workflows know about the board.

### Schema: `workflow_bindings`
- `binding_id`: (String, PK)
- `run_id`: (String, FK)
- `item_id`: (String, FK) Reference to the Antikythera Kanban item.
- `binding_type`: (Enum: "PRIMARY", "RELATED")
- `created_at`: (ISO8601 Timestamp)

**Binding Logic:**
- When a `WorkflowRun` starts, it may create a new Kanban item (via `/api/items`) or bind to an existing one.
- As the run progresses through steps that have `board_mapping`, the system calls `/api/move` to advance the linked Kanban item to the mapped stage.

---

## 4. Event Logging & Auditing
The Event Log is an append-only record for timeline rendering and debugging.

### Schema: `workflow_events`
- `event_id`: (String, PK)
- `run_id`: (String, FK)
- `timestamp`: (ISO8601 Timestamp)
- `event_type`: (Enum: "STEP_START", "STEP_END", "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "STATE_CHANGE", "ERROR")
- `payload`: (JSON) Event-specific data (e.g., `{"from": "INTAKE", "to": "REFINEMENT"}`).
- `actor`: (String) The agent or human who triggered the event.

---

## 5. Approvals & Connections

### Schema: `approval_records`
- `approval_id`: (String, PK)
- `run_id`: (String, FK)
- `step_id`: (String, FK)
- `approver`: (String) User ID of the person who approved.
- `decision`: (Enum: "APPROVED", "REJECTED")
- `comment`: (String)
- `timestamp`: (ISO8601 Timestamp)

### Schema: `integration_connections`
- `connection_id`: (String, PK)
- `provider`: (Enum: "GITHUB", "JIRA", "SLACK", "CUSTOM")
- `config`: (Encrypted JSON) Auth tokens, API keys, base URLs.
- `status`: (Enum: "ACTIVE", "EXPIRED", "DISABLED")
