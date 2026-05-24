# Antikythera Workflow Builder and Template Authoring Specification

This document defines the UX, data rules, and implementation plan for the workflow authoring experience.

## 1. Information Architecture (IA)

The "Workflows" surface is a primary navigation destination, separate from the "Pipeline Board".

### 1.1 Template List View
The entry point for workflow management.
- **Columns**: Template Name, Description, Trigger Type, Version, Status (Active/Draft), Last Modified.
- **Actions**: 
    - `Create New Template` (Primary CTA).
    - `Duplicate` (Clone an existing template to start a new one).
    - `Edit` (Opens the Builder).
    - `Activate/Deactivate` (Toggles whether the template can be triggered).

### 1.2 Template Detail & Builder View
A split-screen or full-page experience focused on the template definition.
- **Header**: Name, Description, and Versioning controls.
- **Trigger Section**: Configuration for the trigger (e.g., defining a cron string for SCHEDULE or a webhook payload for WEBHOOK).
- **Input Definition**: Table of required inputs (key, type, default value, required flag).
- **Workflow Canvas**: A vertical or graph-based builder.
    - **Step Card**: Displays Step ID, Name, Category (e.g., ACTION), and a summary of its config.
    - **Connector**: Visual line representing `next_step`.
    - **Step Editor**: Side panel to configure the specific `config` JSON for the selected step.

---

## 2. Authoring Model & Data Rules

### 2.1 Template Lifecycle
1. **Draft**: Template is being edited. It cannot be triggered.
2. **Validated**: Template passes all validation rules (see Section 3).
3. **Active**: Template is deployed and can be triggered.

### 2.2 Versioning Logic
Templates use Semantic Versioning (SemVer).
- **Patch**: Minor config changes (e.g., updating a description).
- **Minor**: Adding a non-breaking step or input.
- **Major**: Changing the trigger, removing required inputs, or altering the core logic flow.
- **Duplication**: When a template is duplicated, it creates a new `template_id` with version `1.0.0` and copies the logic.

---

## 3. Validation Rules

A template cannot be moved from `Draft` to `Active` unless the following are true:

### 3.1 Trigger Validation
- **SCHEDULE**: Cron expression must be valid.
- **WEBHOOK**: Endpoint URL or event type must be specified.
- **POLLING**: Interval and query criteria must be defined.

### 3.2 Step Sequence Validation
- **Entry Point**: Exactly one step must be designated as the starting step.
- **Connectivity**: Every step (except the final `FINALIZE` step) must have a valid `next_step` or a logical branching path.
- **Cycle Detection**: The workflow must be a Directed Acyclic Graph (DAG) or have explicit loop-termination conditions to prevent infinite runs.
- **Orphan Check**: No steps should exist that cannot be reached from the entry point.

### 3.3 Contract Validation
- **Input Matching**: If a step requires a specific input, it must either be defined in the template's global `inputs` or provided by a previous step's output.
- **Required Fields**: All `config` fields required by the step category (e.g., `action_type` for ACTION steps) must be present.

---

## 4. Step Semantics & Contract

To enable the engine (Phase 2.03/04) to execute steps, the builder enforces the following contracts:

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

---

## 5. Minimal Serialization Format (JSON)

Templates are stored as JSON objects conforming to the `WorkflowTemplate` schema defined in the system model.

```json
{
  "template_id": "GITHUB_PR_REVIEW",
  "name": "PR Review Automation",
  "version": "1.1.0",
  "trigger": {
    "type": "WEBHOOK",
    "config": { "event": "pull_request", "action": "opened" }
  },
  "inputs": [
    { "key": "reviewer_group", "type": "STRING", "required": true }
  ],
  "steps": [
    {
      "step_id": "ST-01",
      "name": "Fetch PR Details",
      "category": "FETCH",
      "config": { "resource": "pull_request", "id": "{{pr_id}}" },
      "next_step": "ST-02",
      "board_mapping": { "stage": "INTAKE", "visual_label": "Fetching PR" }
    },
    {
      "step_id": "ST-02",
      "name": "Check Labels",
      "category": "EVALUATE",
      "config": { "condition": "labels.contains('urgent')" },
      "next_step": "ST-03",
      "on_failure": "ST-04"
    },
    {
      "step_id": "ST-03",
      "name": "Request Urgent Review",
      "category": "ACTION",
      "config": { "type": "notify", "channel": "urgent-channel" },
      "next_step": "ST-05"
    },
    {
      "step_id": "ST-04",
      "name": "Standard Review",
      "category": "ACTION",
      "config": { "type": "assign_reviewer" },
      "next_step": "ST-05"
    },
    {
      "step_id": "ST-05",
      "name": "Mark as Processed",
      "category": "FINALIZE",
      "config": { "status": "completed" }
    }
  ]
}
```
