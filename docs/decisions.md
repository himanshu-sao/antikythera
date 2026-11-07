# Decisions (answered by the user, 2026-11-07)

These answers unblock the held items in `docs/pending-items.md` and the open list in `docs/handsfree-progress.md` (autonomous run 2). A handsfree session implements them as written. Anything not covered here is still held: skip it and report.

## Design decisions

| ID | Decision | What to build | Unblocks |
|---|---|---|---|
| D1 | **Bind 127.0.0.1 and require a token.** | Default the backend host to `127.0.0.1` (start script, compose for local use; containers still bind 0.0.0.0 inside the container but publish on 127.0.0.1). Add a shared bearer token from `ANTIKYTHERA_API_TOKEN`, required on every `/api/*` route via one FastAPI dependency. If the variable is unset at startup, generate a random token, write it to `~/.antikythera/api_token` (mode 0600, honour `ANTIKYTHERA_HOME`) and log where it is. The UI sends `Authorization: Bearer <token>` (token from `VITE_API_TOKEN` at build time or a one-time paste stored in `sessionStorage`; pick one and document it). Restrict CORS to the UI origin(s) from `ANTIKYTHERA_CORS_ORIGINS` (default `http://localhost:5173`). Tests: 401 without token on several routes, 200 with it, CORS headers. | P1-5, P7-4 (B3), part of P1-2 |
| D2 | **Steps dispatch on `adapter` + `action`.** | Step shape is `{step_id, name, adapter, action, config, next_step}`. The engine calls `hub.execute_action(adapter, action, resolved_config)`. `type` is only used to mark `ORCHESTRATOR_TASK` (human-in-the-loop). The template validator already allowlists `adapter`; also require `action` and reject a `type` other than `ORCHESTRATOR_TASK` or absent. Migrate `automation-ideas/workflow_templates.json` shapes **in code** (a load-time adapter that maps old step shapes to the new one) rather than rewriting the user's file; update the builder fallback templates and any tracked fixtures. Keep typed values in `{{var}}` substitution (W3/W5 behaviour) and document it. Tests: a real `IntegrationHub` with a fake adapter runs a two-step template to COMPLETED (Test-plan T8). | P2-1, P1-2, P2-4 |
| D3 | **Hold at the stage with the error.** | When the refiner, architect or tester raises, or returns stub text (`LLMClient.is_stub`), do not advance: keep the item at its current stage, set `blocked_reason`, write no artifact. The UI shows `blocked_reason` on the card. A later successful run clears it. Combine with the existing 3-strike poison-item block. Tests (Test-plan T14, T27). | P2-6 |
| D4 | **Run the executor without a workflow run.** | For pipeline items at EXECUTING, call the agent executor directly; use a bound run only if one exists (keep that path). Remove the "No active run found" failure for the unbound case. Tests: unbound item executes and reaches DONE on success, goes to the tier-aware fallback on failure. | P2-7 |
| D5 | **Review API plus gated moves.** | Add `POST /api/item/{id}/review` with `{status: "APPROVED" or "NEEDS_REVISION", comment?}`. It sets `item.review_status`, appends the comment to `review.md` and the item history. The UI review form calls it instead of writing `review.md` and calling `/api/move`. `/api/move` rejects (422) a move out of a `REVIEW_*` stage, and a move into a stage the item's complexity tier skips, unless `force: true` is sent; the UI only sends `force` from an explicit "Force move" action. Tests for each rule and the UI form. | P2-3, P2-8 |
| D7 | **Allowlist, confine and subprocess.** | Executor `terminal` tool: no shell; split with `shlex.split`; allowlist of programs (`python`, `python3`, `pytest`, `pip`, `ls`, `cat`, `echo`, `git` with only `status`/`diff`/`log`); reject pipes, redirects and `;`/`&&` by construction. Executor file tools: resolve with `os.path.realpath`, require the result to be inside `automation-ideas/requirements/<ID>/`, reject absolute paths; update `tools/verify_executor_p3_2.py` and the tests that pinned absolute passthrough. SafeExecutor: run each script in a subprocess with a timeout (default 10 s) and a memory cap (`resource.setrlimit`, best effort on macOS), returning the same result/error shapes; keep the import allowlist. Tests (Test-plan T6, T7, T4). | P1-4, P1-8, SEC-6, SEC-8 |

## Other answers

| Topic | Decision |
|---|---|
| Docker runtime user | **Keep root for now.** Record the non-root proposal (W6 run 2) for a later live test. Do not change the user. |
| `start_antikythera.sh` env loading | **Switch to the safe KEY=VALUE parser** (same as `docker/entrypoint.sh`). Values are literal; `$VAR` inside values and inline comments are no longer interpreted. Note this in the README and the start banner. |
| Swagger UI at `/docs` | **Disabled unless `ANTIKYTHERA_ENABLE_DOCS=1`.** Set `docs_url`, `redoc_url` and `openapi_url` to `None` by default. Update the README link to say how to enable it. |
| Logs endpoint cap | **Keep the clamp and the `X-Log-Truncated` header.** No change. |
| Studio undefined queue | **Latest run only.** Keep the behaviour and document it in the Studio docs and API docstring. |
| Studio perpetual aggregate | **Build it.** A per-graph aggregate file (for example `studio_runs/<graph_id>.aggregate.json`) updated atomically in `_finalize_run`: total runs, total matched, undefined, escalated, by-status counts, last run id and time. It survives run-log pruning and is returned in the graph detail response. Tests. |
| Studio backend `dry_run` default | **Default to `true`.** `POST /api/studio/graphs/{id}/run` without `dry_run` runs dry; live writes need `dry_run: false`. Update tests and docs. |
| Studio cron scheduling | **Not now.** Leave unbuilt; the status doc already says so. |
| Cleanup | Delete: `ui/src/components/VirtualBoard.tsx`; untracked `test_data/` and `tmp_test_dir/` (update `api/executors/test_operator_registry_parsing.py` so its BASE_DIR uses a temp dir first); `automation-ideas/requirements/ID-999/` (test debris in the real data dir, the ONLY permitted write to real data); the repo-root `test_operator_registry_simple.py` (leave its `PROJECT_STATUS.md` history line). |
| Data restore | Dropped earlier; loss accepted. |
| Session mode | **Parallel workers, then push.** Disjoint files per worker, rules in `docs/worker-rules.md`, full verification at the end. Push to origin only if every check is green (backend, UI, real-data diff, no network attempts). |

## Still not decided (skip and report)

- Studio cron scheduling (decided "not now").
- Non-root container user (decided "keep root for now").
- Anything else not listed above.
