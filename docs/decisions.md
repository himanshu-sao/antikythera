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
- Non-root container user (decided "keep root for now"; note the account on the Docker host is already a regular user — the question was only about the in-container user).
- Anything else not listed above or in the D8/D9 sections.

---

# Decisions added later on 2026-11-07 (topology and setup)

These came out of the deployment discussion after run 2. They extend, and where they overlap supersede, the table above.

## D8 — Deployment topology and ports

**Facts about the deployment (the user's setup):**
- The Docker daemon and all containers run on a **remote Docker host**, reached via `DOCKER_HOST=ssh://...` (Docker context `remote-host`). The laptop only runs the browser and the `docker`/`ssh` clients.
- The remote host runs as a **regular user, not root**, and holds a copy of the code (builds send the build context there).
- Data paths are on the remote host: `~/.antikythera/` (config, `.env`, `.ai_env`) and `~/antikythera-data/` (the `automation-ideas` volume).

**Decision:**
- **Ports become 18006 (API) and 15173 (UI) everywhere they are exposed.** Containers keep 8006/5173 internally. Implement in: `docker/docker-compose*.yml` publish entries (`127.0.0.1:18006:8006`, `127.0.0.1:15173:5173`), `start_antikythera.sh` default `PORT`, `ui/vite.config.ts` (dev server port and default `API_PROXY_TARGET` port), `playwright.config.ts` `baseURL`, `.env.example` (`VITE_API_URL=http://localhost:18006`), and the compose `VITE_API_URL` values. Update every test that hard-codes 5173/8006.
- **Publish loopback-only on the Docker host.** Nothing on any other interface. The local (non-Docker) start path also binds `127.0.0.1`.
- **Access from the laptop is an SSH tunnel**, not published ports: `ssh -N -L 18006:127.0.0.1:18006 -L 15173:127.0.0.1:15173 <user>@<docker-host>`. Document the tunnel in `docker/README.md` and the main README (done in README). Suggest a `LocalForward` block for `~/.ssh/config` in the docs.
- `ANTIKYTHERA_CORS_ORIGINS` default becomes `http://localhost:15173` (see D1).
- Do not change the container-internal ports; only the published/host-side ones.

## D9 — First-run setup wizard

**Goal:** replace hand-editing `~/.antikythera/.env` and `.ai_env` on the Docker host with a guided UI. The user should be able to clone, start the stack, open the tunnel and configure everything from the browser.

**Backend (new `/api/setup` router):**
- `GET /api/setup/status` — what is missing, as a list of typed items (no secret values, only names and presence): env file present, each provider key set/unset (names only), Jira base URL/PAT set/unset, API token generated or not, Slack webhook set/unset (D10), ports/origins at their defaults, data directory present and writable, backup directory configured. Response includes `complete: bool`.
- `POST /api/setup/config` — accepts a partial map of the values above; writes them through the **existing safe env writer** in the AI engine config service (single-quoted values, mode `0600`, `ANTIKYTHERA_HOME`-aware). Provider keys go to `.ai_env`; Jira and non-secret settings to `.env`. Rejects unknown keys and values containing newlines/NUL (same rules as the writer).
- `POST /api/setup/complete` — writes the marker `~/.antikythera/.setup_complete` (mode `0600`); the setup endpoints refuse to do anything once it exists.
- `DELETE /api/setup/complete` (or `POST /api/setup/reopen`) — clears the marker; requires the D1 token; for re-running setup later.

**Security rules (must-have, test each):**
- The setup endpoints are active **only while the marker file is absent**. After completion they return 404 (not 403 with detail).
- While setup is incomplete the endpoints accept **loopback connections only** (check `request.client.host` in `127.0.0.0/8` and `::1`). The SSH tunnel terminates on the Docker host's loopback, so this works remotely. Non-loopback gets 403.
- They never return existing secret values — only whether each is set. `POST /api/setup/config` never echoes values back.
- Once the D1 token exists, reopening setup requires the token; the initial run (no token yet) is protected by the loopback restriction alone.
- Rate-limit `POST /api/setup/config` (simple in-memory counter is enough) to blunt brute-force attempts against Jira/keys during the open window.

**Frontend:**
- A `Setup` screen shown automatically when `GET /api/setup/status` reports incomplete (the UI checks once on load): one section per status item, masked inputs for secrets, a final "Finish setup" that calls `/complete`, and a one-time display of the generated API token with a copy button.
- The UI stores the token in `sessionStorage` and sends it as the D1 bearer on every request.

**Out of scope for the first cut:** editing already-set values after completion (reopen flow covers it), multi-user anything.

---

# Requirements set 2 (2026-11-07, Q/A session)

Scope of the next handsfree arc: **implement D1–D13 plus the remaining docs and Phase 6/7 items.** No live end-to-end acceptance run this arc (decided: skip).

## D10 — Slack notifications

Telegram is gone; nothing notifies the user. Replace with Slack, following the house pattern already used by the digest jobs (`~/Work/src/bin/scripts/*_digest.py` and the Obsidian vault notes):

- **Transport:** Slack incoming webhook. URL resolution order: `ANTIKYTHERA_SLACK_WEBHOOK`, then the shared `ISV_SLACK_WEBHOOK_URL`, then a file outside synced folders (same fallback approach as the digest scripts). The URL is a secret: never logged, never returned by any API, never echoed in errors; masked if it ever appears in config listings. Configure it through the D9 setup wizard (add a "Slack webhook" item to `GET /api/setup/status` and the setup screen).
- **Message style:** match the digests — plain text, source badge `:gear: *[ANTIKYTHERA]*`, short blocks, a character cap with a "...and N more" footer. One message per event for immediate events.
- **Cadence (decided):** failures and blocks are **immediate**; review-gate items are **digested every 6 hours**.
  - Immediate: a run goes BLOCKED or fails terminally; an item's `blocked_reason` is set; a `REC-*` escalation item is created; a poison item is blocked after 3 strikes.
  - Digest (flush at most every 6 hours, checked by the orchestrator loop or a small in-process scheduler): every item currently waiting at a REVIEW_* gate (id, title, stage, waiting-since), plus a count summary. Flush immediately if the digest grows past a cap (e.g. 15 items).
- **Delivery rules:** notifications must never break the pipeline — post on a worker thread or best-effort with a short timeout (5 s), catch and log all errors, and never retry in a loop. If no webhook is configured, log the event at INFO and continue (current behaviour remains the fallback).
- **Suppression:** each immediate event notifies once (dedupe by item id + event type + day). Items already reported in a digest are not re-reported until their state changes.
- Tests: fake `httpx`/urlopen client (no network); URL never appears in logs or responses; immediate vs digest routing; dedupe; timeout and failure are swallowed; no-webhook fallback.

## D11 — Studio handover documentation (Phase 7)

A `docs/studio/` set, aimed at a new operator:

- `overview.md` — what Studio is for, the turn-based build flow (Query → Fan-out → AI-transform → Conditional-action), preview vs commit vs run, dry-run semantics (default on), the graph outline panel.
- `nodes.md` — reference for the four archetypes: fields, conditions, loop edges vs branch edges, undefined queue, `{{var}}` substitution rules (typed whole-placeholder values, absent placeholders kept as text).
- `api.md` — the `/api/studio/*` endpoints with request/response shapes (generate from the router's OpenAPI where possible), including `dry_run`, run logs, the per-graph aggregate, and id validation rules.
- `operations.md` — running graphs, reading run status (`completed` / `partial` / `failed`), the undefined queue (latest run only — decided), run-log retention (`max_run_logs`), backups, and the sandbox limits for AITransform scripts.

The Obsidian vault notes remain the personal knowledge base; these are the shipped docs. Cross-link from the README documentation index.

## D12 — Nightly backup schedule on the Docker host

- Document (and provide as a copy-paste block in `docker/README.md`) a **cron entry or systemd timer on the Docker host** that runs `scripts/backup_data.sh` nightly at an off-peak minute (e.g. 03:17), sourcing the data dir `~/antikythera-data` and keeping the existing rotation (`ANTIKYTHERA_BACKUP_KEEP`, default 14).
- The user installs it once by hand on the host. Also document restoring from an archive (verify the tar listing first, stop the stack, extract, start).
- No scheduler inside the containers for this.

## D13 — Model tier mapping (Studio plan dec #10)

- Nodes already carry `suggested_model_tier`; nothing consumes it. Add a **tier → model mapping to the AI Engine config** (`~/.antikythera/ai_config.json`): a `tiers` object mapping tier names (e.g. `light`, `standard`, `heavy`) to `{provider, model_id}`, editable via the AI Engine settings UI and the D9 setup wizard, with sensible defaults derived from the configured models.
- Consumers: AITransform node execution and the agent stages (refiner/architect/tester/executor) resolve their model by tier with fallback to the configured default model when the tier is unmapped or the node has no tier. Resolution must never fail a run — unknown tier falls back to the default and logs once.
- Tests: tier resolution (mapped, unmapped falls back, node without tier), config edit round-trip, no run fails because of a bad tier.

## Phase 6 journey tests (form decided)

- **Playwright e2e** for the golden paths across surfaces, API mocked with `page.route` (existing pattern): create idea → refine (mocked) → review via the new D5 review form → gated move rules; Studio: build a 2-node graph → preview → save → dry run; Integrations: add + test connection (mocked); AI Engine: set default model (mocked); the D9 setup screen first-run flow.
- **Backend integration tests** for the cross-router flows the browser specs mock away: review endpoint → orchestrator gate advance; template save validation → trigger run (with the D2 dispatch fix); setup wizard status → config write → complete lock.
- Update `playwright.config.ts` `baseURL` for the D8 port change.
