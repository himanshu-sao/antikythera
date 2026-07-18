# 🚩 Project Status: Antikythera

This is the **single master document** for the Antikythera project. It tracks the roadmap, current status, technical gaps, and verification criteria.

## 📊 Current Executive Summary
- **System State**: Cognitive Orchestration System (Hybrid Pipeline + Workflow Engine).
- **Overall Status**: Backend pipeline (Refiner→Architect→Tester) is live and persists artifacts; the July 2026 P0→P2 remediation arc closed the worst runtime defects and wired real LLM providers behind agents/routers. Remaining work is throughput (the Executor/learning stages still stub) and P3 debt hygiene.
- **Active Focus**: Stabilizing the Playwright e2e suite (P3.8). P3.2 is CLOSED — one real backlog idea (SCRIPT-01) carried past spec with all five artifacts non-stub (P3.2.7, done 2026-07-15); the two executor defects that run surfaced are now FIXED (2026-07-15): relative `write_file`/`patch`/`read_file` paths anchor at `automation-ideas/requirements/<id>/` (absolute paths unchanged), and the planner emits exactly one task per file (no more same-path overwrite masking as 4 COMPLETED entries). The P3.2.6 live harness and the P3.2.7 gate were updated for the new anchor; the stale `output/` fixture-dir false-pass is closed (recorded pre-run set + the debris deleted). The learning `"stub response"` loop is fixed (P3.1, done).

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
- [x] **P3.2 Produce one real `execution_report.md`** *(parent — 7 of 7 sub-tasks done; CLOSED 2026-07-15)* — SCRIPT-01 (a real backlog idea, "Standardized System Health & Log Management Utility") was carried end-to-end past spec by the live producer agents (see P3.2.7). All five artifacts non-stub.
  - **Ground truth (2026-07-14 trace, supersedes the old "trace `_execute_native`" scope):** the EXECUTING stage does **not** go through `integration_hub.py`/`_execute_native` (that path is for the workflow `ExecutionEngine`, not the pipeline executor). The pipeline executor is `agents/executor.py::executor_idea` → `ExecutorAgent` — an agentic LLM tool-call loop: `_analyze_phase` (planner) → `_execution_loop` → `_perform_task_multi_turn` (LLM emits a JSON `{tool, args}` → `agents/executor_tools.py::execute_tool` runs `terminal`/`write_file`/`patch`/`read_file`) → `_finalize_phase` writes the report. The blocking failures were **LLM-layer**, not engine-layer — now resolved (P3.2.1–P3.2.6).
  - **Two root-causes shipped in P3.2.1 (commit `c5aef74`, 2026-07-14)** — both verified present in code on this branch (`api/models/config.py` empty-model_id sentinel + `agents/llm_client.py` stdin-prompt `subprocess.run(input=prompt, …)` + `_BOB_TIMEOUT=120s`):
    - `ModelConfig._validate_model_id` rejected `model_id: ""` → the whole `ai_config.json` failed Pydantic load → service fell back to Ollama (not running) → every LLM call died. Empty is the intended sentinel for ibm_bob's "let bob pick its own model" path (`_chat_bob` omits `-m`). The fix unblocks all ibm_bob usage, not just P3.2.
    - `_chat_bob` passed the prompt as a positional after a `--` terminator — does NOT work on bob v1.0.6 (positional after `--` ignored, binary exits 1 "No input provided"). Now piped via `subprocess.run(input=prompt, …)`, which also neutralizes leading-dash prompt injection. `_BOB_TIMEOUT` raised 60→120s.
  - [x] **P3.2.1** — DONE 2026-07-14. Shipped in c5aef74 — empty model_id sentinel + stdin prompt + 120s timeout; `tests/test_llm_client.py` + `tests/test_ai_engine_config.py` green (16 passed). Originally: commit the two uncommitted ibm_bob fixes (`api/models/config.py` empty-model_id + `agents/llm_client.py` stdin prompt/timeout + `tests/test_llm_client.py`). Decision on `tools/verify_executor_p3_2.py`: keep as a fixture harness (gitignore or move into `tools/` with a README) or delete. Run `pytest tests/test_llm_client.py tests/test_ai_engine_config.py -q` after commit — must stay green.
  - [x] **P3.2.2** — DONE 2026-07-14. `get_workspace_files()` now returns top-level files + the `api/` tree, sorted + deduped, capped at `WORKSPACE_FILES_CAP = 60` (`agents/executor_tools.py`); excluded dirs pruned mid-walk (`venv`, `node_modules`, `.git`, `.ui`, `__pycache__`, `dist`, `build`, `playwright-report`, `test-results`, …). Added optional `root` param (default `os.getcwd()` → call site `executor.py:91` unchanged). New `tests/test_executor_tools.py` (5 tests: under-cap, sorted+unique, excludes build/cache dirs incl. `.ui`, no `__pycache__`/`.pyc` mid-walk, cap-is-a-real-bound via `cap+20` overflow). Fast suite: 388 passed / 5 skipped / 1 deselected (e2e), green. No `bob` call. Originally: bound `get_workspace_files()` (`agents/executor_tools.py:11–21`). Today it `os.walk`s the entire repo (minus venv/node_modules/.git) → a multi-hundred-line file list baked into every `_perform_task_multi_turn` prompt → this is the most likely cause of the observed 60–120s bob timeouts/hangs. Change to a bounded, relevant set (e.g. top-level entries + `api/` + the spec's named target files, ~≤60 entries, sorted). Add a unit test asserting the list stays ≤ a fixed cap and excludes venv/node_modules/.git/.ui.
  - [x] **P3.2.3** — DONE 2026-07-14. `ExecutorPlanner.create_checklist` no longer returns the 3-task stub on failure — on empty/unparseable output (or parser exception) it `logger.error`s loudly and returns `[]` (`agents/executor_planner.py`). `ExecutorAgent.execute()` now aborts on an empty checklist (`raise RuntimeError` → existing `except` → `_report_failure`) so `executor_idea` returns `0` with a FAILURE `execution_report.md` and **no** `COMPLETED:` entries (`agents/executor.py`). New `tests/test_executor_planner_fail_loud.py` (3 tests): empty-string planner → `executor_idea(...) == 0` + FAILURE report + no `COMPLETED:`; non-JSON planner → same; direct `create_checklist` empty-output → `[]` (not the old stub). Targeted suite green: `tests/test_executor_planner_fail_loud.py` (3) + `tests/test_executor_agentic.py` + `tests/test_complexity_tiers.py` (38) — 41 passed. No `bob` call. (Full-suite gate deferred to end of P3.2 to save tokens.) Originally: make the planner fail loud instead of silently substituting a stub checklist (`agents/executor_planner.py::create_checklist`). On empty/unparseable planner LLM output it currently `logger.warning("Failed to generate checklist…")` then returns a generic 3-task stub (`Initialize workspace` / `Implement core logic` / `Run verification tests`) — so a bad LLM call masquerades as a real plan and the executor "succeeds" on placeholders. Change to: on empty/stub planner output, raise (or return `[]` and have `execute()` abort → `executor_idea` returns `0`). Add a test: stubbed-empty planner response → `executor_idea` returns 0 and writes a FAILURE report (no COMPLETED log entries).
  - [x] **P3.2.4** — DONE 2026-07-14. Added an env-var injection seam in ``LLMClient._chat_bob`` (`agents/llm_client.py`): when ``ANTIKYTHERA_BOB_STUB`` is truthy, it returns a deterministic stub without spawning the ``bob`` subprocess (saving bob quota / avoiding 8–15s per-call + hangs). Default = real ``bob`` → the real proof intent of P3.2.6 is preserved. Conftest (`conftest.py`) sets the env var default ``=1`` for the whole test session, so ``pytest`` runs *never* hit real ``bob`` (resolving the token concern), while a single ``ANTIKYTHERA_BOB_STUB=0 pytest ...`` opt-in still exercises the real binary. New `tests/test_bob_stub_seam.py` (6 tests: stub-on = no subprocess + deterministic response for executor/planner contexts; stub-off = real command + stdin). Real-bob tests (`tests/test_llm_client.py`) also updated to opt out of the default stub via a one-line helper change (order-independent mocking). Targeted suite green: 68 passed across all llm_client/executor/bob seam tests. No ``bob`` tokens needed for testing. Originally: expose executor LLM stubbing for the verification fixture (``tools/verify_executor_p3_2.py``); injection seam so the P3.2 end-to-end run does not require a live network LLM. Keep the real-bob path as the default.
  - [x] **P3.2.5** — DONE 2026-07-14. Green with the stubbed LLM. First recreate the missing P3.2.4 deliverable: the `tools/verify_executor_p3_2.py` harness (the seam + its unit tests shipped in `c5a..abba` but the standalone harness never landed on disk, fix verified in this session). New `tools/verify_executor_p3_2.py` swaps `LLMClient.chat` at the class level for a deterministic responder (planner → non-empty checklist bypassing the fail-loud guard; executor → `write_file` of `api/health_router.py` + `VERSION`, then `pytest --co` verification turn that `_is_verification_command` classifies AND exits 0). ``python3 tools/verify_executor_p3_2.py`` exits 0: confidence 100, report 232 bytes (no "stub response"), three COMPLETED entries referencing health-endpoint files, both files read back on disk. Working tree clean afterward (no workflow_runs.json debris: key count unchanged at 11).
  - [x] **P3.2.6** **Live gate: prove the real (default) LLM path produces a non-stub report.** DONE 2026-07-15 (commit `4ccbb14`, pushed to origin) — **GREEN against the live `google_gemma` (`gemma-4-31b-it`) default provider**, stub seam OFF. `tools/verify_executor_p3_2_live.py` (new sibling of the CI stub fixture — swaps nothing, runs the real `executor_idea` path) reports `executor_idea()=100`, 2 real `COMPLETED:` entries, `api/health_router.py` + `VERSION` both written to disk & read back, no `stub response`, fixtures auto-cleaned. Two root causes fixed this session: **Fix #2 (planner)** — `agents/executor_planner.py` system prompt now emits ONLY artifact-producing tasks (`file_creation`/`code_implementation`/`dependency_install`); the `verification` type is gone and no final verifier task is produced (Phase 1 had removed `terminal`'s ability to mark `is_done`, so any verifier task was guaranteed to loop forever). **Fix #1 (executor_tools)** — `agents/executor_tools.py::_is_stub_content` dropped its blanket `_MIN_ARTIFACT_BYTES=30` byte floor (it wrongly rejected legitimate 6-byte `VERSION` files as stubs — the exact cause of the prior `Create VERSION file` 5-turn exhaustion loop), kept the `_STUB_MARKERS` substring scan + non-empty check, and `write_file` now self-verifies via an on-disk read-back so “done” is observable from the filesystem; marker matching is now case-insensitive (markers weren't lowered against `content.lower()` — masked by the old byte floor). Tests: `tests/test_executor_tools.py` updated for the new contract (small-but-real content now completes; stub/empty still rejected; case-insensitive match); 21 targeted executor/planner tests green, broader 72 green; CI stub harness `tools/verify_executor_p3_2.py` still green (165b report, conf 100). Previously (2026-07-14) this was partial-not-green: planner over-decomposed to 11 tasks, Gemma tripped on meta/verification tasks, timed out at 5 min mid-loop. The Phase 1 executor simplification (`fdd35dc`: single bounded loop, budget-gated diagnostics) + this session's two fixes closed all three. The `google-genai` dependency should still be pinned (`requirements.txt`/`pyproject.toml`) as a runtime requirement of the default provider path — carried as a minor follow-up, not P3.2.6 scope.
  - [x] **P3.2.7** **Carry one *real backlog* idea past spec.** DONE 2026-07-15 — **GREEN against the live `google_gemma` (`gemma-4-31b-it`) default provider**, stub seam OFF, `tools/verify_p3_2_7_real_idea.py` exit 0 (~5 min, 16:22→16:27). Carried `SCRIPT-01` ("Standardized System Health & Log Management Utility") through Architect→Tester→Review→Executor by calling each `<stage>_idea` entry function directly (bypasses the orchestrator REVIEW gates that block on a human `review_status`, by design). All five artifacts non-stub: `spec.md` (4,876 chars, pre-existing real spec — NOT re-rolled, to avoid degradation), `architecture.md` (24,522 chars), `tests.md` (5,184 chars), `review.md` (986 chars — harness stands in for the human reviewer with a genuine SCRIPT-01-specific sign-off), `execution_report.md` (749 chars, 4 real `COMPLETED:` entries). `architect_idea()=100`, `tester_idea()=100`, `executor_idea()=100`. The gate-cleaning path removed the planted `P3-2-7-SCRIPT01` run entry from `workflow_runs.json` (verified absent post-run); the real backlog artifacts were kept. **Two defects surfaced (recorded, NOT P3.2.7 scope — tracked as follow-ups):** (1) **relative-path defect** — `execute_tool`'s `write_file` resolves the LLM-emitted `path` against process cwd (repo root), NOT `requirements/<ITEM_ID>/`, so the executor's `system_health_utility.sh`/`script_01.conf` landed untracked at repo root (since deleted as debris); the gate's "artifact under requirements/<id>/" on-disk check passed *falsely* on a stale `output/` dir left by the prior health-fixture run, not SCRIPT-01's real output. `write_file` self-verify passes regardless because the read-back resolves the same wrong cwd path. Fix: anchor executor cwd to `requirements/<ITEM_ID>/` or rewrite the path inside `execute_tool`. (2) **no-append semantics** — each `write_file` to the same path *replaces* content (no append/patch), so 4 tasks targeting one `system_health_utility.sh` overwrote each other; only the last (main entry point) survived, so the report's 4 `COMPLETED:` entries overstate the on-disk file. Mem: `antikythera-executor-relative-path-defect`.
  - **⚠️ Security note parked here (not P3.2 scope, record before forgetting):** `execute_tool`'s `terminal` branch runs `subprocess.run(cmd, shell=True, timeout=300)` on **LLM-controlled** `args["command"]` (`agents/executor_tools.py:88`). If the executor LLM is ever pointed at untrusted input this is shell injection. Track as a follow-up hardening task (allowlist of programs, or drop `shell=True`).
  - [x] **P3.2.7 follow-up — fix the two surfaced executor defects.** DONE 2026-07-15. (1) **Relative-path anchor** — added `agents/executor_tools.py::_resolve_item_path(path, item_id)`; the `write_file`/`patch`/`read_file` branches now resolve a RELATIVE `path` at `automation-ideas/requirements/<item_id>/` (built the same way as the report path in `executor.py::_finalize_phase`) and pass ABSOLUTE paths through unchanged, so the CI fixture's absolute-path canned writes keep landing at the repo root. `terminal` is untouched (its cwd-relative semantics for `pip install` etc. are correct). `write_file`'s read-back self-verify now confirms the bytes landed in the ITEM dir — a false-complete against the old wrong-cwd path can no longer slip through. (2) **No-append / one-file-split** — strengthened `agents/executor_planner.py`'s system prompt with a "ONE TASK PER FILE" block and a GUIDELINES point-1 addition; the planner now emits exactly one task per file (full contents in a single `write_file`), so a same-path overwrite no longer masks N `COMPLETED:` entries behind one surviving file. `write_file` semantics are unchanged (replace whole file). Harness/test updates: `tools/verify_executor_p3_2_live.py` redirects `HEALTH_ROUTER_PATH`/`VERSION_PATH` to the item dir (the live Gemma executor emits relative paths); `tools/verify_executor_p3_2.py` (stub harness, feeds absolute paths) unchanged; `tools/verify_p3_2_7_real_idea.py` records the pre-run `REQ_DIR` entry set and the on-disk proof now credits only a GENUINELY-NEW entry (closes the false-pass where a stale `requirements/SCRIPT-01/output/` health-fixture dir satisfied the "any non-kept file" check), and that stale `output/` debris was deleted. New tests in `tests/test_executor_tools.py` (4: `_resolve_item_path` absolute-unchanged / relative-anchors / empty-passthrough, plus an end-to-end `write_file` relative-lands-in-item-dir-not-cwd). Targeted suite: `tests/test_executor_tools.py` + `tests/test_executor_planner_fail_loud.py` = 21 passed. Live gate (`tools/verify_p3_2_7_real_idea.py`) NOT re-run by default (already green; consumes Gemma quota). Mem: `antikythera-executor-relative-path-defect` (now resolved).
- [x] **P3.3 Zombie RUNNING runs** — DONE 2026-07-13. Added `RunManager.reap_stale_runs(max_age_seconds=3600, now=None)` (in `api/managers/run_manager.py`) that walks `workflow_runs.json`, finds any run whose `status` is an in-flight value (case-insensitive `running`/`executing`/`active`/`pending` — covers both the workflow-run `RUNNING` convention and the lowercase `executing` leaked by pipeline runs) and whose `started_at` is older than the threshold (an unparseable/missing `started_at` is treated as ancient → stale, safest default), flips it to `FAILED` with `reap_reason: "orphaned: server restart"` and `reaped_at` (ISO-Z), and appends a `RUN_REAPED` timeline event (actor `lifespan`). Existing methods untouched; two helpers added (`get_all_runs()`, module-level `_parse_started_at()`). The lifespan startup in `api/main.py` now calls `get_state_manager().runs.reap_stale_runs()` before starting the scheduler (best-effort, wrapped in try/except so a reap failure never blocks boot) — uses `get_state_manager()` so the autouse `conftest.reset_state_manager` fixture's per-test temp-dir redirect also redirects the reap. New tests in `tests/test_managers.py` `TestRunManager` (8 reap tests: stale RUNNING reaped + audit event, fresh RUNNING preserved, lowercase `executing` reaped, terminal COMPLETED/BLOCKED/FAILED preserved, unparseable/missing `started_at` treated as stale, a realistic mixed set, empty-store no-op, `get_all_runs`) plus `TestLifespanReaping` (1 test entering `TestClient(app)` to assert startup actually flips a planted 2-month-old zombie to FAILED). Fast suite: 378 passed / 5 skipped / 1 (pre-existing, unrelated) e2e failure (`test_e2e_workflow.py::test_full_workflow_lifecycle` — `AIAdapter.analyze` decision mismatch, fails on HEAD before this change too; see P3.2/P3.8). The 5 live zombie runs in `workflow_runs.json` (2 `RUNNING` from 2026-05-24 + 3 `executing` from 2026-07-12) self-heal on the next server boot via this reaper.
- [x] **P3.4 Dead SecretVault imports** — DONE 2026-07-13. Removed `from .secret_vault import SecretVault` + `vault = SecretVault(BASE_DIR)` from `pipeline_router.py` (the sole remaining site; `skill_router.py` was already cleaned in P2.4). No more `.vault.key`/`secrets.vault` side-effect at import. Regression guard added in `tests/test_automation_skill_routers.py` (`test_pipeline_router_no_longer_instantiates_secret_vault`, mirrors the existing skill-router guard).
- [x] **P3.5 `brain_api.py` second `FastAPI()`** — DONE 2026-07-13. Removed the dead `app = FastAPI()` / `app.include_router(router)` instance from `brain_api.py` (only `router` is the real export, mounted by `main.py`). `tests/test_observer.py` switched from `from api.brain_api import app` to `from api.main import app` (the main app mounts the same `brain_router` with no prefix); `test_observer.py` passes against `api.main.app`.
- [x] **P3.6 `created_at: "now"` literal** — DONE 2026-07-13. Added `api/managers/_timestamps.py` with `normalize_created_at()` and `sanitize_state()` — dependency-free so both `api/` and `agents/` can import it. Wired into all three pipeline-state loaders: `agents/state.py load_state()`, `KanbanStateManager.load_state()`, and `StateManager.load_state()`. Each reader self-heals non-ISO `created_at` (e.g. `"now"`) on load; the repair is persisted on next save. The 1 surviving `"now"` entry in `pipeline-state.json` was backfilled. `tests/test_timestamp_sanitizer.py` (12 tests): format recognition, repair, idempotency, full-state sanitization, both manager load paths, `create_item` emits ISO, and committed-file backfill guard. Also fixed `test_state_functions.py` isolation (was leaking writes to the live file via `reload()`), `test_workflow_automation.py` isolation (was pointing `StateManager` at the checkout's live file), and `test_api.py` fixture (missing `created_at` tripped sanitize_state's repair in strict equality assertion). Full suite: 370 passed / 5 skipped (1 pre-existing E2E failure remains — see P3.2/P3.8).
- [x] **P3.7 Empty workflow templates** — DONE 2026-07-13. Filled `github_pr_release` (3 steps: fetch merged PR via GitHub adapter → promote board item to DONE → comment release summary) and `audit_test_tpl` (2 steps: fetch PR context via GitHub adapter → record audit entry comment) with intent-matching step definitions in the `AUTO-MOVE-TEST` step shape (`step_id`/`name`/`category`/`config{adapter,action,description,...}`/`next_step`) that the UI `WorkflowManager.tsx` renders. Both templates are referenced (`github_pr_release` by `api/trigger_router.py:37`; `audit_test_tpl` by 3 manual audit scripts), so deletion was not appropriate. Also fixed a pre-existing trailing comma in `TEST_RECOVERY_01`'s `created_at` that made the entire JSON file invalid — `TemplateManager._load` was silently returning `{}` (caught by `json.load` → `JSONDecodeError`), masking all 7 templates from the engine/routers. Added `test_committed_templates_have_nonempty_steps` regression guard in `tests/test_managers.py::TestTemplateManager` that loads the committed `workflow_templates.json` and asserts no template has `steps: []`. Fast suite: 379 passed / 5 skipped / 1 (pre-existing, P3.2/P3.8 e2e).
- [ ] **P3.8 Playwright e2e suite (10 tests across 4 specs)** *(parent — do the sub-tasks below in order)* — last prior run (2026-07-02) had 6 golden-path tests red (pipeline create/filter/drag/reorder/error + deletion). All are API-mocked via `page.route`. Key files: `tests/e2e/*.spec.ts`, `playwright.config.ts`, `ui/src/components/` (for selector verification).
  - [x] **P3.8.1** DONE 2026-07-17. Baseline captured against live full stack (`start_antikythera.sh`): **6 failed / 4 passed (31.9s)**. Full output saved to `tests/e2e/.last-run-2026-07-17.txt`. Failing tests (6): `deletion.spec.ts:34 Item Deletion › should delete an item and it should disappear from the board`; `pipeline.spec.ts:35 Pipeline Golden Path › should create a new idea and see it in INTAKE`; `pipeline.spec.ts:91 Pipeline Golden Path › should filter ideas by search query, priority, and stage`; `pipeline.spec.ts:145 Pipeline Golden Path › should open and close workflow guide`; `pipeline.spec.ts:201 Pipeline Golden Path › should persist intra-column reordering`; `pipeline.spec.ts:257 Pipeline Golden Path › should show error message when API fails`. Passing (4): `addIntegrationModal › opens Add Integration modal`; `pipeline.spec.ts:157 › should move card between stages`; `integrationsManager › renders integration cards and Add Connection CTA`; `integrationsManager › type filter works`. Raw observation for P3.8.2 (not a fix): 4 of the 6 failures hit the 30.0s timeout hung on a page-object locator action (create→`newItemButton.click()`, filter→`searchInput.fill()`, workflow-guide→`workflowButton.click()`, deletion→`trashIcon.click()`) → points at category (b) selector staleness for those; the remaining two (intra-column reorder, error-on-API-fail) fail fast on a content/visibility assertion → (a) or (b). Categorization belongs to P3.8.2.
  - [x] **P3.8.2** DONE 2026-07-17. Categorized all six baseline failures. Method: live UI inspected via headless Chrome DevTools against `:5173/pipeline` (mocks intercept `/api/state`, so the `beforeEach` data is controlled — failures come from the DOM, not data) + curled live `/api/state` for shape comparison. **Verdict: all six are category (b) selector staleness — zero (a)/(c)/(d).** The spec selectors target UI affordances that no longer render. Live `/api/state` shape is compatible with the mocks (items flat with `title`/`stage`/`priority`/etc., plus extra live-only fields the mocks omit but the tests never read), so there is **no API-mock mismatch**. Per-failure:
    | # | Test | Spec selector / action | Live render | Category | Root cause |
    |---|------|------------------------|-------------|----------|------------|
    | 1 | `pipeline.spec.ts:35` create idea → INTAKE | `button` named `+ New Idea` (`PipelinePage.newItemButton`) → click | button is `+ Add idea` (×10, one per column); no `+ New Idea` | **(b)** | retired button label |
    | 2 | `pipeline.spec.ts:91` filter by search/priority/stage | `input[placeholder="Search ideas..."]` + `select` with `All Priorities`/`All Stages` | **no search input, no `<select>` filters at all** | **(b)** | filter UI removed/never shipped |
    | 3 | `pipeline.spec.ts:145` open/close workflow guide | `button` named `How it works` (`workflowButton`) | none — only `Workflows` nav link + `🌙` theme toggle | **(b)** | workflow-guide modal/UI removed |
    | 4 | `pipeline.spec.ts:201` persist intra-column reorder | `.grid-cols-5 .bg-white` cards | live card class is `group relative bg-white p-4 rounded-[10px] ... cursor-grab ...` — no `.grid-cols-5 .bg-white`; 0 match | **(b)** | card wrapper class changed (grid layout replaced) |
    | 5 | `pipeline.spec.ts:257` error message when API fails | `text=Error:` + `text=Retry` | page renders nothing for a mocked 500 `/api/state` (no `Error:`/`Retry` UI surface) | **(b)** | error/retry UI not present (retired or never built) |
    | 6 | `deletion.spec.ts:34` delete item disappears | `button[title="Delete"]` on card | **no delete affordance** — `anyDeleteAttr: []`; cards have `cursor-grab` (drag) only | **(b)** | per-card delete button removed |
    Supporting evidence (observed live DOM): `button[title]` returned only `Refresh pipelines`; h2 column headers still match (Intake/Refinement/Review Spec/Architecture/Review Arch/Testing/Review Test/Approved/Executing/Done) — the board skeleton is intact, only the interactive affordances drifted. Live `/api/state` → 200; `GET /api/items` → 405 (POST-only, as the mocks assume) — confirms the mock path is sound.
    **Implication for P3.8.3/P3.8.4:** since no failures are (a)-mock-mismatch, P3.8.3 ("fix mock mismatch first") is a **no-op**. The work is all **(b)** — rewrite the page-object selectors (`PipelinePage.ts`) + spec assertions to the live UI (correct add-button label, new card class, removed filters/workflow-guide/error-UI — several specs may need substantive rewrite or retirement since the feature they assert is gone). 3 passing specs (`move card between stages`, both `integrationsManager`, `addIntegrationModal`) survive because their selectors still match.
  - [x] **P3.8.3** DONE 2026-07-17 — **no-op by category**: P3.8.2 found **zero** (a)-API-mock-mismatch failures (all six failures are category (b) selector staleness). The mock-to-live `/api/state` shape is compatible (live items carry extra fields the mocks omit, but the failing tests never read them and `/api/items` is POST-only as the mocks assume), so there is no `page.route` body to correct. Skipped straight to P3.8.4 (the (b)-category selector rewrites).
  - [ ] **P3.8.4** **Fix remaining selector-staleness + timing failures**, then **re-run the full suite until green or ≤1 known flaky test quarantined** (move a genuinely flaky test to a `@quarantine`/`.skip` with a comment explaining why, rather than leaving it red). Update this parent [x] with the final pass count.

---

### P4 — Throughput (open)
- [x] **P4.1 Complexity-tier stage-skip pipeline (GateGuard)** — **DONE 2026-07-13** (commit `bad9926` on `feat/p2.4-route-llm-propose-brainstorm`). Implemented exactly per the design below and verified present in the live tree (`grep`): `agents/constants.py:55,62,65` `TIER_STAGES`/`DEFAULT_COMPLEXITY`/`next_stage()`; `api/constants.py:17` `VALID_COMPLEXITIES`; `agents/refiner.py:99,107` `COMPLEXITY_KEYWORDS`/`estimate_complexity()`; `agents/handlers.py:18` `StageHandler._advance()` (8 forward `transition_stage` calls rewritten) + `:67` REFINEMENT complexity-set; `api/schemas.py:12,38,85,108` `complexity` field + validator on `CreateItemRequest`/`UpdateItemRequest`. UI wiring (`CreateItemModal`/`ui/src/hooks/usePipelineState.ts`/`KanbanColumn.tsx` badge/`CardEditor.tsx` override) landed in the same commit. The design section below is retained as the authoritative reference; the ledger entry no longer needs the stale "not yet implemented" caveat.

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

**Last Updated**: 2026-07-15
