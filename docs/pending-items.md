# Pending items (review at fd980ed, 2026-11-07)

Consolidated from two read-only reviews of `66340b8..HEAD` plus a check of every open todo item against the code. Supersedes the "Open items" section of `docs/handsfree-progress.md`.

**Tags:** `V` = I re-checked it against the code. `R` = reported by a reviewer with file:line evidence, not re-checked by me. `D#` = blocked on a held decision.

**State at review:** backend 950 passed / 5 skipped / 10 deselected; UI vitest 71 passed; real data unchanged; branch pushed (`fd980ed`).

---

## P0: can damage real data or break a running system

| ID | Item | Where | Tag |
|---|---|---|---|
| P0-1 | **Two collected tests create and then `rmtree` directories inside the real `automation-ideas/`.** They are `unittest` classes using `./automation-ideas/test_suite`, `test_suite_state` and `test_bob_shell`, so the autouse fixture does not reach their `setUp`. Every default `pytest` run touches the live data folder. | `tests/test_workflow_automation.py:10,15`; `tests/test_bob_shell_integration.py:12` | V |
| P0-2 | **Pipeline loop has no corrupt-file handling.** `agents/state.load_state` does a bare `json.load`, so a corrupt `pipeline-state.json` fails every 30-second cycle with no backup. The API side now quarantines; the orchestrator side does not. Also bad UTF-8 in `integrations.json` raises before the hub's try, with no backup. | `agents/state.py:39-47`; `api/integration_hub.py:134-137`; `api/managers/base.py:40-44` (non-dict root not treated as corrupt) | V (state), R (hub, base) |
| P0-3 | **Retry timer thread can die silently.** `_advance` reads the template outside its try; a missing template or a corrupt manager file kills the timer thread and leaves the run RUNNING with nothing driving it. | `api/execution_engine.py:137-146, 165-166` | R |
| P0-4 | **Runs can be reported as started but never saved.** `create_run` swallows exceptions and returns False; `start_run` ignores the return value and hands back a run id that does not exist. Same pattern in bindings. | `api/execution_engine.py:55`; `api/managers/run_manager.py:113-138`; `api/managers/binding_manager.py:9-30` | R |
| P0-5 | **Corrupt Studio graph or skill files are silently overwritten.** `_load_graph` and `_load_skill` return None on bad JSON, so the next create with the same name replaces the file. `/integrations/status` swallows errors. | `api/managers/studio_graph_manager.py:38-48`; `api/managers/skill_manager.py:38-48`; `api/studio_router.py:255-256, 547-566` | R |
| P0-6 | **Lost update on inline output.** `update_inline_output` reads and writes the whole pipeline state without `state_lock()`, so it can overwrite an orchestrator commit or an API edit. | `api/board_router.py:163-170` | V |
| P0-7 | **`run_pipeline` has no mutual exclusion.** The orchestrator loop, the agents scheduler heartbeat, Telegram `/run` and watcher events can all process the same item at once (double LLM or executor spend, duplicate history). | `agents/orchestrator.py`; callers in `agents/scheduler.py:71`, `agents/telegram.py:137` | V (callers), R (impact) |
| P0-8 | **Containerised orchestrator cannot start.** `config.yaml` is tracked but not copied into the Docker image, and the agents build an `LLMClient` from it at import. | `docker/Dockerfile:40-42`; `agents/refiner.py:21`, `architect.py:21`, `tester.py:20` | V |
| P0-9 | **AI engine settings cannot be saved in Docker.** `~/.antikythera` is mounted read-only, but the service writes `ai_config.json` and `.ai_env` there. Setting a default fails; setting a key silently does not persist. | `docker/docker-compose*.yml`; `api/services/ai_engine_config.py:104-113, 738-776` | R |

## P1: security

