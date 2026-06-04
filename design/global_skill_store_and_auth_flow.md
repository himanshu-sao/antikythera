# Design: Global Skill Store & Auth Flow

## 1. Global Skill Store

### 1.1 Purpose
To store reusable skills (especially parsing skills) that can be shared across different paths and pipelines.
Skills are text extractors that use regex or JSON paths to pull structured data from unstructured text (e.g., Jira descriptions, GitHub issue bodies).

### 1.2 Skill Structure
A skill is defined by the following attributes:
- `skill_id`: Unique identifier (string)
- `name`: Human-readable name (string)
- `category`: SkillCategory (EXTRACTION, TRANSFORMATION, CLASSIFICATION, PARSING)
- `few_shot_prompt`: The prompt used to guide the AI in generating the skill's logic (string)
- `output_schema`: JSON schema defining the expected output structure (object)
- `version`: Semantic version string (default: "1.0.0")
- `created_at`: Timestamp of creation (datetime)
- `skill_type`: Either "action" or "parse" (literal)
- `parser_config`: For parse skills, contains regex patterns or JSON paths (object, optional)

### 1.3 Storage
- **In-Memory**: For development and testing, skills are stored in an in-memory dictionary (as seen in `skill_router.py`).
- **Persistent**: In production, skills will be stored in a JSON file or database under the `automation-ideas` directory (same as the skill router's base directory).
- **File Format**: Each skill can be stored as a separate JSON file named `<skill_id>.json` or as a single JSON array file.

### 1.4 Skill Router API (Existing)
The existing skill router provides:
- `POST /brainstorm`: Generate a few-shot prompt and schema from a text sample and target fields.
- `POST /save`: Save a finalized skill.
- `GET /{skill_id}`: Retrieve a skill by ID.

### 1.5 Skill Usage in OperatorRegistry
The `OperatorRegistry` will be extended to:
- Load all skills from the global skill store (or a subset marked as global).
- Provide a method `execute_parsing_skill(skill_id, text)` that runs a parsing skill's logic on input text.
- For parse skills, the logic is:
  1. If the skill has `parser_config` with regex patterns, apply each pattern to the text and extract named groups.
  2. If the skill has `parser_config` with JSON paths, parse the text as JSON and extract values at those paths.
  3. Combine results into a dictionary matching the skill's `output_schema`.
- The `OperatorRegistry` will also handle fallback: if a skill fails to parse, return empty dict and log warning.

### 1.6 Skill Re-use Across Paths
- When a path is promoted to a pipeline, its parsing skills are automatically added to the global skill store.
- When a new path is created, it can reference existing global skills by ID in its steps' `config` (for parse steps) or by importing them via the skill store.
- The `OperatorRegistry` will maintain a list of active parsing skills (from global store and path-specific) to pass to loop steps for field extraction.

## 2. Auth Prompt Flow for 401

### 2.1 Purpose
To handle authentication errors (HTTP 401) gracefully by prompting the user for credentials, updating the secret vault, and retrying the failed step.

### 2.2 Flow
1. **Detection**: When an adapter (e.g., JiraAdapter, GitHubAdapter) receives an HTTP 401 response, it raises an `AuthError` exception.
2. **Catch**: The `OperatorRegistry` catches `AuthError` during step execution.
3. **Prompt**: The system triggers a system proposal to the user: 
   - Title: "Authentication Required"
   - Message: "The step '[step_id]' failed due to missing or invalid credentials for [adapter_name]. Please provide a valid token."
   - Input: A text field for the token (password-style input).
4. **Update**: On user submission, the token is stored in the secret vault under the appropriate key (e.g., `jira_token`, `github_token`).
5. **Retry**: The step is retried automatically with the updated credentials.
6. **Limit**: To prevent infinite loops, retry is limited to 3 attempts per step execution.

### 2.3 Implementation Details
- **Adapter Modification**: Each adapter (JiraAdapter, GitHubAdapter) will check for 401 in its HTTP methods and raise a custom `AuthError` (or reuse `HTTPException` with status 401).
- **OperatorRegistry**: 
  - Add a try-catch block around adapter calls to catch `AuthError`.
  - On catch, invoke the system proposal mechanism (similar to dynamic package install).
  - After successful user input, update the vault and retry the step.
- **Secret Vault**: The existing `SecretVault` class (in `secret_vault.py`) is used to store tokens. It already supports reading and writing secrets to files in the `automation-ideas` directory.
- **UI Component**: The `AutomationStudio` component will need to handle the auth prompt modal (this is covered in task 4.5.3).

### 2.4 Security Considerations
- Tokens are stored in the secret vault, which is encrypted at rest (using a vault key).
- The vault key is stored in `.vault.key` and should be kept secure.
- Tokens are never logged or exposed in API responses.
- The auth prompt is shown only to the user in the current session and is not stored.

## 3. Open Questions
- Should skills have an `is_global` flag to control whether they are shared?
- How should skill versioning be handled when updating a skill?
- Should we allow skill dependencies (e.g., one skill building on another)?

## 4. Conclusion
This design provides a reusable skill store for parsing and other skills, and a secure auth prompt flow to handle 401 errors. It enables the system to be more robust and user-friendly in the face of missing credentials and promotes sharing of extraction logic across automation paths.
