#!/usr/bin/env python3
"""P3.2.6 LIVE gate — prove the *real* default-LLM (google_gemma) executor path
produces a non-stub ``execution_report.md`` end-to-end.

Sibling of ``tools/verify_executor_p3_2.py`` (the no-network CI fixture).  The
CI fixture swaps ``LLMClient.chat`` at the class level for a deterministic
responder; **this** script deliberately does **not** swap anything, so the
live provider selected by ``ai_config.json`` (``google_gemma`` /
``gemma-4-31b-it`` since 2026-07-13) runs for real against the network.

Go-slow rules (see ``PROMPT.md`` §P3.2.6): ONE run, wait fully, kill at ~120s
if it hangs, no parallel runs, report honestly even if it flakes.  This script
installs a 125s ``SIGALRM`` backstop so a hang still dies — we never let a live
probe pile up.

It plants the *same* trivial health-endpoint idea the CI fixture uses
(``P3-2-HEALTH``) purely so the run is reproducible and the ``write_file``
target is small.  P3.2.7 — a *real* backlog idea past spec — is the next gate
and the one that closes the parent; this P3.2.6 gate only needs to prove the
live LLM can drive the agentic loop to a non-stub report + real on-disk file.

Teardown reuses the CI fixture's cleanup (deletes the planted run entry, the
fixture req dir, and any ``api/health_router.py`` / ``VERSION`` the executor
wrote — those are harness artifacts, not real backlog files).

Exit codes: ``0`` live-green, ``1`` a real assertion failed, ``2`` setup/teardown
or hang.  Run from repo root::

    python3 tools/verify_executor_p3_2_live.py
"""
from __future__ import annotations

import os
import signal
import sys
import importlib.util
import logging

# Repo root importable when run as a plain script.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
os.chdir(_REPO_ROOT)

# Surface executor logs so the live run is observable from the console.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from agents import executor as executor_mod  # noqa: E402
from api.managers.run_manager import RunManager  # noqa: E402

# Reuse the CI fixture's id, paths, spec/arch planters, cleanup, and target.
_spec = importlib.util.spec_from_file_location(
    "verify_executor_p3_2", os.path.join(_REPO_ROOT, "tools", "verify_executor_p3_2.py")
)
_fix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fix)

RUN_ID = _fix.RUN_ID
ITEM_ID = _fix.ITEM_ID
IDEAS_DIR = _fix.IDEAS_DIR
REQ_DIR = _fix.REQ_DIR
REPORT_PATH = _fix.REPORT_PATH
# P3.2.7 follow-up — the executor now anchors RELATIVE write_file paths at the
# item's requirements dir (agents/executor_tools._resolve_item_path).  The
# sibling CI fixture (verify_executor_p3_2.py) feeds ABSOLUTE paths via a
# stubbed chat, so its writes keep landing at the repo root — that's why
# ``_fix.HEALTH_ROUTER_PATH`` is repo-rooted and we leave that file unchanged.
# THIS live harness does NOT stub chat: the real Gemma executor reads the
# fixture spec/arch (which name ``api/health_router.py`` / ``VERSION``) and
# emits those as RELATIVE paths, which now anchor under ``REQ_DIR``.  So the
# on-disk proof below must read them from the item dir, not the repo root.
HEALTH_ROUTER_PATH = os.path.join(REQ_DIR, "api", "health_router.py")
VERSION_PATH = os.path.join(REQ_DIR, "VERSION")

# Load the user's env (symlink target ~/.antikythera/.env) so GOOGLE_API_KEY
# is present, exactly as the running app would have it.
_envp = os.path.join(os.path.expanduser("~"), ".antikythera", ".env")
if os.path.isfile(_envp):
    for _line in open(_envp, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)


def main() -> int:
    run_manager = RunManager(base_dir=IDEAS_DIR)

    # Fresh slate (a prior interrupted run may have left debris).
    _fix._cleanup(run_manager)
    _fix._plant_fixtures(run_manager)

    # Decide success *honestly*.  A real model may plan a different number of
    # tasks / different COMPLETED: wording than the 2-task stub, so the gate is
    # the core P3.2 anti-stub contract, not the stub's exact byte count.
    failures: list = []
    report_size = None
    completed_lines: list = []
    confidence = None

    def _on_alarm(signum, frame):
        sys.stderr.write("\nP3.2.6 LIVE GATE: hung past 125s — killing.\n")
        try:
            _fix._cleanup(run_manager)
        except Exception:
            pass
        sys.exit(2)

    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(125)
    try:
        confidence = executor_mod.executor_idea(ITEM_ID, run_manager, RUN_ID)
    except Exception as exc:  # noqa: BLE001 — report, then cleanup
        failures.append(f"executor_idea raised: {exc!r}")
    finally:
        signal.alarm(0)

    # ----- Assertions on the report that survived ----------------------
    if not os.path.isfile(REPORT_PATH):
        failures.append(f"execution_report.md not written at {REPORT_PATH}")
    else:
        report = open(REPORT_PATH, encoding="utf-8").read()
        report_size = len(report)
        if "stub response" in report:
            failures.append("report contains 'stub response' (degradation string leaked)")
        if len(report) <= 100:
            failures.append(f"report too short ({len(report)} chars) — near-empty stub report")
        completed_lines = [ln for ln in report.splitlines()
                           if ln.strip().startswith("- COMPLETED:")]
        if not completed_lines:
            failures.append("no COMPLETED: log entries in report")

    # ----- On-disk proof the live write_file tool actually landed ------
    health_written = os.path.isfile(HEALTH_ROUTER_PATH)
    if not health_written:
        failures.append("api/health_router.py was NOT written to disk by the live run")
    else:
        on_disk = open(HEALTH_ROUTER_PATH, encoding="utf-8").read()
        if "/health" not in on_disk:
            failures.append("api/health_router.py on disk has no /health route")

    # Always restore the repo, even on success — the health file is a harness
    # artifact, not real backlog work.
    _fix._cleanup(run_manager)

    print("P3.2.6 LIVE GATE (real google_gemma):")
    print("  provider            = google_gemma (gemma-4-31b-it)")
    print(f"  executor_idea()     = {confidence!r}  (100 == success, 0 == failure)")
    size_str = f"{report_size} bytes" if report_size is not None else "<no report>"
    print(f"  execution_report.md = {size_str}")
    print(f"  COMPLETED: entries  = {len(completed_lines)}")
    for ln in completed_lines:
        print(f"    {ln.strip()}")
    print(f"  api/health_router.py written = {health_written}")
    print("  fixtures cleaned             = True")
    if failures:
        print("\nP3.2.6 LIVE GATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nP3.2.6 LIVE GATE GREEN — real default LLM produced a non-stub report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
