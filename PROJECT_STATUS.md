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

### P2 — Real LLM behind agents & routers (partial)
- [x] **P2.1/P2.2 Wire real LLM provider** — `LLMClient` resolves provider/model from `AIEngineConfigService` first, falls back to `config.yaml`.
- [x] **P2.3 Wire AIEngineConfigService into agent execution layer** — `LLMClient` extended from 2 to all 8 providers via a single OpenAI-compatible path + Google GenAI path; graceful degradation (missing API keys deferred from init to `chat()`; placeholder `"antikythera-missing-key"` prevents construction failure). `AIAdapter.analyze()` routed through shared `LLMClient.chat()` with JSON parsing + deterministic `_simulate_llm_call` fallback. Fake `sk-antikythera-sim` key removed. Backend tests: 233 passed / 4 deselected / 5 skipped (fast suite excludes live-LLM integration tests).
- [ ] **P2.4 Normalize `automation/skill/builder` routers** — `automation_router /propose` uses regex/keyword matching (no LLM call), `skill_router /brainstorm` returns hardcoded static templates (`"MOCK AI Logic"`), `builder_router /generate` delegates to `AIAdapter.analyze()` which IS already wired through `LLMClient` (#6 above). The first two need to be routed through `LLMClient.chat()` with proper system prompts. **Depends on P2.6** (they need `_chat_bob()` for `ibm_bob` support).
- [ ] **P2.5 Trigger/action endpoint mismatch** — UI `WorkflowManager.tsx:79` calls `/api/workflows/trigger`; trigger_router serves `/api/triggers/webhook/{provider}`. Reconcile (either add the route or fix the UI call).
- [ ] **P2.6 Wire `ibm_bob` provider through the `bob` CLI subprocess** — `ibm_bob` is the only provider that isn't an HTTP endpoint; it's reached by shelling out to the local `bob` binary (v1.0.6, `bob --version` confirmed). The `bob` CLI handles its own authentication (first-time browser SSO, cached credentials valid for 24 hours), so no `BOBSHELL_API_KEY` management is needed by `LLMClient`. The gap: `LLMClient` currently puts `ibm_bob` in the HTTP `else` branch (`OpenAI(api_key, base_url)`), which fails and degrades to the stub string because there's no HTTP endpoint to reach. The fix:
    - **`agents/llm_client.py`**: Add `_chat_bob()` method — `subprocess.run(["bob", "-m", model, "-p", prompt, "--output-format", "text"], timeout=60, check=False)`, where `prompt = system_prompt + "\n\n" + user_prompt`. Route `ibm_bob` provider to it instead of the HTTP branch. Return stdout on success; on non-zero exit or timeout, degrade to the stub string (same graceful degradation as all providers).
    - **`api/adapters/bob_shell.py`**: Simplify `execute()` to match — drop `BOB_API_KEY`/vault auth gymnastics since `bob` manages its own auth. Use the same subprocess pattern: `bob -p prompt`. Keep `BaseAdapter` contract intact; just clean the implementation.
    - **`api/services/ai_engine_config.py`**: For `ibm_bob` provider: (a) `_list_ibm_bob_models()` → return the statically-configured model id directly (the `bob` CLI has no `--list-models` command — confirmed via `bob --help`). (b) `_test_ibm_bob()` → lightweight smoke test: `bob -m <model> -p "ping" --output-format text` instead of HTTP `GET /v1/models`. (c) Remove `ibm_bob` from `needs_api_key` check — no HTTP API key required.
    - **`tests/`**: Add unit test for `_chat_bob()` mocking `subprocess.run`. Add test confirming `BobShellAdapter.execute()` uses correct CLI pattern (no auth-key dependency).

### P3 — Debt hygiene (open)
- [ ] **P3.1 Learning loop writes `"stub response"`** — `automation-ideas/brain/patterns.md` still contains ~17 `## Learned on …` sections whose body is literally `stub response`. The memory loop runs and persists, but the LLM returns nothing real → it learns nothing. Fix `agents/memory.py` to use the shared `LLMClient`.
- [ ] **P3.2 Produce one real `execution_report.md`** — of ~26 requirement dirs, no original real backlog idea has been carried past spec (16 stalled at spec-only; 4 reached REVIEW with one-line stub `review.md`; 3 produced a 5-artifact set but stub `execution_report.md`; 1 fixture `E2E-ITEM` reached DONE with no artifacts). Prove one idea end-to-end.
- [ ] **P3.3 Zombie RUNNING runs** — `workflow_runs.json` has 2 `RUNNING` runs open since 2026-05-24 (6 BLOCKED, 1 COMPLETED of 9). Reap/recover on startup.
- [ ] **P3.4 Dead SecretVault imports** — `pipeline_router.py` and `skill_router.py` still instantiate `SecretVault` at import time (creates `.vault.key`/`secrets.vault` on disk; dead but side-effecting). Remove.
- [ ] **P3.5 `brain_api.py` second `FastAPI()`** — dead app instance at `brain_api.py:~134`. Remove.
- [ ] **P3.6 `created_at: "now"` literal** — `pipeline-state.json` still has 1 item with a string `"now"` instead of an ISO timestamp. Fix the writer + backfill.
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

**Last Updated**: 2026-07-12
