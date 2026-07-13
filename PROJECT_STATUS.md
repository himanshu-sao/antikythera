# 🚩 Project Status: Antikythera

This is the **single master document** for the Antikythera project. It tracks the roadmap, current status, technical gaps, and verification criteria.

## 📊 Current Executive Summary
- **System State**: Cognitive Orchestration System (Hybrid Pipeline + Workflow Engine).
- **Overall Status**: Backend pipeline (Refiner→Architect→Tester) is live and persists artifacts; the July 2026 P0→P2 remediation arc closed the worst runtime defects and wired real LLM providers behind agents/routers. Remaining work is throughput (the Executor/learning stages still stub) and P3 debt hygiene.
- **Active Focus**: Fixing the learning `"stub response"` loop, producing one real end-to-end idea carried past spec, and stabilizing the Playwright e2e suite.

---

## 🗺️ Project Roadmap

### 1. Core System Implementation (Completed)
- [x] **Phase 0-3**: Foundation, Orchestrator, Architect/Tester Agents, and basic notifications.
- [x] **Phase 4-6**: Memory Agent, Kanban UI (Read/Write/Drag-and-Drop), and real-time updates.
- [x] **Phase 7-11**: Event-driven triggers, Automation Registry, Regression Loop, Pattern Promotion, and Execution Engine.

### 2. UI Refinement & Verification (In Progress)
- [x] **Phase 1**: Discovery & Context audit.
- [x] **Phase 2**: Architectural Blueprint & directory structure.
- [x] **Phase 3**: Atomic Implementation (Modular App, custom hooks).
- [x] **Phase 4: Unit Verification**
    - [x] Fix `App.test.tsx` parse errors.
    - [x] Fix `ArtifactViewer.test.tsx` timeouts.
    - [x] Fix `App.polling.test.tsx` environment issues.
    - [x] Stabilize `ArtifactViewer.edit.test.tsx`.
    - [ ] **Implement "Workflow Architect" component**.
    - [x] Verify Lifecycle Orchestrator End-to-End.
- [x] **Phase 5: Integration Flow**
    - [ ] Test component interactions and API flows.
    - [x] **Decouple "Compose Instruction" from Jira (Use Integration Hub selector)**.
    - [x] **Implement Structured Jira Configuration (URL, Password) in Integrations Hub**.
    - [x] **Fix Integration Connection Status UI/API**.
    - [x] **Implement Capability Discovery in Integration Detail Modal**.
- [ ] **Phase 6: System Validation**
    - [ ] End-to-end user journey testing.
    - [ ] Error scenario and recovery validation.
- [ ] **Phase 7: Handover**
    - [ ] Final documentation and handover.

---

## 🛠️ Backend Remediation Arc (July 2026)

A stop-the-bleed → wiring → real-LLM pass applied over 2026-07-11/12. Tracked here so it is not lost between sessions. Each item below is **verified present in the codebase** on `main` (HEAD as of this update).

### P0 — Stop-the-bleed (✅ complete)
- [x] **P0.1 Orchestrator GET `/{item_id}` 500** — `orchestrator_router.py` now uses `state_manager.get_item_details()` (was `.items.get()` on a dict → AttributeError). Uppercase ID-normalized.
- [x] **P0.2 `set_default_model` unreachable** — added missing `@router.post("/set-default")` decorator in `ai_engine_config_router.py`.
- [x] **P0.3 Jira adapter env-based auth** — token resolution now env-first (`JIRA_PAT`/`JIRA_TOKEN`) with vault fallback; `_get_token()` helper; `AuthError`→401 (was 500 for all). `JiraAdapter(None)` safe to construct.
- [x] **P0.4 CORS spec violation** — `allow_credentials=False` (was `["*"]` + `credentials=True`, which browsers reject).
- [x] **P0.5 `npm test` runner** — `ui/package.json` `"test": "vitest run"` (already correct; prior session memory was stale).
- [x] **Test hardening** — `JIRA_PAT` env-leak into no-token tests fixed across `test_adapters.py`, `test_auth_retry.py`, `test_operator_registry_simple.py`, `test_integrations_api.py`.

