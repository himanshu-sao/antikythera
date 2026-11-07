# Rules for parallel hardening workers

Eight workers (W1 to W8) edit different files in the same checkout at the same time. Read this file, then `CLAUDE.md`, then `docs/pending-items.md` (item IDs such as P0-1) and `docs/handsfree-progress.md` (what was done earlier).

Repo: FastAPI backend `api/`, agent pipeline `agents/`, React UI `ui/`, JSON state in `automation-ideas/` (gitignored REAL user data). Branch `feat/phase4-workflow-architect`, HEAD `35b641f` when the run started.

## Hard rules

1. **Edit only the files you own** (listed in your brief) plus NEW files you create (new tests, new scripts). If an item needs a file you do not own, skip it and report it.
2. **Tests first for bugs.** Write the regression test, confirm it fails for the right reason, fix, confirm it passes. Write comprehensive tests for code you add or change (happy path, guards, edge cases, regression). Use fakes for LLMs, hosts and credentials. The autouse fixture `isolate_data_dir` in `conftest.py` redirects data paths to `tmp_path`; rely on it, and build managers and engines on `tmp_path` in your tests.
3. **Targeted runs only.** Never run the whole suite, e2e, or the whole vitest suite.
   - Python: `env -u GOOGLE_API_KEY -u GOOGLE_API_KEY_KANBAN -u NVIDIA_API_KEY -u OPENROUTER_API_KEY -u OPENAI_API_KEY ANTIKYTHERA_BOB_STUB=1 ./venv/bin/python -m pytest <files> -q -p no:cacheprovider -W ignore`
   - Never pass `-m` (do not select `live_llm`, `network` or `watcher` tests). Never `source venv/bin/activate`.
   - UI: `cd ui && npx vitest run <specific files>`.
   - A test failing with "network blocked in tests" needs a fake. Fix it within your files or report it.
4. **No network, no installs.** Do not run docker, `pip install`, `npm install`/`ci`/`audit`, `git fetch`/`push`, or the start/stop/restart scripts, and do not start servers. Never set `dangerouslyDisableSandbox`.
5. **Never touch real data.** Do not write to the real `automation-ideas/`, `registry/` or `~/.antikythera/`. Never print, copy or quote a secret value, or the contents of `~/.antikythera/*` or `.env`: names and counts only. Never put environment values in assertion messages.
6. **Delete only what your brief lists.**
7. **Git.** Commit each item separately: `git add <your paths>` then `git commit -m "<msg>" -- <explicit paths>`. Never `git add -A`, `git add .`, `git commit -a`, amend, rebase, reset, stash, checkout of other files, or push. If `.git/index.lock` exists, wait 5 s and retry (up to 6 times). Conventional commit messages that mention the item ID. No Co-Authored-By trailer.
8. **Do not edit `docs/`, the vault, or any file you do not own** (except where your brief says so). W1 owns `conftest.py` and `pytest.ini` and may be editing them while you work. If you see fixture or collection errors you did not cause, wait 60 s and re-run (up to 3 times), then report.
9. **Decisions.** `docs/decisions.md` (2026-11-07) answers D1, D2, D3, D4, D5 and D7 and several other topics. Implement only what your brief assigns from it. The list below is what was held BEFORE those answers; anything not answered in `docs/decisions.md` is still held.

   **Previously held (now see `docs/decisions.md`):**
   - D1 authentication.
   - D2 workflow step dispatch and schema (`api/execution_engine.py` `hub.execute_action` call and step `type` handling).
   - D3 what happens when refiner, architect or tester fail or return stub text.
   - D4 run binding at EXECUTING.
   - D5 board move rules and `review_status` from the UI.
   - D7 executor `terminal` tool, SafeExecutor sandboxing, and absolute executor paths.
   - Also: do not flip the backend `dry_run` default, and do not wire `api/trigger_router.set_trigger_deps` (the webhook would bypass template validation). Do not change the `${env:X}` resolution policy.