| ID | Item | Where | Tag |
|---|---|---|---|
| P1-1 | **Secrets still leak from the integration list.** Unmasked: camelCase keys (`accessToken`, `clientSecret`), nested `auth.token`, `headers.Authorization`, values after a flag in `args` (`--api-key X`), and URL userinfo (`postgres://u:pw@h`). | `api/integration_hub.py:19-47, 233-248` | V |
| P1-2 | **Template validation still bypassable** by naming an integration in `step.type`; the engine dispatches on that name and an MCP integration runs its command. Needs D2 and D1. | `api/workflow_router.py:127-146`; `api/execution_engine.py:193` | R, D1/D2 |
| P1-3 | **Templates with non-list `steps` skip all validation;** config-only adapter steps skip the schema check. | `api/workflow_router.py:110-113, 150-160` | R |
| P1-4 | **SEC-7 is not a boundary:** absolute paths pass through and symlinks escape (no `realpath`). The terminal tool still runs `shell=True`. Needs D7. | `agents/executor_tools.py:67-78, 199` | V (`shell=True`), R (symlink), D7 |
| P1-5 | **No authentication anywhere,** server binds 0.0.0.0, CORS `*`. Includes the AI engine key routes, integration creation (MCP commands) and `/api/automation/accept`. Needs D1. | `api/main.py`; `start_antikythera.sh` | V, D1 |
| P1-6 | **Error responses include absolute file paths** (corrupt-file messages, `detail=str(e)`). | `api/board_router.py:22-25`; `api/workflow_router.py`; `api/integrations_router.py:45-50, 188-193` | R |
| P1-7 | **Swagger UI and the OpenAPI schema are public at `/docs`** now that the data mount is gone. Set `docs_url=None` if the schema should stay private. | `api/main.py:73` | V |
| P1-8 | **SafeExecutor runs in-process with no timeout** and is reachable from Studio and `/api/automation/accept`. Needs D7. | `api/executors/safe_executor.py:186` | V, D7 |
| P1-9 | **Network guard gaps** in tests: `connect_ex`, UDP `sendto`, DNS lookups and asyncio non-blocking connects are not caught. | `conftest.py` network guard | R |
| P1-10 | **`LLMClient()` loads the cwd `.env` and the real `~/.antikythera/ai_config.json`** in any test that does not stub it; `_persistent_env_path` ignores `HOME`. | `agents/llm_client.py:102, 133`; `api/services/ai_engine_config.py:82-84, 697` | R |
| P1-11 | **Rotate the Google key.** Test output earlier in this session may have echoed provider key material. Only you can do this. | - | user action |
| P1-12 | **Check published Docker images.** Images built before `eac8428` copied `automation-ideas/` (including vault files). Rebuild and rotate any secret they held. | - | user action |
| P1-13 | **Real data file modes:** `automation-ideas/secrets.vault` and `integrations.json` are 0644. The new atomic writes make them 0600 on the next save. | - | V |

## P2: correctness

| ID | Item | Where | Tag |
|---|---|---|---|
| P2-1 | **Every ordinary workflow step still fails** (2.1): `execute_action` called with 2 of 3 arguments. Needs D2. | `api/execution_engine.py:193` | V, D2 |
| P2-2 | **Studio: two placeholders in one string are not substituted.** The whole-placeholder regex matches across `{{a}} and {{b}}` and returns the text unchanged. | `api/execution/studio_graph_engine.py:866, 892-896` | V |
| P2-3 | **UI review gate is disconnected.** The UI writes `review.md` and calls `/api/move`; nothing sets `item.review_status` except Telegram, so the UI "needs revision" never reaches the pipeline and UI approval bypasses the gate. Needs D5. | `api/schemas.py:85-99`; `ui/src/hooks/useArtifacts.ts:96-125` | R, D5 |
| P2-4 | **Workflow engine value types changed** (`_resolve_context` now keeps ints, dicts and None instead of strings). Decide and record under D2. | `api/execution_engine.py:247-266` | R, D2 |
| P2-5 | **Native adapter calls block the event loop** (sync `execute_action` from async handlers, up to 30 s for MCP). | `api/integration_hub.py:287-349`; `api/integrations_router.py` | R |
| P2-6 | **Agent failures still advance the item;** stub text still becomes a spec. Needs D3. | `agents/handlers.py:64, 118, 156, 233` | V, D3 |
| P2-7 | **EXECUTING never finds a bound run.** Needs D4. | `agents/handlers.py:200, 215` | V, D4 |
| P2-8 | **Board moves have no rules.** Needs D5. | `api/board_router.py:98-105` | V, D5 |
| P2-9 | **Studio branch edges still ignored** (S3). | `api/execution/studio_graph_engine.py:477-480` | V |
| P2-10 | **Studio graph shape not validated** (S6): no cycle, duplicate-id or dangling-edge checks. | `api/execution/studio_graph_engine.py` | V |
| P2-11 | **Builder ignores LLM output** unless the decision contains "JSON" (S12). | `api/builder_router.py:57` | V |
| P2-12 | **A poison item is retried every 30 s forever** with no backoff or BLOCKED marker. | `agents/orchestrator.py:120-130` | R |
| P2-13 | **Startup reaper and in-memory timers:** a run that was retrying less than an hour before a restart stays RUNNING. `reap_stale_runs` uses separate lock acquisitions. | `api/managers/run_manager.py:76-109`; `api/main.py:60` | R |
| P2-14 | **Retry budget is cumulative per run** (`retry_count` never reset); dead BLOCKED branch in `record_failure`. | `api/execution_engine.py:203-213`; `api/retry_manager.py:52-61` | R |
| P2-15 | **Webhook runs use `current_step`, not `current_step_index`;** resuming one raises KeyError. | `api/trigger_router.py:53-58` | R |
| P2-16 | **Priority workaround:** the facade drops `priority`, so the route does a second, unchecked write. | `api/workflow_state_manager.py:44-48`; `api/board_router.py:43-46` | V |
| P2-17 | **Studio:** run-log pruning parses every log on each save; same-name graph creates within one second can overwrite. | `api/execution/studio_graph_engine.py:1047-1088`; `api/studio_router.py:252-256` | R |
| P2-18 | **Pipelines run endpoint returns `status: running`** for a run that never executes. | `api/pipeline_router.py:128-150` | R |
| P2-19 | **Jira test with no token returns 500** (`hub.vault` is None); duplicated blocks. | `api/integrations_router.py:97-135` | R |
| P2-20 | **Telegram feature** (D6, decided "remove"): not done. | `agents/telegram.py` | V |
| P2-21 | **Studio cron** (D11, decided "drop the claim"): status doc still mentions cron fields. | `PROJECT_STATUS.md` | V |
| P2-22 | **Undefined queue retention:** accumulate across runs, or latest run only? | `api/execution/studio_graph_engine.py` | decision |