### P1 — Wire what's built but disconnected (✅ complete)
- [x] **P1.1 `_execute_native` real dispatch** — `integration_hub.py` now `importlib.import_module`s the adapter and maps action→method (`fetch_resource→fetch`, etc.) instead of returning a fake success.
- [x] **P1.2 Register all adapters** — `BobShellAdapter` + `InternalKanbanAdapter` registered alongside Jira/GitHub.
- [x] **P1.3 Register dead routers** — `trigger_router`, `builder_router`, `workflow_router` now `include_router`'d. `workflow_router` moved to `/api/workflows` prefix (matches UI). ⚠️ Pre-existing mismatch remains: UI calls `/api/workflows/trigger` but trigger_router serves `/api/triggers/webhook/{provider}` — see P2.5.
- [x] **P1.4 Lifecycle wiring** — `lifespan` context manager starts/stops `AntikytheraScheduler`; `RetryManager` constructed and injected into `ExecutionEngine` + `app.state`. Retries scheduled via daemon `threading.Timer`. ⚠️ Confirm thread-safety of run-state mutation from the timer thread before relying on retries in prod.
- [x] **P1.5 `internal.py` state race** — adapter now uses `api.main.get_state_manager()` (guarded by `isinstance(wf_mgr, WorkflowStateManager)`), eliminating the legacy `StateManager` lock-file race.

