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
- [ ] **P3.2 Produce one real `execution_report.md`** — of ~26 requirement dirs, no original real backlog idea has been carried past spec (16 stalled at spec-only; 4 reached REVIEW with one-line stub `review.md`; 3 produced a 5-artifact set but stub `execution_report.md`; 1 fixture `E2E-ITEM` reached DONE with no artifacts). Prove one idea end-to-end. **Scope (2026-07-13):** pick a simple, well-scoped idea already at SPEC stage (e.g. from `automation-ideas/requirements/`), run it manually through Refiner→Architect→Tester→Executor, and verify every artifact is non-stub. Key files: `agents/orchestrator.py` (pipeline driver), `agents/refiner.py`, `agents/architect.py`, `agents/tester.py`, `api/executors/` (execution). The Executor stage is the biggest unknown — may still be stub/mock. Start by tracing `_execute_native` through `integration_hub.py` to see what actually runs.
- [x] **P3.3 Zombie RUNNING runs** — DONE 2026-07-13. Added `RunManager.reap_stale_runs(max_age_seconds=3600, now=None)` (in `api/managers/run_manager.py`) that walks `workflow_runs.json`, finds any run whose `status` is an in-flight value (case-insensitive `running`/`executing`/`active`/`pending` — covers both the workflow-run `RUNNING` convention and the lowercase `executing` leaked by pipeline runs) and whose `started_at` is older than the threshold (an unparseable/missing `started_at` is treated as ancient → stale, safest default), flips it to `FAILED` with `reap_reason: "orphaned: server restart"` and `reaped_at` (ISO-Z), and appends a `RUN_REAPED` timeline event (actor `lifespan`). Existing methods untouched; two helpers added (`get_all_runs()`, module-level `_parse_started_at()`). The lifespan startup in `api/main.py` now calls `get_state_manager().runs.reap_stale_runs()` before starting the scheduler (best-effort, wrapped in try/except so a reap failure never blocks boot) — uses `get_state_manager()` so the autouse `conftest.reset_state_manager` fixture's per-test temp-dir redirect also redirects the reap. New tests in `tests/test_managers.py` `TestRunManager` (8 reap tests: stale RUNNING reaped + audit event, fresh RUNNING preserved, lowercase `executing` reaped, terminal COMPLETED/BLOCKED/FAILED preserved, unparseable/missing `started_at` treated as stale, a realistic mixed set, empty-store no-op, `get_all_runs`) plus `TestLifespanReaping` (1 test entering `TestClient(app)` to assert startup actually flips a planted 2-month-old zombie to FAILED). Fast suite: 378 passed / 5 skipped / 1 (pre-existing, unrelated) e2e failure (`test_e2e_workflow.py::test_full_workflow_lifecycle` — `AIAdapter.analyze` decision mismatch, fails on HEAD before this change too; see P3.2/P3.8). The 5 live zombie runs in `workflow_runs.json` (2 `RUNNING` from 2026-05-24 + 3 `executing` from 2026-07-12) self-heal on the next server boot via this reaper.
- [x] **P3.4 Dead SecretVault imports** — DONE 2026-07-13. Removed `from .secret_vault import SecretVault` + `vault = SecretVault(BASE_DIR)` from `pipeline_router.py` (the sole remaining site; `skill_router.py` was already cleaned in P2.4). No more `.vault.key`/`secrets.vault` side-effect at import. Regression guard added in `tests/test_automation_skill_routers.py` (`test_pipeline_router_no_longer_instantiates_secret_vault`, mirrors the existing skill-router guard).
- [x] **P3.5 `brain_api.py` second `FastAPI()`** — DONE 2026-07-13. Removed the dead `app = FastAPI()` / `app.include_router(router)` instance from `brain_api.py` (only `router` is the real export, mounted by `main.py`). `tests/test_observer.py` switched from `from api.brain_api import app` to `from api.main import app` (the main app mounts the same `brain_router` with no prefix); `test_observer.py` passes against `api.main.app`.
- [x] **P3.6 `created_at: "now"` literal** — DONE 2026-07-13. Added `api/managers/_timestamps.py` with `normalize_created_at()` and `sanitize_state()` — dependency-free so both `api/` and `agents/` can import it. Wired into all three pipeline-state loaders: `agents/state.py load_state()`, `KanbanStateManager.load_state()`, and `StateManager.load_state()`. Each reader self-heals non-ISO `created_at` (e.g. `"now"`) on load; the repair is persisted on next save. The 1 surviving `"now"` entry in `pipeline-state.json` was backfilled. `tests/test_timestamp_sanitizer.py` (12 tests): format recognition, repair, idempotency, full-state sanitization, both manager load paths, `create_item` emits ISO, and committed-file backfill guard. Also fixed `test_state_functions.py` isolation (was leaking writes to the live file via `reload()`), `test_workflow_automation.py` isolation (was pointing `StateManager` at the checkout's live file), and `test_api.py` fixture (missing `created_at` tripped sanitize_state's repair in strict equality assertion). Full suite: 370 passed / 5 skipped (1 pre-existing E2E failure remains — see P3.2/P3.8).
- [x] **P3.7 Empty workflow templates** — DONE 2026-07-13. Filled `github_pr_release` (3 steps: fetch merged PR via GitHub adapter → promote board item to DONE → comment release summary) and `audit_test_tpl` (2 steps: fetch PR context via GitHub adapter → record audit entry comment) with intent-matching step definitions in the `AUTO-MOVE-TEST` step shape (`step_id`/`name`/`category`/`config{adapter,action,description,...}`/`next_step`) that the UI `WorkflowManager.tsx` renders. Both templates are referenced (`github_pr_release` by `api/trigger_router.py:37`; `audit_test_tpl` by 3 manual audit scripts), so deletion was not appropriate. Also fixed a pre-existing trailing comma in `TEST_RECOVERY_01`'s `created_at` that made the entire JSON file invalid — `TemplateManager._load` was silently returning `{}` (caught by `json.load` → `JSONDecodeError`), masking all 7 templates from the engine/routers. Added `test_committed_templates_have_nonempty_steps` regression guard in `tests/test_managers.py::TestTemplateManager` that loads the committed `workflow_templates.json` and asserts no template has `steps: []`. Fast suite: 379 passed / 5 skipped / 1 (pre-existing, P3.2/P3.8 e2e).
- [ ] **P3.8 Playwright e2e suite (10 tests across 4 specs)** — last prior run (2026-07-02) had 6 golden-path tests red (pipeline create/filter/drag/reorder/error + deletion). All are API-mocked via `page.route`. Re-run and stabilize. `.last-run.json` is currently absent — needs a fresh run before this item can be marked. **Scope (2026-07-13):** (a) run `npx playwright test` from project root, capture output; (b) categorize failures: API mock mismatch (route handler returns wrong shape), selector staleness (UI changed since test was written), timing/flakiness, or genuine regressions; (c) fix the API-mock mismatch failures first (usually highest payoff — check `page.route` handlers against current API response shapes); (d) re-run until green or ≤1 known flaky test quarantined. Key files: `tests/e2e/*.spec.ts`, `playwright.config.ts`, `ui/src/components/` (for selector verification).

