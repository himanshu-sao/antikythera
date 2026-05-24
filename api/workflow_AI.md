# 🤖 Antikythera Workflow Engine Briefing

**Purpose**: Specialized context for the automation logic, triggers, and runtime execution.

---

## ⚙️ The Workflow Model
Unlike the linear Pipeline, Workflows are **graphs of executable steps** that can be triggered by events or schedules.

### 1. Workflow Templates
- Defined in `automation-ideas/workflow_templates.json`.
- Contain a sequence of steps, each mapped to an agent or a tool.
- Support branching and conditional execution based on step results.

### 2. The Execution Engine (`WorkflowEngine`)
- Responsible for iterating through steps in a template.
- Manages "Run State" in `automation-ideas/workflow_runs.json`.
- Handles retries via `RetryManager`.

### 3. Trigger System (`TriggerManager`)
- **Event-Driven**: Watches for external events (e.g., GitHub PR, Jira ticket) via adapters.
- **Scheduled**: Runs on a heartbeat via the `Scheduler`.
- **Manual**: Triggered via the UI or Telegram.

## 🔄 Workflow $\rightarrow$ Pipeline Integration
Workflows can "inject" items into the Pipeline. For example, a "Bug Report" workflow can automatically create an `INTAKE` card on the Kanban board.

## 🛠 Technical Constraints
- **Isolation**: Workflow runs should not mutate global pipeline state directly; they should use the `WorkflowStateManager`.
- **Timeouts**: Every workflow step must have a defined timeout to prevent zombie processes.
- **Logging**: Every run generates a unique `RUN-ID` and logs events to `.jsonl` files in `automation-ideas/events/`.