## P3: UI

| ID | Item | Where | Tag |
|---|---|---|---|
| P3-1 | **Logs tab shows the raw JSON envelope** (`res.text()` on a `{"logs": ...}` response) and requests 1 MiB, which is now capped. | `ui/src/components/AIEngineSettings.tsx:187-190` | V |
| P3-2 | **`ArtifactViewer.tsx` hard-codes `http://localhost:8006`.** | `ui/src/components/ArtifactViewer.tsx:25` | R |
| P3-3 | **Integrations form pre-fills the masked token** and can overwrite the secret reference on blur. | `ui/src/components/IntegrationsManager.tsx:395-409, 614-625` | R |
| P3-4 | **Priority select never preselects "high";** no "critical" option. | `ui/src/components/CardEditor.tsx:91-93` | R |
| P3-5 | **Backend `dry_run` default is still `False`** for non-UI callers (scripts, curl). | `api/studio_router.py:162, 170` | R |
| P3-6 | Earlier UI items still open: drag to empty column (U1), polling cleanup (U2), dead calls (U3), `require()` imports (U4), Settings nav and placeholders (U5), Workflow Architect `default` poll (U6), AI provider list (U7), Blueprint error text (S13). | various | from todo |

## P4: tests and infrastructure

| ID | Item | Where | Tag |
|---|---|---|---|
| P4-1 | **Fixture does not redirect** `agents/handlers.DATA_DIR`, `agents/brain_loop` paths, or the cwd used by `agents/executor.py` and `executor_tools.py`. Safe today only because existing tests patch or chdir. | `agents/handlers.py:14`; `agents/brain_loop.py:19-22`; `agents/executor.py:220-243` | V |
| P4-2 | **Logger cache:** `get_logger()` returns cached instances, so a logger created before the fixture keeps the real path. | `agents/logger.py:11, 58-64` | R |
| P4-3 | **cwd-relative test dirs under `tests/`** (cleanup-only isolation). | `tests/test_brain_loop.py`, `test_api.py`, `test_e2e_workflow.py`, others | R |
| P4-4 | **Two tests still return non-None,** so the warning filter stays. | `tests/integration/test_full_jira_flow.py`; `api/executors/test_operator_registry_parsing.py` | V |
| P4-5 | **Unused imports and stale comments** across the changed files (including `reset_state_manager` and "RETRYING"). | see backend review R31 | R |
| P4-6 | **Proposed tests from the test plan** not yet written: T6/T7 (SafeExecutor escape and timeout), T16 (branch edges), T19 (drag), T20 (Blueprint 422), T22 (builder validate), T25 (MCP timeout kill), T26 (polling cleanup), T27 (refiner stub), T29/T30 (builder and MCP happy paths). | `docs/` vault Test-plan | from plan |

## P5: Docker and scripts