---

### P4 — Throughput (open)
- [ ] **P4.1 Complexity-tier stage-skip pipeline (GateGuard)** — **DESIGN COMPLETE 2026-07-13; not yet implemented.** The 10-stage waterfall (`PIPELINE_STAGES` at `agents/constants.py:5–16`) forces every item through Refiner→Architect→Tester→Executor regardless of size, which over-engineers trivial ideas ("add a `/health` endpoint" still gets a Mermaid architecture diagram + 5-section test plan) and drives LLM hallucination (the architect invents tech-stack decisions for a single-file utility because the prompt asks for them and the confidence heuristic penalizes missing sections — `agents/refiner.py:59–93` `calculate_confidence`). The agent system prompts already carry "Proportionality"/"Strict Adherence" prose but there is no gating logic that skips stages. This item adds a `complexity` field per item and a `next_stage()` helper so the orchestrator advances through a *tier-specific subset* of stages, defaulting to today's full pipeline. The prior design doc was deleted and re-derived against the live tree; every claim below is verified against the cited `file:line`. **Full design is the final section of this file** — see "P4.1 Design — Complexity-Tier Stage-Skip Pipeline."
  - Note for implementers: the deleted doc had six factual errors (wrong `transition_stage` call count, `VALID_STAGES` mis-attributed to `agents/constants.py`, "PATCH supports arbitrary fields" false, `transition_stage` "always next stage" false, `CreateItemModal.tsx` path off, omitted `CardEditor`); they are all corrected in the design. Re-verify `file:line` anchors at edit time — current as of HEAD 2026-07-13 on `feat/p2.4-route-llm-propose-brainstorm`.

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

