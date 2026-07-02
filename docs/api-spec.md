# 📡 Antikythera API Specification

This document defines the REST API contract between the Antikythera Kanban UI and the Backend.

## 🌐 Base Configuration
|- **Base URL**: `http://localhost:8006` (or as defined by `VITE_API_URL`)
|- **Content Type**: `application/json`
|- **ID Normalization**: All `item_id` parameters are coerced to uppercase by the backend.

---

## 🛠 System Endpoints

### Health Check
`GET /health`
- **Description**: Verifies API connectivity and state manager availability.
- **Success Response**: `200 OK`
  ```json
  { "status": "healthy", "service": "antikythera-kanban-api" }
  ```
- **Error Response**: `503 Service Unavailable` if state cannot be loaded.

---

## 📦 State & Items

### Get Full State
`GET /api/state`
- **Description**: Returns the complete `pipeline-state.json` mapping.
- **Success Response**: `200 OK`
  ```json
  {
    "last_heartbeat": "ISO8601-Timestamp",
    "items": {
      "ID-001": { ...PipelineItem }
    }
  }
  ```

### Create Item
`POST /api/items`
|- **Description**: Initializes a new automation idea in the `INTAKE` stage.
|- **Request Body**: `CreateItemRequest`
  ```json
  {
    "item_id": "string (required, 1-50 chars, alphanumeric)",
    "title": "string (required, 1-200 chars)",
    "source_type": "url | directory | text | null",
    "source_value": "string | null",
    "due_date": "YYYY-MM-DD | null"
  }
  ```
|- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Item ID-XXX created" }
  ```
|- **Error Response**: `400 Bad Request` if `item_id` already exists or validation fails.

### Update Item
`PATCH /api/item/{item_id}`
|- **Description**: Updates metadata for a specific item.
|- **Request Body**: `UpdateItemRequest` (all fields optional)
  ```json
  {
    "title": "string",
    "description": "string",
    "priority": "low | medium | high | critical",
    "confidence_score": "number (0-100)",
    "source_type": "url | directory | text",
    "source_value": "string",
    "due_date": "YYYY-MM-DD",
    "blocked_reason": "string"
  }
  ```
|- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Item ID-XXX updated" }
  ```
|- **Error Response**: `404 Not Found` if item does not exist.

### Delete Item
`DELETE /api/item/{item_id}`
- **Description**: Completely removes an item from the pipeline state.
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Item ID-XXX deleted" }
  ```
- **Error Response**: `404 Not Found` if item does not exist.

### Get Item Details
`GET /api/item/{item_id}`
- **Description**: Retrieves full metadata and history for a specific item.
- **Success Response**: `200 OK`
  ```json
  { ...PipelineItem }
  ```
- **Error Response**: `404 Not Found`.

---

## 💬 Comments

### Add Comment
`POST /api/item/{item_id}/comment`
- **Description**: Appends a new discussion comment.
- **Request Body**: `CommentRequest`
  ```json
  {
    "author": "string (required)",
    "body": "string (required)"
  }
  ```
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "comment": { "id": "com_...", "author": "...", "body": "...", "createdAt": "..." } }
  ```

### Delete Comment
`DELETE /api/item/{item_id}/comment/{comment_id}`
- **Description**: Removes a specific comment.
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Comment com_... deleted" }
  ```

---

## 🔄 Pipeline Movement

### Move Item
`POST /api/move`
- **Description**: Updates the stage and optional order of a pipeline item.
- **Request Body**: `MoveRequest`
  ```json
  {
    "item_id": "string (required)",
    "new_stage": "INTAKE | REFINEMENT | ... | DONE",
    "order": "number (optional)"
  }
  ```
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Item ID-XXX moved to STAGE" }
  ```

### Bulk Reorder
`POST /api/items/reorder`
- **Description**: Sets the sequence of items within a specific stage.
- **Request Body**: `ReorderRequest`
  ```json
  {
    "stage": "string (required)",
    "ordered_ids": ["ID-001", "ID-003", "ID-002"]
  }
  ```
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Reordered X items in STAGE" }
  ```

---

## 📄 Artifacts

### Get Artifact
`GET /api/item/{item_id}/artifact/{artifact_name}`
- **Valid Artifacts**: `spec.md`, `architecture.md`, `tests.md`, `review.md`
- **Success Response**: `200 OK` (FileResponse) or `204 No Content` if file doesn't exist.

### Update Artifact Content
`POST /api/item/{item_id}/artifact/{artifact_name}/content`
- **Restriction**: Only `review.md` can be edited via this endpoint.
- **Request Body**:
  ```json
  { "content": "string" }
  ```
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Updated review.md for ID-XXX" }
  ```
