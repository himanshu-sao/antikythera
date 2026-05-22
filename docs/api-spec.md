# 📡 Hermes API Specification

This document defines the REST API contract between the Hermes Kanban UI and the Backend.

## 🌐 Base Configuration
- **Base URL**: `http://localhost:8000` (or as defined by `VITE_API_URL`)
- **Content Type**: `application/json`
- **ID Normalization**: All `item_id` parameters are coerced to uppercase by the backend.

---

## 🛠 System Endpoints

### Health Check
`GET /health`
- **Description**: Verifies API connectivity and state manager availability.
- **Success Response**: `200 OK`
  ```json
  { "status": "healthy", "service": "hermes-kanban-api" }
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
- **Description**: Initializes a new automation idea in the `INTAKE` stage.
- **Request Body**: `CreateItemRequest`
  ```json
  {
    "item_id": "string (required, 1-50 chars, alphanumeric)",
    "title": "string (required, 1-200 chars)",
    "source_type": "url | directory | null",
    "source_value": "string | null",
    "due_date": "YYYY-MM-DD | null"
  }
  ```
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Item ID-XXX created" }
  ```
- **Error Response**: `400 Bad Request` if `item_id` already exists or validation fails.

### Update Item
`PATCH /api/item/{item_id}`
- **Description**: Updates metadata for a specific item.
- **Request Body**: `UpdateItemRequest` (all fields optional)
  ```json
  {
    "title": "string",
    "description": "string",
    "priority": "low | medium | high | critical",
    "confidence_score": "number (0-100)",
    "source_type": "url | directory",
    "source_value": "string",
    "due_date": "YYYY-MM-DD"
  }
  ```
- **Success Response**: `200 OK`
  ```json
  { "status": "success", "message": "Item ID-XXX updated" }
  ```
- **Error Response**: `404 Not Found` if item does not exist.

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