## P4.1 Design — Complexity-Tier Stage-Skip Pipeline
*Status: DESIGN 2026-07-13 — see P4.1 ledger entry. Not yet implemented.*

### Problem (ground-truth verified)
- The 10 stages live in `PIPELINE_STAGES` at `agents/constants.py:5–16`. `STAGE_AGENTS` (`22–33`) maps each to an agent (`refiner`/`architect`/`tester`/`executor`) or `None`. `STAGE_HANDLERS` (`36–47`) maps each to a `StageHandler` method.
- `Orchestrator.process_item` (`agents/orchestrator.py:58–65`) reads `item["stage"]` and calls the matching handler. The pipeline has **no notion of complexity** — every item walks every non-review stage.
- Over-engineering + hallucination (problem-statement, above) stem from the architect/tester LLM calls being unconditional. The system prompts (`agents/refiner.py:118–131`, plus `architect.py`/`tester.py`) carry "Proportionality" prose only; nothing gates the call.

### Design: complexity tiers with stage-skip
Retain the 10-stage vocabulary and 10-column board. Introduction of per-item `complexity` controls which stages the orchestrator advances *through*; skipped columns simply stay empty for that item.

| Tier | Stages actually visited | Skips |
|------|--------------------------|-------|
| `trivial` | INTAKE → REFINEMENT → REVIEW_SPEC → EXECUTING → DONE | ARCHITECTURE, REVIEW_ARCH, TESTING, REVIEW_TEST, APPROVED |
| `simple` | INTAKE → REFINEMENT → REVIEW_SPEC → ARCHITECTURE → REVIEW_ARCH → EXECUTING → DONE | TESTING, REVIEW_TEST, APPROVED |
| `complex` (default) | full 10 stages | none — current behavior |

- Review gates are preserved on every review stage the tier *keeps*. Skipped review stages never trip the `get_next_actionable_items` PENDING block (`agents/orchestrator.py:25–40`) because the item is never placed there.

### How complexity is set (precedence)
1. **Human override at create-time** (highest priority): `complexity` in `CreateItemRequest` body. Stored on the item at INTAKE.
2. **Refiner heuristic at REFINEMENT** (only if (1) is absent/`"auto"`): a deterministic keyword/word-count classifier in `agents/refiner.py`. No new LLM call — reuses the spec text already produced.
3. **Default `"complex"`**: if neither sets it → full pipeline (backward-compatible, no migration).

"Human wins, refiner fills gaps, default complex" — exactly one of the three applies.

### Transition logic — `_advance()` on `StageHandler`
Today every handler calls `self.orchestrator.transition_stage(item, "<EXPLICIT_NEXT>", state, item_id)` with a hard-coded target. **There are 14 such calls** in `agents/handlers.py` (the prior doc mis-counted "9"; verified `grep -c transition_stage handlers.py` = 14): line 19 (→REFINEMENT), 46 (→REVIEW_SPEC), 53 (→ARCHITECTURE), 56 (→REFINEMENT, NEEDS_REVISION), 84 (→REVIEW_ARCH), 91 (→TESTING), 94 (→ARCHITECTURE, NEEDS_REVISION), 122 (→REVIEW_TEST), 129 (→APPROVED), 132 (→TESTING, NEEDS_REVISION), 138 (→EXECUTING), 172 (→DONE, INLINE), 202 (→DONE), 204 (→REVIEW_TEST, failure fallback).

`Orchestrator.transition_stage` (`agents/orchestrator.py:42–56`) sets `item["stage"]` + `assigned_agent` and adds history; it accepts **any** string and enforces no ordering. Add a private helper to `StageHandler`:

```python
# agents/handlers.py — new method on StageHandler
def _advance(self, item, state, item_id):
    """Move to the next stage for this item's complexity tier (DONE if none)."""
    current = item.get("stage", "INTAKE")
    nxt = next_stage(current, item.get("complexity"))
    self.orchestrator.transition_stage(item, nxt or "DONE", state, item_id)
```

Replace the **forward** `transition_stage` calls (19, 46, 53, 84, 91, 122, 129, 138) with `self._advance(item, state, item_id)`. **Leave these untouched** — they are not forward progress:
- `56` (REVIEW_SPEC NEEDS_REVISION → REFINEMENT), `94` (REVIEW_ARCH NEEDS_REVISION → ARCHITECTURE), `132` (REVIEW_TEST NEEDS_REVISION → TESTING): intentional backwards loops; `_advance` would re-skip.
- `172` (INLINE success → DONE), `202` (executor success → DONE), `204` (executor failure → REVIEW_TEST): executor outcome logic — handled separately below.