- **Error Response**: `400 Bad Request` if artifact is not `review.md`.


---

## 🤖 AI Engine Configuration

### List Models
`GET /api/ai-engine/models`
- **Description**: Lists available AI models across all configured providers.
- **Query Parameters**: `provider` (optional): Filter by provider name.
- **Success Response**: `200 OK` — JSON array of model objects.

### Add Model
`POST /api/ai-engine/models`
- **Description**: Registers a new AI model configuration.
- **Request Body**: Provider, model ID, display name, and config.

### Delete Model
`DELETE /api/ai-engine/models/{model_id}`
- **Description**: Removes an AI model configuration.

### List Providers
`GET /api/ai-engine/providers`
- **Description**: Lists all configured AI providers (Ollama, NVIDIA NIM, Google Gemma, IBM Bob, OpenAI, Anthropic, OpenRouter).

### Test Connection
`POST /api/ai-engine/test-connection`
- **Description**: Tests connectivity to a specific AI provider.

### API Key Management
`GET /api/ai-engine/keys` / `POST /api/ai-engine/keys` / `DELETE /api/ai-engine/keys/{key_id}`
- **Description**: CRUD for provider API keys.

---

## ⚙️ Automation & Skills

### Compile Automation
`POST /api/automation/compile`
- **Description**: Compiles a natural language automation description into a workflow template.
- **Tag**: Automation Compiler

### List / Search Skills
`GET /api/skills`
- **Description**: Lists available operator skills from the registry.
- **Tag**: Skill Brainstormer

---

## 🔀 Pipeline Management

### Pipeline CRUD
`GET /api/pipelines` / `POST /api/pipelines` / `GET /api/pipelines/{id}`
- **Description**: Manage workflow pipeline definitions.

### Pipeline Runs
`POST /api/pipelines/{id}/runs` / `GET /api/pipelines/{id}/runs`
- **Description**: Execute and monitor pipeline runs.

### Pipeline Logs
`GET /api/pipelines/{id}/runs/{run_id}/logs`
- **Description**: Retrieve execution logs for a pipeline run.
- **Tag**: Pipeline Management

---

## 🔌 Integrations

### List Integrations
`GET /api/integrations`
- **Description**: Lists all configured external integrations.

### Add / Update / Delete Integration
`POST /api/integrations` / `PATCH /api/integrations/{id}` / `DELETE /api/integrations/{id}`
- **Description**: Manage integration connections (Jira, GitHub, etc.).

### Test Integration Connection
`POST /api/integrations/{id}/test`
- **Description**: Tests connectivity to an external service.

### Jira-Specific
`GET /api/jira/*` / `POST /api/jira/*`
- **Description**: Jira-specific operations (test connection, search issues, etc.).

---

## 🧠 Brain & Learning

### Get Patterns
`GET /api/patterns`
- **Description**: Retrieves learned patterns from the PatternStore.

### Promote Pattern
`POST /api/patterns/promote`
- **Description**: Promotes a human-corrected resolution to the pattern store.

### Brain Loop Status
`GET /api/brain/status`
- **Description**: Returns memory/learning system status.

---

## 🏃 Execution Engine

### List Workflow Templates
`GET /api/workflow-templates`
- **Description**: Returns all workflow template definitions from `workflow_templates.json`.

### Start Workflow Run
`POST /api/engine/start`
- **Description**: Initiates a workflow run from a template with optional context.

### Get Run Status
`GET /api/engine/runs/{run_id}`
- **Description**: Returns the current state and step history of a workflow run.

### Workflow Step Action
`POST /api/engine/runs/{run_id}/action`
- **Description**: Applies a human action (approve, reject, retry, skip) to a step awaiting approval.

### Trigger Management
`GET /api/triggers` / `POST /api/triggers` / `DELETE /api/triggers/{id}`
- **Description**: Manage event, schedule, and webhook triggers for workflow templates.

---

## 🎯 Orchestrator

### Orchestrator Status
`GET /api/orchestrator/status`
- **Description**: Returns orchestrator state machine status and pipeline health.

### Orchestrator Action
`POST /api/orchestrator/action`
- **Description**: Triggers an orchestrator action (e.g., force-reprocess, heartbeat).

---

*Note: Many routers (board, integrations, jira, orchestrator, engine, trigger) are registered without an explicit `/api/` prefix in `main.py`. The actual URL paths may differ from the documented ones. Check `api/main.py` for the exact route registrations.*