### P2 — Real LLM behind agents & routers (✅ complete)
- [x] **P2.1/P2.2 Wire real LLM provider** — `LLMClient` resolves provider/model from `AIEngineConfigService` first, falls back to `config.yaml`.
- [x] **P2.3 Wire AIEngineConfigService into agent execution layer** — `LLMClient` extended from 2 to all 8 providers via a single OpenAI-compatible path + Google GenAI path; graceful degradation (missing API keys deferred from init to `chat()`; placeholder `"antikythera-missing-key"` prevents construction failure). `AIAdapter.analyze()` routed through shared `LLMClient.chat()` with JSON parsing + deterministic `_simulate_llm_call` fallback. Fake `sk-antikythera-sim` key removed. Backend tests: 233 passed / 4 deselected / 5 skipped (fast suite excludes live-LLM integration tests).
- [x] **P2.4 Normalize `automation/skill/builder` routers** — DONE 2026-07-13. `automation_router /propose` and `skill_router /brainstorm` now call the shared `LLMClient.chat()` (UI-default provider/model, falling back to `config.yaml`) with dedicated system prompts framing a single JSON response; fenced-JSON strip + stub-guard + deterministic keyword/template fallback preserved so the UI still works offline (mirrors the `AIAdapter.analyze()` degradation contract). `builder_router /generate` was already wired through `LLMClient` via `AIAdapter.analyze()` (#6). `ProposalRequest` now accepts the `model` field the UI already sends (forward-compat; not yet spliced into the chat call — `LLMClient` owns model resolution). New tests: `tests/test_automation_skill_routers.py` (10 tests: LLM-available, stub/unparseable/missing-keys fallback, 400 contract, `model`-field acceptance, plus a P3.4 regression guard). Fast suite: 330 passed / 5 skipped / 5 deselected (live-LLM integration tests deselected). Note: the `skill_router.py` half of **P3.4** (dead `SecretVault` import) was also closed here — only `pipeline_router.py` remains.
- [x] **P2.5 Trigger/action endpoint mismatch** — DONE 2026-07-13. Added `POST /api/workflows/trigger` to `workflow_router.py` (not `trigger_router`, to keep the webhook-for-external-provider contract of `/api/triggers/*` separate). Accepts `{template_id, inputs}`, 404s on unknown template, creates a `RUNNING` run via `state_manager.runs.create_run()` and (optionally) binds `inputs.item_id` → `state_manager.bindings.bind_run_to_item()`. Returns `{status, run_id, message}` exactly as `WorkflowManager.tsx:79` expects. New tests in `tests/test_automation_skill_routers.py`: 404 for missing template, run creation for a known template, optional `item_id` binding. Fast suite: 334 passed / 5 skipped / 5 deselected.
- [x] **P2.6 Wire `ibm_bob` provider through the `bob` CLI subprocess** — DONE 2026-07-12. `ibm_bob` is the only provider that isn't an HTTP endpoint; it's reached by shelling out to the local `bob` binary (v1.0.6, `bob --version` confirmed). The `bob` CLI handles its own authentication (first-time browser SSO, cached credentials valid for 24 hours), so no API key is managed by `LLMClient` or the adapter. Verified empirically on v1.0.6 — the original spec's command `["bob","-m",model,"-p",prompt,"--output-format","text"]` was corrected: `-p` is deprecated (use positional in `_chat_bob`/`_test_ibm_bob`), no fabricated default model id (an unrecognized id crashes the binary with "An unexpected critical error occurred: [object Object]"), and `--chat-mode ask` + `--hide-intermediary-output` + `--allowed-mcp-server-names ""` are required for a clean completion (without them `bob` emits MCP-discovery errors on stderr and the full `<thinking>` agentic trace on stdout).
    - **`agents/llm_client.py`** ✅: `_chat_bob()` shells out with the verified flag set; `ibm_bob` removed from `_OPENAI_COMPAT`; no OpenAI client is constructed for it; `-m` only passed when a model is configured (otherwise `bob` uses its own default). Non-zero exit raises `RuntimeError`, which `chat()` degrades to the stub string. Live smoke against the real `bob` binary returned `\nANSWER=42\n\n`, rc 0, empty stderr.
    - **`api/adapters/bob_shell.py`** ✅: `execute()` simplified — dropped `BOB_API_KEY`/vault auth gymnastics (`bob` manages its own auth). Returns the same `{"status","output"|"message"}` shape; `_build_command(prompt, args)` static helper added for testability. `api_key_env` config key kept-but-ignored for backward compatibility. `FileNotFoundError` now reported cleanly.
    - **`api/services/ai_engine_config.py`** ✅: `_list_ibm_bob_models()` returns the statically-configured model id (no `--list-models` in `bob`); `_test_ibm_bob()` is a subprocess smoke (`bob --chat-mode ask --allowed-mcp-server-names "" --hide-intermediary-output -o text -m <id> -p ping`) instead of HTTP `GET /v1/models`; `ibm_bob` removed from both `needs_api_key` membership lists (test_connection + list_available_models).
    - **`tests/`** ✅: `tests/test_llm_client.py` — 4 new tests (no OpenAI client built, verified flag set incl. no deprecated `-p`, `-m` omitted when no model, non-zero exit degrades to stub). `tests/test_adapters.py` — `test_execute_fails_when_no_key` replaced with `test_execute_succeeds_without_api_key` (new no-key contract) + `test_build_command_shape` (verified argv, no key flag). `tests/test_ai_engine_config.py` (new) — 8 tests covering `_test_ibm_bob` (success/failure/missing-binary/timeout), `_list_ibm_bob_models` (static-id, no-key), and the `needs_api_key` exclusion (test_connection + UI list). All 29 P2.6-related tests pass; `test_bob_shell_integration.py` (workflow end-to-end) still green.

### P3 — Debt hygiene (open)
- [x] **P3.1 Learning loop writes `"stub response"`** — DONE 2026-07-13. `agents/memory.py` gained `_is_stub_response()` guard (same `"stub response" in text.lower()` contract used by routers/AIAdapter) on both write-paths: `_analyze_patterns` (periodic loop) and `extract_pattern_from_content` (on-completion promotion). Both return `None`/`False` without appending when the LLM response is a stub or empty. `extract_pattern_from_content` now resolves `PATTERNS_FILE` from the module-level constant (not a parallel local path) so tests can redirect both paths with one monkeypatch. The 17 `stub response` bodies previously polluting `patterns.md` were removed (file reduced from 149 lines to 70, preserving the two real `## Learned on` sections). `tests/test_memory_stub_guard.py` (17 tests) covers `_is_stub_response` parametrization, stub/empty/real on both code paths, and the full `run_learning_loop` write-through. Full suite: 356 passed / 5 skipped. **Follow-up (2026-07-13): centralized stub-detection on `LLMClient.is_stub()` `@staticmethod` — `_is_stub_response` (memory), `automation_router /propose`, `skill_router /brainstorm`, and `AIAdapter.analyze` all call it instead of inlining `"stub response" in raw.lower()`. The stub phrase now lives in one place. Test suite: 358 passed / 5 skipped.
- [ ] **P3.2 Produce one real `execution_report.md`** — of ~26 requirement dirs, no original real backlog idea has been carried past spec (16 stalled at spec-only; 4 reached REVIEW with one-line stub `review.md`; 3 produced a 5-artifact set but stub `execution_report.md`; 1 fixture `E2E-ITEM` reached DONE with no artifacts). Prove one idea end-to-end.
- [ ] **P3.3 Zombie RUNNING runs** — `workflow_runs.json` has 2 `RUNNING` runs open since 2026-05-24 (6 BLOCKED, 1 COMPLETED of 9). Reap/recover on startup.
- [x] **P3.4 Dead SecretVault imports** — DONE 2026-07-13. Removed `from .secret_vault import SecretVault` + `vault = SecretVault(BASE_DIR)` from `pipeline_router.py` (the sole remaining site; `skill_router.py` was already cleaned in P2.4). No more `.vault.key`/`secrets.vault` side-effect at import. Regression guard added in `tests/test_automation_skill_routers.py` (`test_pipeline_router_no_longer_instantiates_secret_vault`, mirrors the existing skill-router guard).
- [x] **P3.5 `brain_api.py` second `FastAPI()`** — DONE 2026-07-13. Removed the dead `app = FastAPI()` / `app.include_router(router)` instance from `brain_api.py` (only `router` is the real export, mounted by `main.py`). `tests/test_observer.py` switched from `from api.brain_api import app` to `from api.main import app` (the main app mounts the same `brain_router` with no prefix); `test_observer.py` passes against `api.main.app`.
- [x] **P3.6 `created_at: "now"` literal** — DONE 2026-07-13. Added `api/managers/_timestamps.py` with `normalize_created_at()` and `sanitize_state()` — dependency-free so both `api/` and `agents/` can import it. Wired into all three pipeline-state loaders: `agents/state.py load_state()`, `KanbanStateManager.load_state()`, and `StateManager.load_state()`. Each reader self-heals non-ISO `created_at` (e.g. `"now"`) on load; the repair is persisted on next save. The 1 surviving `"now"` entry in `pipeline-state.json` was backfilled. `tests/test_timestamp_sanitizer.py` (12 tests): format recognition, repair, idempotency, full-state sanitization, both manager load paths, `create_item` emits ISO, and committed-file backfill guard. Also fixed `test_state_functions.py` isolation (was leaking writes to the live file via `reload()`), `test_workflow_automation.py` isolation (was pointing `StateManager` at the checkout's live file), and `test_api.py` fixture (missing `created_at` tripped sanitize_state's repair in strict equality assertion). Full suite: 370 passed / 5 skipped (1 pre-existing E2E failure remains — see P3.2/P3.8).
- [ ] **P3.7 Empty workflow templates** — `github_pr_release` and `audit_test_tpl` in `workflow_templates.json` have `steps: []`. Either fill or remove.
- [ ] **P3.8 Playwright e2e suite (10 tests across 4 specs)** — last prior run (2026-07-02) had 6 golden-path tests red (pipeline create/filter/drag/reorder/error + deletion). All are API-mocked via `page.route`. Re-run and stabilize. `.last-run.json` is currently absent — needs a fresh run before this item can be marked.

---

## ⏳ Technical Gaps & Pending Tasks

### Automation Studio
- [ ] **UI Placeholders**: Implement "Add Context", "Use Variable", and "Examples" buttons.
- [ ] **Validation**: Add unit/integration tests for new endpoints and UI components.

### General System Gaps
- [ ] **Backend**: Complete implementation of variable handling and context addition.
- [ ] **Stability**: `SESSION_UPDATE.md` is severely stale (last entry 2026-06-06, predating the entire July remediation arc). Either backfill it to reflect P0→P2 or retire it in favor of this document.

---

## 🧪 Verification & Test Strategy

### 1. Unit Tests
- Test individual hooks in isolation.
- Test pure functions and utilities.
- Test component rendering with different props.

### 2. Integration Tests
- Test component interactions.
- Test API integration points.
- Test state management flows.

### 3. UI/Functional Tests
- Test user interactions (drag/drop, clicks, form submissions).
- Test responsive behavior.
- Test accessibility features.

### 4. End-to-End Tests
- Test complete user workflows.
- Test error scenarios.
- Test loading states.

**Current test state (July 2026):**
- Backend pytest fast suite: green (live-LLM integration tests deselected). Run with `pytest` from the venv.
- UI vitest: green, 9/9. Run with `cd ui && npx vitest run`.
- Playwright e2e: **unverified this session** — needs a fresh `npx playwright test` run (see P3.8).

---

## 🤖 AI Agent Protocol
When resolving issues from this document:
1. **Update Documentation**: Update `README.md` and design docs to reflect new behavior. Do not use changelogs; update the descriptions.
2. **Cleanup**: Remove the checklist entry once resolved and verified.
3. **Testing**: Move resolved items to a `Needs Testing` state with exact test commands and expected outputs.
4. **Environment**: Always use the Python virtual environment and `start_antikythera.sh` / `stop_antikythera.sh`.
5. **Verify before writing**: Claims from prior sessions may be stale. Verify a fix is still present in code (or a test still fails) before marking it, and verify before re-opening. Keep this doc accurate over comprehensive.

---

**Last Updated**: 2026-07-13