`next_stage(stage, complexity)` (new, in `agents/constants.py`) returns the next stage name for the tier, or `None` for terminal/unknown:

```python
TIER_STAGES = {
    "trivial": ["INTAKE","REFINEMENT","REVIEW_SPEC","EXECUTING","DONE"],
    "simple":  ["INTAKE","REFINEMENT","REVIEW_SPEC","ARCHITECTURE","REVIEW_ARCH","EXECUTING","DONE"],
    "complex":  PIPELINE_STAGES,  # the current 10
}
DEFAULT_COMPLEXITY = "complex"
def next_stage(current, complexity):
    path = TIER_STAGES.get(complexity or DEFAULT_COMPLEXITY, TIER_STAGES[DEFAULT_COMPLEXITY])
    try: return path[path.index(current)+1]
    except (ValueError, IndexError): return None
```

### Refiner — keep `int` return; add `estimate_complexity()` (NO signature change)
**Design decision (corrects prior doc):** the previous design proposed changing `refine_idea()` return from `int` to `tuple[int, str]`. That is a wide-blast change — `.tests/test_refiner.py:18,21,28` assert `isinstance(confidence, int)` / `>= 70`, `tests/test_orchestrator_pipeline.py:71` patches `return_value=85`, and `handlers.py:28` unpacks the int. Instead:

- `refine_idea()` (`agents/refiner.py:96–144`) **keeps returning `int`**. No caller/tour breakage.
- Add a sibling deterministic function:
```python
# agents/refiner.py
COMPLEXITY_KEYWORDS = {"trivial": ["health","ping","rename","typo","one-line","log line"],
                       "simple":  ["endpoint","script","cli","helper","migration"],
                       "complex": ["service","microservice","auth","distributed","migration of","security-critical"]}
def estimate_complexity(spec_content, title="") -> str:
    text = (spec_content + " " + title).lower()
    if len(spec_content) < 400: return "trivial"
    hits = {t: sum(text.count(k) for k in kws) for t,kws in COMPLEXITY_KEYWORDS.items()}
    if hits["trivial"] and not hits["complex"]: return "trivial"
    if hits["simple"] and not hits["complex"]: return "simple"
    return "complex"
```
- In `handle_refinement` (`handlers.py:21–46`), after `confidence = refiner.refine_idea(...)` (line 28), set complexity **only if unset by the human**:
```python
if not item.get("complexity") or item.get("complexity") == "auto":
    from pathlib import Path
    spec = Path(refiner.REQUIREMENTS_DIR, item_id, "spec.md").read_text()
    item["complexity"] = refiner.estimate_complexity(spec, title)
```

### Executor failure/retry path — tier-aware fallback
`handle_executing` (`handlers.py:140–204`) ends:
```python
if confidence > 0:
    self.orchestrator.transition_stage(item, "DONE", state, item_id)      # line 202
else:
    self.orchestrator.transition_stage(item, "REVIEW_TEST", state, item_id)  # line 204
```
Line 204 is unreachable for `trivial`/`simple` (no REVIEW_TEST in tier). Replace line 204's target with a tier-aware value:
```python
else:
    fallback = "REVIEW_TEST" if next_stage("REVIEW_TEST", item.get("complexity")) else "REVIEW_SPEC"
    self.orchestrator.transition_stage(item, fallback, state, item_id)
```
REVIEW_SPEC is the universal gate present in all three tiers; REVIEW_TEST is used only when the tier keeps it. Lines 172/202 (→DONE) stay.

### Manual drag-and-drop bypass — the `POST /api/move` hole (NEW constraint the prior doc missed)
`POST /api/move` (`api/board_router.py:89–98` → `MoveRequest` `api/schemas.py:44–54` → `STATE_MANAGER.update_item`) sets `item["stage"]` to **any** `VALID_STAGES` value the user drags to. It does **not** consult `next_stage()` or the tier. So a user dragging a `trivial` card onto the ARCHITECTURE column would land it in a skipped stage.