| ID | Item | Where | Tag |
|---|---|---|---|
| P5-1 | **Production UI image serves nothing** (plain nginx, no built assets). Proposal in the progress log (O1). | `docker/docker-compose.prod.yml`; `docker/Dockerfile.ui` | R |
| P5-2 | **Health endpoint** (O5), **backup and retention for `automation-ideas/`** (O7), **config load fallback and non-atomic config saves** (O8). | various | from todo |
| P5-3 | **Script robustness:** unquoted `cd $UI_DIR`, `.env` sourced before the existence check, `pkill -f vite` matches unrelated processes, runtime runs as root, sandbox image duplicates dev pins. | `start_antikythera.sh:64, 85`; `stop_antikythera.sh:14`; `docker/Dockerfile`, `Dockerfile.sandbox` | R |
| P5-4 | **`.env.example` sets `VITE_API_URL` to the frontend URL** (5173) instead of the backend (8006). | `.env.example:7` | V |

## P6: docs

| ID | Item | Where | Tag |
|---|---|---|---|
| P6-1 | `api/AI.md:28` still says `/docs` serves `automation-ideas/`; `api/AI.md:35` says `os.rename`. | `api/AI.md` | V |
| P6-2 | CLAUDE.md gotcha 2 (routers instantiate SecretVault) and gotcha 10 (prompt is positional; it is stdin) are stale; test command uses `source venv/bin/activate`; no mention of the network guard or `live_llm` marker. | `CLAUDE.md:35, 93, 101` | V |
| P6-3 | README: "Python 3.11+", Secret Vault claim, Jira env var names (`JIRA_PAT`, not `JIRA_ISV_...`), masking description. | `README.md:9, 30, 82, ~192-194` | V (Secret Vault), R (rest) |
| P6-4 | `docs/api-spec.md`: nonexistent routes (`/health`, pipelines `runs`/`logs`), no Studio section, `{id}` vs `{name}`. | `docs/api-spec.md` | R |
| P6-5 | `PROJECT_STATUS.md`: stale test counts, the old `test_architect` ordering claim, `reset_state_manager` reference. | `PROJECT_STATUS.md:10-12, 103, 175` | R |
| P6-6 | `ui/AI.md`: proxy target is now `API_PROXY_TARGET`. | `ui/AI.md:42` | R |
| P6-7 | Earlier doc items: H1 (regenerate api-spec), H3 (`docs/agents/*`), H6/H7 (duplicate models, stub routes). | various | from todo |

## P7: product completion (status doc)

| ID | Item | Where |
|---|---|---|
| P7-1 | Cross-surface end-to-end journey testing. | `PROJECT_STATUS.md:45` |
| P7-2 | Error scenario and recovery validation. | `PROJECT_STATUS.md:46` |
| P7-3 | Studio handover documentation. | `PROJECT_STATUS.md:48` |
| P7-4 | B3 auth (same as D1). | `PROJECT_STATUS.md:147` |
| P7-5 | Studio plan items: model tiers, perpetual aggregate, stub-route removal (S14). | `docs/plans/mighty-greeting-cookie.md` |

## Housekeeping (your call)

- Leftover untracked or empty directories: `config/`, `interceptors/`, `reporters/`, `utils/`, `requirements/`, `audit/`, `hermes/`, `test_data/`, `tmp_test_dir/` (untracked vault key file), `Users/` (nested git repo), `src/` (tracked and referenced), `screen-capture.log`.
- `automation-ideas/requirements/ID-999/` test debris.
- `test_operator_registry_simple.py` at the repo root (cited by `PROJECT_STATUS.md`).
- `venv/` was committed to git history earlier (`695cc47`, `512b61c`).

## Decisions still needed

| ID | Question | Blocks |
|---|---|---|
| D1 | Auth approach (bind to 127.0.0.1 now, token later?) | P1-2, P1-5, P7-4 |
| D2 | Workflow step schema: dispatch on `adapter` or `type`; value types in substitution | P1-2, P2-1, P2-4 |
| D3 | What happens when a stage agent fails or returns stub text | P2-6 |
| D4 | Entering EXECUTING with no bound run | P2-7 |
| D5 | Board move rules and how the UI sets `review_status` | P2-3, P2-8 |
| D7 | Executor terminal tool and SafeExecutor sandboxing; absolute executor paths | P1-4, P1-8 |
| - | Undefined-queue retention; perpetual aggregate; SEC-10 clamp vs 422; Swagger UI public or not | P2-22, P7-5, P1-7 |

## Suggested order

1. **P0-1** (tests touching real data), then **P0-2, P0-6, P0-7** (state safety), **P0-3, P0-4, P0-5**.
2. **P1-1, P1-3, P1-6** (security fixes that need no decision) and **P2-2**.
3. **P0-8, P0-9, P5-4** (Docker and config).
4. **P3-1 to P3-5** (UI fixes) and **P4-1, P4-2** (fixture gaps).
5. Your decisions **D1 to D7**, then the items they unblock.
6. Docs (P6), then P7.