10. **Skip and report** an item (with the question) if it needs a new dependency, a user-visible data or schema change beyond what is described, or a behaviour decision not given. Stop your whole task if three items in a row fail, or if your change breaks tests outside your scope that you cannot fix within your files.
11. **Confirm each defect in the code before changing it.** If the code refutes it, skip and report. You may remove unused imports in files you own and touch.
12. At the start and the end run `stat -f '%m %N' automation-ideas/pipeline-state.json automation-ideas/integrations.json` and report both results. They must not change.

## Final message

Plain markdown, no emojis, under 900 words:

- A table of items: ID, summary, commit hash, tests added, failing-before / passing-after.
- Items skipped or needing a decision, with the question.
- Behaviour changes the user will notice.
- Anything another worker or the coordinator must know.
- Any test you saw touching real data or the network.

## Ownership map (who may edit what)

| Worker | Area | Files |
|---|---|---|
| W1 | Test infrastructure | `conftest.py`, `pytest.ini`, `agents/logger.py`, `agents/executor.py`, `agents/executor_tools.py`, `tests/test_isolation_fixture.py`, `tests/test_network_guard.py`, `tests/test_workflow_automation.py`, `tests/test_bob_shell_integration.py`, `tests/test_api.py`, `tests/test_e2e_workflow.py`, `tests/test_secret_vault.py`, `tests/integration/*`, `api/executors/test_operator_registry_parsing.py`, `tests/test_executor_*.py`, `tests/test_llm_client.py` |
| W2 | Pipeline state | `agents/state.py`, `agents/orchestrator.py`, `agents/scheduler.py`, `scripts/run_orchestrator.py`, `tests/test_state*.py`, `tests/test_orchestrator_*.py`, `tests/test_run_orchestrator.py` |
| W3 | API engine and managers | `api/execution_engine.py`, `api/retry_manager.py`, `api/escalation_manager.py`, `api/managers/{base,run_manager,template_manager,binding_manager,kanban_state_manager}.py`, `api/workflow_state_manager.py`, `api/trigger_router.py`, `api/pipeline_router.py`, `api/board_router.py`, `api/orchestrator_router.py`, `api/engine_router.py`, `api/brain_managers.py`, `api/brain_api.py`, `api/main.py`, `tests/test_managers*.py`, `tests/test_execution_engine_steps.py`, `tests/test_board_items.py`, `tests/test_pipeline_router.py`, `tests/test_brain_deltas.py`, `tests/test_workflow_trigger_router.py`, `tests/test_observer.py` |
| W4 | Automation Studio and builder | `api/execution/studio_graph_engine.py`, `api/studio_router.py`, `api/models/studio.py`, `api/managers/{skill_manager,studio_graph_manager}.py`, `api/builder_router.py`, `ui/src/components/{AutomationStudio,BlueprintArchitect,WorkflowBuilder,WorkflowArchitect}.tsx`, `ui/src/api/studioClient.ts`, `ui/src/types/studio.ts`, their vitest files, `tests/test_studio_*.py`, `tests/test_builder_router.py` |
| W5 | Integrations, templates, AI engine | `api/integration_hub.py`, `api/integrations_router.py`, `api/workflow_router.py`, `api/routers/ai_engine_config_router.py`, `api/services/ai_engine_config.py`, `api/models/config.py`, `tests/test_integration*.py`, `tests/test_missing_secret_routes.py`, `tests/test_credentials_resolution.py`, `tests/test_ai_engine_config.py`, `tests/test_workflow_router_template.py`, `tests/test_security_hardening.py` |
| W6 | Docker, scripts, ops | `docker/*`, `.dockerignore`, `.env.example`, `start_antikythera.sh`, `stop_antikythera.sh`, `restart_antikythera.sh`, `requirements*.txt`, new `scripts/backup_data.sh`, new `tests/test_backup_script.py` |
| W7 | UI (non-Studio) | `ui/src/**` except the W4 files above, plus their vitest files and `ui/src/test/setup.tsx` |
| W8 | Telegram removal | `agents/telegram.py`, `agents/notifications.py`, `agents/brain_loop.py`, `tests/test_telegram.py`, `tests/test_brain_loop.py`, `tests/test_notifications*.py`, and only the Telegram mentions in `README.md`, `docs/agents/AI.md`, `docs/CONTRIBUTING.md`, `api/workflow_AI.md`; plus the cron statements in `PROJECT_STATUS.md` |