Two acceptable policies; (**A recommended**):
- **(A) Allow the manual move but let the next pipeline run self-correct.** On the next `process_item`, the item is at a stage whose handler advances via `_advance()` — `next_stage(current, complexity)` from a skipped stage returns the stage-after-it in the full list if the skipped stage happens to be a prefix, or `None`→DONE if terminal. Simpler: clamp in `MoveRequest.validate_stage` — if `item.complexity` is set and the target isn't in `TIER_STAGES[complexity]`, reject with 422 *unless* the user is also setting `complexity` in the same move. This keeps the invariant without fighting the UI.
- **(B) Do nothing** — treat manual drag as explicit human override ("the user knows best"). Lower safety; a one-correctness-bug risk if a skipped stage's handler then runs an agent.

Decision deferred to implementer; **A** is the conservative choice.

### `VALID_STAGES` duplication (prior doc error #2)
`VALID_STAGES` lives in **`api/constants.py:8–11`** (re-declared), **not** `agents/constants.py`. `api/constants.py` imports nothing from `agents/`. The new `VALID_COMPLEXITIES`/`COMPLEXITY_TIERS` vocabulary therefore needs **parallel definition** — add `VALID_COMPLEXITIES = ["trivial","simple","complex"]` to `api/constants.py` for schema validation, and `TIER_STAGES` + `next_stage` to `agents/constants.py` for orchestration. (Single-source import would be cleaner but is a larger refactor; out of scope here.)

