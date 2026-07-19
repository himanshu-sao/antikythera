# 🚩 Project Status: Antikythera

This is the **single master document** for the Antikythera project. It tracks the roadmap, current status, technical gaps, and verification criteria.

## 📊 Current Executive Summary
- **System State**: Cognitive Orchestration System (Hybrid Pipeline + Workflow Engine).
- **Overall Status**: Backend pipeline (Refiner→Architect→Tester) is live and persists artifacts; the July 2026 P0→P2 remediation arc closed the worst runtime defects and wired real LLM providers behind agents/routers. P3 debt hygiene is closed except **P3.2** (produce one real end-to-end idea past spec); the learning `"stub response"` loop is fixed and the Playwright e2e suite is green. Remaining work is throughput (P3.2) and the P2.4/P2.5 backend wiring.
- **Active Focus**: Producing one real end-to-end idea carried past spec and fixing the learning `"stub response"` loop. (Playwright e2e suite now green — see P3.8.)

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
- [ ] **P2.4 Normalize `automation/skill/builder` routers** — `automation_router /propose` uses regex/keyword matching (no LLM call), `skill_router /brainstorm` returns hardcoded static templates (`"MOCK AI Logic"`), `builder_router /generate` delegates to `AIAdapter.analyze()` which IS already wired through `LLMClient` (#6 above). The first two need to be routed through `LLMClient.chat()` with proper system prompts. ~~**Depends on P2.6**~~ (P2.6 now DONE — `_chat_bob()` is available, so this is unblocked).
- [ ] **P2.5 Trigger/action endpoint mismatch** — UI `WorkflowManager.tsx:79` calls `/api/workflows/trigger`; trigger_router serves `/api/triggers/webhook/{provider}`. Reconcile (either add the route or fix the UI call).
- [x] **P2.6 Wire `ibm_bob` provider through the `bob` CLI subprocess** — DONE 2026-07-12. `ibm_bob` is the only provider that isn't an HTTP endpoint; it's reached by shelling out to the local `bob` binary (v1.0.6, `bob --version` confirmed). The `bob` CLI handles its own authentication (first-time browser SSO, cached credentials valid for 24 hours), so no API key is managed by `LLMClient` or the adapter. Verified empirically on v1.0.6 — the original spec's command `["bob","-m",model,"-p",prompt,"--output-format","text"]` was corrected: `-p` is deprecated (use positional in `_chat_bob`/`_test_ibm_bob`), no fabricated default model id (an unrecognized id crashes the binary with "An unexpected critical error occurred: [object Object]"), and `--chat-mode ask` + `--hide-intermediary-output` + `--allowed-mcp-server-names ""` are required for a clean completion (without them `bob` emits MCP-discovery errors on stderr and the full `<thinking>` agentic trace on stdout).
    - **`agents/llm_client.py`** ✅: `_chat_bob()` shells out with the verified flag set; `ibm_bob` removed from `_OPENAI_COMPAT`; no OpenAI client is constructed for it; `-m` only passed when a model is configured (otherwise `bob` uses its own default). Non-zero exit raises `RuntimeError`, which `chat()` degrades to the stub string. Live smoke against the real `bob` binary returned `\nANSWER=42\n\n`, rc 0, empty stderr.
    - **`api/adapters/bob_shell.py`** ✅: `execute()` simplified — dropped `BOB_API_KEY`/vault auth gymnastics (`bob` manages its own auth). Returns the same `{"status","output"|"message"}` shape; `_build_command(prompt, args)` static helper added for testability. `api_key_env` config key kept-but-ignored for backward compatibility. `FileNotFoundError` now reported cleanly.
    - **`api/services/ai_engine_config.py`** ✅: `_list_ibm_bob_models()` returns the statically-configured model id (no `--list-models` in `bob`); `_test_ibm_bob()` is a subprocess smoke (`bob --chat-mode ask --allowed-mcp-server-names "" --hide-intermediary-output -o text -m <id> -p ping`) instead of HTTP `GET /v1/models`; `ibm_bob` removed from both `needs_api_key` membership lists (test_connection + list_available_models).
    - **`tests/`** ✅: `tests/test_llm_client.py` — 4 new tests (no OpenAI client built, verified flag set incl. no deprecated `-p`, `-m` omitted when no model, non-zero exit degrades to stub). `tests/test_adapters.py` — `test_execute_fails_when_no_key` replaced with `test_execute_succeeds_without_api_key` (new no-key contract) + `test_build_command_shape` (verified argv, no key flag). `tests/test_ai_engine_config.py` (new) — 8 tests covering `_test_ibm_bob` (success/failure/missing-binary/timeout), `_list_ibm_bob_models` (static-id, no-key), and the `needs_api_key` exclusion (test_connection + UI list). All 29 P2.6-related tests pass; `test_bob_shell_integration.py` (workflow end-to-end) still green.

### P3 — Debt hygiene (P3.1, P3.3-P3.8 closed; P3.2 open)
- [x] **P3.1 Learning loop writes `"stub response"`** — DONE prior to 2026-07-18. `agents/memory.py:6,20` now imports and constructs the shared `LLMClient`; `automation-ideas/brain/patterns.md` has **0** `stub response` bodies — post-2026-07-12 "Learned on" sections contain real structured patterns (Sequential Pipeline, Confidence Scoring, File Organization, etc.). Verified 2026-07-19.
- [ ] **P3.2 Produce one real `execution_report.md`** — of ~26 requirement dirs, no original real backlog idea has been carried past spec (16 stalled at spec-only; 4 reached REVIEW with one-line stub `review.md`; 3 produced a 5-artifact set but stub `execution_report.md`; 1 fixture `E2E-ITEM` reached DONE with no artifacts). Prove one idea end-to-end. ← **the remaining real-work item in P3.**
- [x] **P3.3 Zombie RUNNING runs** — DONE prior to 2026-07-18. `workflow_runs.json` (now a dict keyed by run-id) has **0 RUNNING** statuses: `{BLOCKED:5, COMPLETED:1, FAILED:6}`. Verified 2026-07-19.
- [x] **P3.4 Dead SecretVault imports** — DONE 2026-07-19. Removed `from .secret_vault import SecretVault` + `vault = SecretVault(BASE_DIR)` from `api/pipeline_router.py` and `api/skill_router.py` (the `vault` symbol was unreferenced; `BASE_DIR`/`os.makedirs` retained to keep creating the `automation-ideas/` data dir). `secret_vault.py` itself is left in place — its own tests still pass. Stray `.vault.key`/`secrets.vault` files are no longer recreated on router import. Verified: `tests/test_observer.py`, `test_secret_vault.py`, `test_orchestrator_pipeline.py`, `test_skill_reuse.py`, `test_integration_status.py` — 14 passed.
- [x] **P3.5 `brain_api.py` second `FastAPI()`** — DONE 2026-07-19. Removed the dead `from fastapi import FastAPI` + `app = FastAPI()` + `app.include_router(router)` block at the end of `api/brain_api.py` (never imported/run — `api/main.py:37` imports only `router`). Updated `tests/test_observer.py`, which had imported that dead `app`, to build a test-local `FastAPI()` mounting the brain router (standard single-router isolation pattern). `test_observer.py` passes.
- [x] **P3.6 `created_at: "now"` literal** — DONE prior to 2026-07-18. `grep '"now"'` in `automation-ideas/pipeline-state.json` returns 0 — no string `"now"` literals remain (write path now emits ISO timestamps). Verified 2026-07-19.
- [x] **P3.7 Empty workflow templates** — DONE prior to 2026-07-18. `workflow_templates.json` has **no empty-step templates** — `github_pr_release` → 3 steps, `audit_test_tpl` → 2 steps (all templates ≥1 step). Verified 2026-07-19.
- [x] **P3.8 Playwright e2e suite (10 tests across 4 specs)** — DONE 2026-07-18, all 10 green (`npx playwright test` from repo root; `test-results/.last-run.json` → `passed`). Two layered root causes were fixed: (1) **App wiring** — `handleDragEnd` in `ui/src/App.tsx` routed every drag to `handleMoveItem` (→`/api/move`); the `handleReorder` hook (→`POST /api/items/reorder`) was implemented in `usePipelineState.ts` but never destructured in `App.tsx`, so intra-column reorders never persisted. Same-stage drops now route to `handleReorder`, cross-stage to `handleMoveItem`; `closestCorners` collision detection added to the `DndContext` (default `rectIntersection` is unreliable across per-column `SortableContext`s). (2) **dnd-kit + Playwright** — `locator.dragTo()` issues a single bounding-box hop that doesn't satisfy `PointerSensor`'s `activationConstraint:{distance:5}`, so `onDragEnd` never fired; added `PipelinePage.dragCardOnto()` (manual `mouse.move→down→stepped moves→up`) and switched the reorder test to it. The board filter bar, "How it works" workflow-guide affordance, Error+Retry state, and per-card Delete button were also restored — all required by the golden-path specs. Branch: `feat/p3.8.4-restore-pipeline-filters`. (`ui/test-results/` + `ui/playwright-report/` are now in `.gitignore`, commit `ef5eaee`.)

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
- Playwright e2e: **green, 10/10** (2026-07-18). Run `npx playwright test` from the repo root (Playwright lives at repo root, not under `ui/`) with the Vite dev server on `:5173`. See P3.8.

---

## 🤖 AI Agent Protocol
When resolving issues from this document:
1. **Update Documentation**: Update `README.md` and design docs to reflect new behavior. Do not use changelogs; update the descriptions.
2. **Cleanup**: Remove the checklist entry once resolved and verified.
3. **Testing**: Move resolved items to a `Needs Testing` state with exact test commands and expected outputs.
4. **Environment**: Always use the Python virtual environment and `start_antikythera.sh` / `stop_antikythera.sh`.
5. **Verify before writing**: Claims from prior sessions may be stale. Verify a fix is still present in code (or a test still fails) before marking it, and verify before re-opening. Keep this doc accurate over comprehensive.

---

**Last Updated**: 2026-07-19
