# Antikythera Phase 2 Rollout and Validation Strategy

This document defines the quality assurance and deployment sequence for transforming the Antikythera Generic Pipeline into a Workflow Automation System.

## 1. Test Matrix

To ensure the stability of the core board while introducing complex automation, we will implement a layered testing approach.

### 1.1 Unit & Schema Validation (Layer 1)
- **Template Validator**: Tests ensuring that `WorkflowTemplates` are rejected if they have cycles, orphans, or missing trigger configs.
- **Schema Integrity**: Tests verifying that JSON serialization/deserialization for templates and runs doesn't lose data.
- **Adapter Unit Tests**: Mocking external APIs to verify that GitHub/Jira adapters handle success, 404, 500, and timeout errors correctly.

### 1.2 Lifecycle & State Machine (Layer 2)
- **Transition Tests**: Verifying that a run can move from `ACTIVE` $\rightarrow$ `NEEDS_APPROVAL` $\rightarrow$ `ACTIVE` without losing context.
- **Deduplication Tests**: Triggering the same webhook 5 times in 1 second and verifying only one `WorkflowRun` is created.
- **Retry Logic**: Verifying that exponential backoff increases delays as expected.

### 1.3 Integration & E2E Scenarios (Layer 3)
These "Golden Path" scenarios must be verified before a release.

| Scenario | Expected Outcome |
| :--- | :--- |
| **The GitHub Loop** | PR Opened $\rightarrow$ Template Triggered $\rightarrow$ Run created $\rightarrow$ Card moved to `REFINEMENT` $\rightarrow$ Analysis performed $\rightarrow$ Comment added to PR. |
| **The Jira Triage** | JQL Poller finds issue $\rightarrow$ Run created $\rightarrow$ Card moved to `INTAKE` $\rightarrow$ Operator approves $\rightarrow$ Issue assigned in Jira. |
| **The Human Gate** | Run reaches `APPROVAL` step $\rightarrow$ Run state becomes `NEEDS_APPROVAL` $\rightarrow$ Board card shows `[Approval Req]` $\rightarrow$ Operator clicks "Approve" $\rightarrow$ Run continues. |
| **The Flaky API** | Action step fails with 503 $\rightarrow$ Engine retries 3 times $\rightarrow$ Final failure $\rightarrow$ Card moved to `INTAKE` for triage $\rightarrow$ Event log records all 3 attempts. |

---

## 2. Rollout Sequence

We will introduce the system in four "Waves" to minimize risk to the operational board.

### Wave 1: Foundation & Persistence (Low Risk)
- **Implementation**: Add `workflow_templates`, `workflow_runs`, and `workflow_bindings` tables/files.
- **Goal**: Enable the system to store templates and runs without actually executing them.
- **Verification**: Verify that data can be saved/loaded via API.

### Wave 2: Read-Only Observability (Low Risk)
- **Implementation**: Implement the `WorkflowRun` timeline and the Run Detail UI.
- **Goal**: Allow operators to see "Simulated" runs to verify the UI and timeline rendering.
- **Verification**: Verify that an event stream renders a correct visual timeline.

### Wave 3: The First "Live" Pipeline (Medium Risk)
- **Implementation**: Enable the Execution Engine and one single integration (e.g., GitHub).
- **Goal**: Automate one real-world process end-to-end.
- **Verification**: Run the "GitHub Loop" scenario successfully 5 times.

### Wave 4: Full Automation & Scaling (High Risk)
- **Implementation**: Enable Polling, Webhooks, and multi-integration support.
- **Goal**: Transition from manual triggers to fully autonomous, trigger-based automation.
- **Verification**: Verify that multiple different workflows can run concurrently without interfering.

---

## 3. Release Gates

A wave is considered "Released" only if:
1. **Regression Check**: The generic Kanban board still works perfectly for manual items.
2. **Stability Check**: No `FATAL` engine crashes over 24 hours of testing.
3. **Audit Check**: Every single board move performed by the engine is backed by a `workflow_event` in the timeline.

---

## 4. Fallback & Recovery

- **Manual Override**: Every workflow-bound card retains its standard `/api/move` and update capabilities. An operator can always manually move a card, which should be recorded as an "Operator Override" event in the run timeline.
- **Circuit Breaker**: If a template fails more than 10 times in an hour, the engine automatically sets its status to `Draft` (deactivated) to prevent API spam.
- **Data Recovery**: Every `WorkflowRun` stores its full `inputs` and `template_version`, allowing any failed run to be "Cloned and Fixed" for debugging.