### Touchpoints (11 files — verified paths)
| Layer | File:line | Change |
|-------|-----------|--------|
| Agents/constants | `agents/constants.py` (after line 47) | Add `TIER_STAGES`, `DEFAULT_COMPLEXITY`, `next_stage()` |
| Agents/refiner | `agents/refiner.py` (after line 93, sibling to `calculate_confidence`) | Add `estimate_complexity()`; **do not** change `refine_idea()` signature |
| Agents/handlers | `agents/handlers.py:21–46` | `handle_refinement`: set `item["complexity"]` if unset |
| Agents/handlers | `agents/handlers.py` | Add `_advance()`; replace forward calls at **8 lines**: 19, 46, 53, 84, 91, 122, 129, 138 |
| Agents/handlers | `agents/handlers.py:204` | Tier-aware executor failure fallback |
| API/constants | `api/constants.py:14` area | Add `VALID_COMPLEXITIES` (parallel to `VALID_PRIORITIES`) |
| API/schemas | `api/schemas.py:6–42` (`CreateItemRequest`) + `:67–98` (`UpdateItemRequest`) | Add optional `complexity: Optional[str]` field + `field_validator` against `VALID_COMPLEXITIES` (note: these are **closed Pydantic models** — prior doc's "arbitrary field updates" claim was false; the field MUST be added for `PATCH /api/item/{id}` `model_dump(exclude_unset=True)` at `board_router.py:45` to forward it) |
| API/manager | `api/managers/kanban_state_manager.py:27,33–45` | Add `complexity=None` param to `create_item`; add `"complexity": complexity` to the item dict literal |
| API/router | `api/board_router.py:27–34` | Pass `complexity=item_request.complexity` into `create_item` |
| API/router | `api/board_router.py:90` (`/move`) | **(A)** optional 422 guard if target ∉ `TIER_STAGES[item.complexity]` |
| UI | `ui/src/components/modals/CreateItemModal.tsx` (lines 10–19 state, 141–154 Pri/Source grid) | Add Complexity `<select>` (options Auto/Trivial/Simple/Complex; default Auto); state key `complexity: 'auto'` |
| UI | `ui/src/hooks/usePipelineState.ts:97–106` (POST body) | Add `complexity: itemData.complexity` to the create-item body |
| UI | `ui/src/components/KanbanColumn.tsx:99–113` (`KanbanCardContent` destructures `priority`,`confidence`) | Add a complexity badge (e.g. a small uppercase pill near the priority badge at line 159–172) |
| UI | `ui/src/components/CardEditor.tsx` *(exists; prior doc omitted it)* | Add the same `<select>` so the human can override complexity post-REVIEW_SPEC (the "refiner under-estimates → human overrides" edge case routes here) — verify path at edit time |

### What does NOT change
- `PIPELINE_STAGES`, `STAGE_AGENTS`, `STAGE_HANDLERS` (`agents/constants.py`) — fully intact. The board still renders 10 columns (`KanbanColumn.tsx` `STAGE_CONFIG`).
- `Orchestrator.transition_stage` (`orchestrator.py:42`) — untouched; only the call sites change.
- `Orchestrator.run_pipeline`, `get_next_actionable_items`, the scheduler, retry manager, execution engine, workflow router, trigger router — zero changes.
- Existing items without `complexity` → `"complex"` via the `or DEFAULT_COMPLEXITY` in `next_stage()` and the schema default. No migration.

### Edge cases
| Case | Resolution |
|------|------------|
| Refiner under-estimates (trivial → actually complex) | Human sees classification at REVIEW_SPEC; overrides via `CardEditor.tsx` or drag; `PATCH /api/item/{id}` (now with `complexity` field) stores it. |
| Refiner over-estimates (simple → complex) | Unnecessary stages run (= today's behavior) — harmless; heuristic tunable later. |
| Review-gate approved on a review stage the tier keeps | `_advance()` → next tier stage; skipped review stages are never entered. |
| Review-gate NEEDS_REVISION | Existing backwards loops (lines 56/94/132) are explicitly left on direct `transition_stage` calls — `_advance()` is **not** used for revision routing. |
| Executor failure, `confidence <= 0`, tier lacks REVIEW_TEST | Fall back to `REVIEW_SPEC` (universal). |
| Manual drag to a skipped stage | Policy A guards in `MoveRequest` validator; or policy B lets it self-correct on next run. |
| `complexity: "auto"` persisted from UI | `next_stage` and `estimate_complexity` both treat `"auto"` as unset → refiner fills it at REFINEMENT. |
| Unknown/typo complexity string | `next_stage` falls back to `DEFAULT_COMPLEXITY` (complex); schema validator rejects unknowns at the API boundary. |

### Implementation order
1. `agents/constants.py` — `TIER_STAGES`, `DEFAULT_COMPLEXITY`, `next_stage()`. Pure, unit-testable.
2. `agents/refiner.py` — `estimate_complexity()` (plus `COMPLEXITY_KEYWORDS`). `refine_idea` unchanged.
3. `agents/handlers.py` — `_advance()`; 8 forward call rewrites; `handle_refinement` complexity-set; `handle_executing` fallback fix.
4. `api/constants.py` — `VALID_COMPLEXITIES`.
5. `api/schemas.py` — `complexity` field + validator on both requests.
6. `api/managers/kanban_state_manager.py` + `api/board_router.py` — store on create.
7. *(optional)* `api/schemas.py` `MoveRequest` + `board_router.py:90` — drag guard (policy A).
8. UI: `CreateItemModal.tsx` dropdown → `usePipelineState.ts` body → `KanbanColumn.tsx` badge → `CardEditor.tsx` override.

### Test plan (new `tests/test_complexity_tiers.py` + updates)
- **`next_stage` unit table:** for each `(current, tier)` ∈ cartesian product, assert correct successor; `None` for `DONE`/unknown/terminal; `DEFAULT_COMPLEXITY` fallback for `None`/`""`/`"auto"`/typo complexity.
- **`estimate_complexity` unit:** known-trivial spec (short, health/ping keywords) → `"trivial"`; known-simple → `"simple"`; long multi-service → `"complex"`.
- **`handle_refinement` integration:** human sets `complexity="trivial"` → refiner does NOT overwrite; human omits (`"auto"`/absent) → refiner sets it; both leave `confidence_score` an `int` (guards against the tuple-regression).
- **Pipeline tier traversal:** a `trivial` item never visits ARCHITECTURE/TESTING/APPROVED (assert via `process_item` driving a mock state through REFINEMENT→REVIEW_SPEC approved→EXECUTING→DONE, checking `item["stage"]` history never equals a skipped stage).
- **Executor failure fallback:** `confidence<=0` on a `trivial` item → stage becomes `REVIEW_SPEC`, not `REVIEW_TEST`.
- **Schema/manager:** `POST /api/items` with `complexity:"simple"` persists it; `PATCH` updates it; unknown value → 422.
- **Manual move guard (policy A):** move to a skipped stage → 422 (or 200 if also setting complexity).
- **Regression updates:** `tests/test_refiner.py` — **no change needed** (signature preserved; assert `estimate_complexity` is separate). `tests/test_orchestrator_pipeline.py:71` `return_value=85` patch — **no change** (still an int). Both prior concerns are avoided by the keep-`int` design decision.
- **Command:** `source venv/bin/activate && pytest tests/test_complexity_tiers.py tests/test_refiner.py tests/test_orchestrator_pipeline.py tests/test_api.py tests/test_managers.py -q` → expect green. Run full suite after.

---

**Last Updated**: 2026-07-13
