# Pending items (review at de14fad0, 2026-11-08)

> **Update 2026-11-08 (fix session, baseline c58f2e1f):** P0-1..P0-4, P1-1..P1-3, P2-1..P2-4 and P3-1 are DONE (five parallel workers B1-B5 plus coordinator fixes; backend 1987 passed, UI 262 passed, real data unchanged, all mutation-checked). The tables below are the pre-fix record. What remains open: P3-2..P3-8, P4-1..P4-6, P5 (arc B scope), P6 (root JS toolchain decision), and the known limitations — plus one new item: a repeatedly failing-but-not-raising agent is now held at its stage and retried every cycle indefinitely (the three-strike poison block counts only raising handlers; extend strike-counting to held items). B4 also fixed a pre-existing dependency-override leak in tests/test_studio_router_endpoints.py tearDown.

Consolidated from two read-only reviews of `252945a..HEAD` (run 3 + arc A + post-arc fixes, 110 commits) plus a direct verification of every decided-but-unbuilt item. Supersedes the previous list entirely.

**Tags:** `V` = verified against the code by the coordinator or a reviewer with file:line evidence. `D#` = blocks on or violates a recorded decision in `docs/decisions.md`.

**State at review:** backend 1892 passed / 5 skipped / 10 deselected, UI vitest 249 passed, Playwright 10/10, real data unchanged, everything pushed. Data-safety verdict from the review: clean.

---

## P0 — breaks the product in the real deployment

| ID | Item | Where | Tag |
|---|---|---|---|
| P0-1 | **First-run setup can never complete in Docker.** The setup router's loopback gate checks `request.client.host`, but through Docker NAT or the Vite/nginx proxy the backend sees a bridge-gateway or container IP, so `GET /api/setup/status` returns 403 for the legitimate tunnel user. Works only in the native start-script path. Fix: honour a configured trusted proxy (X-Forwarded-For from the known proxy only), allow the Docker bridge subnet, or gate on a one-time setup secret instead of peer IP. | `api/setup_router.py:124-134`; compose networking | V |
| P0-2 | **The pipeline tab list is always empty in production.** `loadPipelines` still uses plain `fetch`, never carries the bearer token, 401s silently (`if (res.ok)` swallows it), and bypasses `apiFetch` so the TokenGate never opens. The arc's "every fetch migrated" commit missed this one. | `ui/src/App.tsx:168` | V |
| P0-3 | **Failed workflow steps are recorded as done.** `_execute_native` returns `{"status": "error"}` instead of raising, and `_advance` never checks `result["status"]`, so a run where every step failed marches to COMPLETED. Concrete: the stored `AI_INTEGRATION_BOB` template migrates to `bob_shell`/`fetch_resource`, which raises `NotImplementedError`, and the run still reports success. Fix: check the status in `_advance` and route to `_handle_failure`; also add the builder's list/vector verbs (`list_pull_requests`, `list_tickets`, `update`) to `_ACTION_MAP` so builder-generated templates can actually run. | `api/execution_engine.py:225-244`; `api/integration_hub.py:590-604`; `api/adapters/bob_shell.py:130-132` | V |
| P0-4 | **WorkflowBuilder cannot save a template at all.** It POSTs the generated template without a `template_id`, so every save fails with 400. `BlueprintArchitect` derives one from the name; WorkflowBuilder does not, and neither the LLM parser nor the fallback templates produce one. | `ui/src/components/WorkflowBuilder.tsx:56-76`; `api/workflow_router.py:297-298` | V |

## P1 — security

| ID | Item | Where | Tag |
|---|---|---|---|
| P1-1 | **SafeExecutor escape.** `operator` is on the import whitelist and `type` remains in the child builtins; `operator.attrgetter("__class__")` reaches dunder attributes via a string, bypassing the AST dunder ban (which only inspects `Attribute` nodes). From there the subclasses walk reaches `os`/`subprocess`. Exactly the threat D7 confines. Fix: drop `operator` (and `types`) from the whitelist, remove `type` from child builtins, reject string literals containing `__` passed to attrgetter/itemgetter. | `api/executors/safe_executor.py:122-132, 280-287, 302-306` | V |
| P1-2 | **The terminal tool leaks the API's own secrets.** Allowlisted `python -c` runs with the full parent environment, so model-chosen code can read `ANTIKYTHERA_API_TOKEN`, `JIRA_PAT` and provider keys. `bob_shell` already uses a minimal env; the terminal tool should too (PATH plus explicitly safe vars). | `agents/executor_tools.py:310-313` | V |
| P1-3 | **`adapter_module` is never validated.** A token-holder can POST an integration pointing at any importable module with an `*Adapter` class, which the hub then imports and instantiates; the canonical fallback also routes credentials by user-controlled `adapter_module`. Operator-level (needs the token), but D2's allowlist intent is not enforced at the integration layer. Fix: validate against `CANONICAL_ADAPTERS` in add/update. | `api/integration_hub.py:606-615`; `api/integrations_router.py` POST | V |

## P2 — decided but never built (fell between the arcs)

These four were answered in the Q/A sessions and assigned to neither arc:

| ID | Item | Where | Tag |
|---|---|---|---|
| P2-1 | **D3: hold at stage on agent failure.** Decided: a failed or stub-reply refiner/architect/tester keeps the item at its stage with `blocked_reason`, writes no artifact. Today the handler still sets `blocked_reason` and advances. | `agents/handlers.py:64, 118, 156` | V, D3 |
| P2-2 | **D4: run the executor without a bound run.** Decided: pipeline items at EXECUTING run the agent executor directly. Today both paths raise "No active run found". | `agents/handlers.py:200, 215` | V, D4 |
| P2-3 | **Studio backend `dry_run` default → true.** Decided; still `False` at the API level, so a curl caller omitting the flag gets a LIVE run. Only the UI checkbox protects. (One-line fix plus tests.) | `api/studio_router.py:192, 200` | V |
| P2-4 | **Perpetual aggregate (dec #21).** Decided "build it": a per-graph aggregate file updated in `_finalize_run` (total runs, matched, undefined, escalated, last run), surviving log pruning, in the graph detail response. Only comments mention it today. | `api/execution/studio_graph_engine.py` | V |

## P3 — correctness and polish

| ID | Item | Where | Tag |
|---|---|---|---|
| P3-1 | **Help page: eight wrong claims.** (1) "the token is never returned by any endpoint" contradicts the setup screen's one-time display; (2) the tunnel/loopback setup claim is wrong in Docker (P0-1); (3) "needs revision sends it back" — the UI records the decision and the orchestrator moves the item back on its next cycle (phrase it accurately); (4) "dry run is ON by default" is API-wrong (P2-3); (5) four of the listed tunables are `wired: false`; (6) corrupt-file errors are path-free in responses, only logs name the file; (7) the workflow example has a self-referencing dead `next_step`; (8) the Slack webhook line oversells (nothing notifies until D10). | `api/help.html` | V |
| P3-2 | **review.md race.** The review endpoint appends under the board lock, but the artifact-content endpoint replaces the whole file with no lock; a concurrent edit can drop an appended review line. | `api/board_router.py:169-217` vs `:248-270` | V |
| P3-3 | **Start script still sources env files as shell.** The decided safe KEY=VALUE parser was applied only to the Docker entrypoint. A `.env` value with `$(...)` still executes at start. | `start_antikythera.sh:28-29, 73-81` | V |
| P3-4 | **Canonical dispatch updates the wrong status key.** After a fallback dispatch, status updates use the requested name (e.g. `jira`) instead of the matched record's key, so the credential-supplying integration's status never reflects the run. | `api/integration_hub.py:549, 553` | V |
| P3-5 | **README port sentence is now wrong.** "today the published ports are still 8006/5173 on all interfaces" — they are loopback 18006/15173 everywhere now. | `README.md:138` | V |
| P3-6 | **Unwired settings.** `orchestrator_interval_s` (run script hard-codes 30 s), both Studio caps (model defaults), `digest_interval_h` (no digest yet): a PATCH persists values nothing reads. Wire the interval and caps; the digest waits for D10. Also `agents/state.py:17-18` comment contradicts its value (0600 vs 0644). | `scripts/run_orchestrator.py:18`; `api/models/studio.py` defaults | V |
| P3-7 | **Executor tunables are not settings** (max attempts, workspace cap, terminal timeout) — arc B consumers per the D14 record. | `agents/executor.py`, `agents/executor_tools.py` | V |
| P3-8 | **Settings surface thinner than decided:** the env-backed secret settings (Slack webhook, token presence) and the heartbeat move from `config.yaml` are absent. | `api/settings_store.py` | V, D14 |

## P4 — tests and infrastructure

| ID | Item | Where | Tag |
|---|---|---|---|
| P4-1 | **Consumer tests read the developer's real `~/.antikythera/settings.json`.** conftest never sets `ANTIKYTHERA_HOME`, so the settings consumers (poison strikes, retry delays, reap age, max tasks, bob timeout) and one auth test are machine-dependent. One-line autouse fix. | `conftest.py`; consumers in `api/retry_manager.py:21` etc. | V |
| P4-2 | **Real-data-dir instances at import/fallback.** `builder_router`'s dead module-level `WorkflowStateManager` mkdirs the real `knowledge/` at import; `internal.py`'s exception fallback builds a manager on the real data dir. | `api/builder_router.py:20`; `api/adapters/internal.py:48-52` | V |
| P4-3 | **UI error handling.** `submitReview`/`requestMove`/`forceMove` have no try/catch (unhandled rejections, silent failures); `saveContent` failures are invisible. | `ui/src/hooks/useArtifacts.ts:89-105, 129-181` | V |
| P4-4 | **E2E gaps.** No spec mocks `/api/setup/status` (outcomes depend on backend state); nothing exercises the token/401 flow at browser level; the journey specs are arc B scope. | `tests/e2e/*.spec.ts` | V |
| P4-5 | **Network guard: `gethostbyname` uncovered** (no current production path uses it). | `conftest.py` | V |
| P4-6 | **SetupScreen clipboard dead-end** on non-secure origins (localhost is fine). | `ui/src/components/SetupScreen.tsx:227-239` | V |

## P5 — arc B scope (decided, waiting)

D10 Slack notifications (failures immediate, gates digested every 6 h), D13 model tiers (light/standard/heavy, safe defaults), D14 frontend (Settings tab, Studio per-graph form), D11 `docs/studio/` set, D12 nightly backup schedule docs, Phase 6 journey tests (Playwright + backend integration), remaining doc fixes (`docs/api-spec.md` nonexistent routes and no Studio section; `docs/agents/AI.md` wrong stages; `executor-agent-design.md` "3 attempts" vs the code's 5), removal of the stub routes (`/api/automation/templates`, `/api/automation/state`, the in-memory `/api/skills`), consolidation of the duplicate `Skill`/condition models.

## P6 — cleanup decision

The root JS toolchain (`package.json` with jest/vite scripts, `jest.config.js`, `babel.config.js`, root `vite.config.ts`) overlaps the `ui/` toolchain and jest would try to collect the vitest suite. Deleting it was proposed twice; it needs your explicit OK because the root `npm test`/`npm run dev` shortcuts disappear.

## Known limitations (accepted, recorded)

- SafeExecutor memory cap not enforced on macOS (`setrlimit` rejects `RLIMIT_AS`/`RLIMIT_DATA`); CPU and file-size limits are.
- The D7 terminal allowlist is not a sandbox: `python`/`pip`/`pytest` run arbitrary code as the current user (mitigate with P1-2's minimal env).
- Path checks are TOCTOU-sensitive (symlink swap after the check); the model cannot create symlinks through the tools.
- AppShell requests fire before the setup gate resolves (harmless).
- Setup POST rate limit is global (20/60 s).
- Retry timers and the poison-item counter are in-memory; a restart re-arms them and the boot reaper fails in-flight runs.

## Suggested order

1. **P0-1 to P0-4** (the deployment blockers; all small-to-medium).
2. **P1-1, P1-2** (SafeExecutor escape, terminal env leak), then P1-3.
3. **P2-1 to P2-4** (the fallen-through decisions; D3 and the dry-run default are one-liners).
4. **P3-1** (help page accuracy) together with P0-1/P2-3 since the same claims are involved.
5. **P4-1** (the conftest one-liner), then the rest of P3/P4.
6. **Arc B** (P5) with the P2 items folded into its scope if not done before.

## Closed since the previous list

Run 3 (252945a..d1c248a) closed the previous P0-1..P0-9, P1-1, P1-3, P1-6, P1-9, P1-10, P2-2/5/9/10/11/12/15/16/17/18/19/20, P3-1..P3-4, P4-1..P4-4, P5-1/3/4 and the Telegram/cron doc items. Arc A (7826013..8b41be34) closed P1-5 (auth), P2-1 (step dispatch), P2-3 (review API), P2-4 (typed values), P2-8 (move gates) and P7-4/B3. The post-arc fixes closed the stored-template runtime gap (canonical fallback + integration-record credentials) and added `/help`. B3/auth is done via D1.
