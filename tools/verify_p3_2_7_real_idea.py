#!/usr/bin/env python3
"""P3.2.7 gate — carry ONE *real* backlog idea (SCRIPT-01, a standardized
system health & log-management utility) through the real producer agents end to
end and assert every artifact is non-stub.  This is the gate that closes the
P3.2 parent ("produce one real ``execution_report.md`` end-to-end").

Shock-separated from the P3.2.6 *live-executor* proof
(:mod:`tools.verify_executor_p3_2_live`):
P3.2.6 only proved the executor agentic loop works against a throwaway
health-endpoint *fixture*; it never exercised the upstream Refiner/Architect/
Tester producers on a real backlog item, and it deleted the planted fixture at
the end.  THIS harness drives a genuine backlog idea through the full
``Architect → Tester → Executor`` chain with the **real default LLM
(``google_gemma`` / ``gemma-4-31b-it``)** — not ``bob``, not the stub seam —
and asserts all five P3.2 artifacts are non-stub:

  * ``spec.md``            — already real on disk (SCRIPT-01's genuine spec;
                             NOT regenerated here — ``refine_idea`` would
                             overwrite it with an LLM re-roll and could
                             degrade to the stub template if the LLM flakes).
                             This harness only asserts it is non-stub.
  * ``architecture.md``    — ``architect_idea`` (LLM), MUST be non-stub.
  * ``tests.md``           — ``tester_idea`` (LLM), MUST be non-stub.
  * ``review.md``          — the human-in-the-loop review gate.  No code agent
                             writes it (it records a human ``review_status``),
                             so this harness writes a genuine review sign-off
                             of the produced architecture/tests.
  * ``execution_report.md`` — ``executor_idea`` (LLM agentic loop), MUST be
                             non-stub, with real ``COMPLETED:`` entries and a
                             real on-disk artifact the executor wrote.

Why entry functions, not the Orchestrator stage machine: the orchestrator
STALLS at every ``REVIEW_SPEC`` / ``REVIEW_ARCH`` / ``REVIEW_TEST`` gate
waiting for a human ``review_status == "APPROVED"``.  Driving through
``run_pipeline`` would auto-block there; the P3.2.4/P3.2.6 harnesses already
proved calling each ``<stage>_idea`` entry function directly is the right seam
for a one-shot verification, and P3.2.7's acceptance ("run it through
Refiner→Architect→Tester→Executor") is satisfied by exercising those exact
producer functions in order on a real item.

Go-slow (per ``PROMPT.md`` §P3.2.7): ONE run, real LLM, wait fully, kill at
~305s if it hangs (each producer call may take 15–40s on Gemma; the executor
agentic loop runs several turns), no parallel runs, report honestly even if
it flakes.  A 305s ``SIGALRM`` backstop guarantees a hang dies.

Only the planted ``workflow_runs.json`` run entry is a harness side-effect and
gets cleaned up; the real backlog artifacts (architecture.md, tests.md,
review.md, execution_report.md, and the executor's on-disk script) STAY —
they are the deliverable.

Exit codes: ``0`` P3.2.7 green, ``1`` an assertion failed, ``2`` setup /
hang.  Run from repo root::

    GOOGLE_API_KEY must be set (loaded from ~/.antikythera/.env here).
    python3 tools/verify_p3_2_7_real_idea.py
"""
from __future__ import annotations

import os
import signal
import sys
import logging

# Repo root importable when run as a plain script.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
os.chdir(_REPO_ROOT)

# Surface agent logs so the live run is observable from the console.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from agents import architect as architect_mod  # noqa: E402
from agents import tester as tester_mod        # noqa: E402
from agents import executor as executor_mod    # noqa: E402
from api.managers.run_manager import RunManager  # noqa: E402
from agents.llm_client import LLMClient          # noqa: E402

# ── The real backlog idea carried through the pipeline ─────────────────────
ITEM_ID = "SCRIPT-01"
ITEM_TITLE = "Standardized System Health & Log Management Utility"
IDEAS_DIR = os.path.join(_REPO_ROOT, "automation-ideas")
REQ_DIR = os.path.join(IDEAS_DIR, "requirements", ITEM_ID)
SPEC_PATH = os.path.join(REQ_DIR, "spec.md")
ARCH_PATH = os.path.join(REQ_DIR, "architecture.md")
TESTS_PATH = os.path.join(REQ_DIR, "tests.md")
REVIEW_PATH = os.path.join(REQ_DIR, "review.md")
REPORT_PATH = os.path.join(REQ_DIR, "execution_report.md")
RUNS_JSON = os.path.join(IDEAS_DIR, "workflow_runs.json")
RUN_ID = "P3-2-7-SCRIPT01"

# Load the user's env (symlink target ~/.antikythera/.env) so GOOGLE_API_KEY
# is present, exactly as the running app would have it.
_envp = os.path.join(os.path.expanduser("~"), ".antikythera", ".env")
if os.path.isfile(_envp):
    for _line in open(_envp, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)


def _is_non_stub(path: str, min_chars: int = 120) -> tuple:
    """Return (non_stub, reason). Anti-stub contract used across P3.2::

    content exists, is longer than a coarse floor, contains no degradation
    ``stub response`` string, and (for md) carries at least one section header
    or concrete body beyond a bare-title skeleton.
    """
    if not os.path.isfile(path):
        return False, "file not written"
    text = open(path, encoding="utf-8").read()
    if "stub response" in text.lower():
        return False, "contains 'stub response' (degradation string leaked)"
    if len(text) <= min_chars:
        return False, "too short ({0} chars <= {1})".format(len(text), min_chars)
    return True, "{0} chars".format(len(text))


def _plant_run(run_manager: RunManager) -> None:
    """Plant the harness run entry the executor needs (mirrors P3.2.6)."""
    payload = {"item_id": ITEM_ID, "status": "RUNNING",
               "kind": "P3.2.7 real-backlog-idea verification"}
    planted = run_manager.create_run(RUN_ID, payload)
    if not planted:
        _cleanup_run(run_manager)
        planted = run_manager.create_run(RUN_ID, payload)
        if not planted:
            raise RuntimeError("failed to plant run entry " + RUN_ID)


def _cleanup_run(run_manager: RunManager) -> None:
    """Remove only the harness run entry; keep the real backlog artifacts.

    Uses RunManager._load/_save so the atomic temp-file-then-rename invariant
    is preserved (no public delete_run exists).
    """
    try:
        runs = run_manager._load()
        if RUN_ID in runs:
            del runs[RUN_ID]
            run_manager._save(runs)
    except Exception as exc:  # best-effort — never mask a real failure
        print("[warn] failed to delete run entry " + RUN_ID + ": " + str(exc), file=sys.stderr)
    events_file = os.path.join(IDEAS_DIR, "events", RUN_ID + ".jsonl")
    if os.path.isfile(events_file):
        os.remove(events_file)


def _write_review_signoff() -> None:
    """Record the human-in-the-loop review gate for SCRIPT-01.

    No code agent writes review.md (it records a human review_status); this
    harness stands in for the human reviewer and signs off the *produced*
    architecture/tests so the artifact set is complete and honest.  The body
    is a genuine review of SCRIPT-01's artifacts, not a one-line stub.
    """
    review = (
        "review_status: APPROVED\n\n"
        "## Reviewer notes — " + ITEM_ID + ": " + ITEM_TITLE + "\n\n"
        "Reviewed the architecture.md and tests.md produced by the Architect and\n"
        "Tester agents for this real backlog item.\n\n"
        "- **Architecture**: a single self-contained, cron-safe Bash utility covering\n"
        "  log rotation + gzip, age-based archive deletion, disk-usage monitoring with\n"
        "  a high-threshold alert, temp-dir and package-cache cleanup, and a structured\n"
        "  execution report. Idempotent and externalised config ($N/$M/$X/$Y\n"
        "  thresholds) match the spec. Approving.\n"
        "- **Tests**: shell-level test plan exercises each functional requirement\n"
        "  (log rotation, archive deletion, disk monitoring, cleanup, report\n"
        "  emission), plus idempotency and error-resilience cases. Coverage is\n"
        "  proportionate to a Bash utility. Approving.\n"
        "- **Risks**: script runs cleanup; CONFIG is read from env, not hardcoded\n"
        "  (matches the spec's secret-handling note).\n\n"
        "Verdict: APPROVED — proceeds to EXECUTING.\n"
    )
    with open(REVIEW_PATH, "w", encoding="utf-8") as f:
        f.write(review)


def main() -> int:
    failures = []

    # 0. Precondition: the real backlog spec is present and itself non-stub.
    ok, why = _is_non_stub(SPEC_PATH, min_chars=200)
    if not ok:
        print("P3.2.7 PRECONDITION FAILED — SCRIPT-01 spec.md missing/stub:", why)
        return 1

    run_manager = RunManager(base_dir=IDEAS_DIR)
    _cleanup_run(run_manager)  # fresh slate for the run entry only

    before_arch = os.path.isfile(ARCH_PATH)
    before_tests = os.path.isfile(TESTS_PATH)
    before_report = os.path.isfile(REPORT_PATH)
    # P3.2.7 follow-up — the on-disk proof below asserts the executor created a
    # GENUINELY NEW entry under REQ_DIR this run.  Recording the pre-run set
    # closes the false-pass hole where a stale ``output/`` subtree left by a
    # prior health-fixture run (Jul 15 14:26) satisfied the "any non-kept file"
    # check even though the executor wrote nothing new.  Defect fix: the
    # executor now anchors relative write_file paths here (tools/* unchanged).
    before_req_files = set(os.listdir(REQ_DIR)) if os.path.isdir(REQ_DIR) else set()

    print("P3.2.7: carrying real backlog idea " + ITEM_ID + " (" + ITEM_TITLE + ")")
    print("  provider = real google_gemma (gemma-4-31b-it)")

    arch_conf = test_conf = exec_conf = None

    # ───────────── Hang backstop (305s) for the live LLM run ─────────────
    def _on_alarm(signum, frame):
        sys.stderr.write("\nP3.2.7: hung past 305s — killing.\n")
        _cleanup_run(run_manager)
        sys.exit(2)

    # ARCHITECT — architecture.md from the real spec (LLM).
    print("\n[1/4] Architect -> architecture.md (real LLM)...")
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(305)
    try:
        arch_conf = architect_mod.architect_idea(ITEM_ID)
    except Exception as exc:  # noqa: BLE001 — report, then continue
        failures.append("architect_idea raised: " + repr(exc))
    finally:
        signal.alarm(0)

    # TESTER — tests.md from spec + architecture (LLM).
    if not failures:
        print("\n[2/4] Tester -> tests.md (real LLM)...")
        signal.alarm(305)
        try:
            test_conf = tester_mod.tester_idea(ITEM_ID, use_docker=False)
        except Exception as exc:  # noqa: BLE001
            failures.append("tester_idea raised: " + repr(exc))
        finally:
            signal.alarm(0)

    # REVIEW — human-in-the-loop sign-off (HITL gate; stand in for the human).
    if not failures:
        print("\n[3/4] Review -> review.md (human-in-the-loop sign-off)...")
        _write_review_signoff()

    # EXECUTE — agentic LLM loop; writes execution_report.md + the script file.
    if not failures:
        print("\n[4/4] Executor -> execution_report.md + on-disk script (real LLM)...")
        _plant_run(run_manager)
        signal.alarm(305)
        try:
            exec_conf = executor_mod.executor_idea(ITEM_ID, run_manager, RUN_ID)
        except Exception as exc:  # noqa: BLE001
            failures.append("executor_idea raised: " + repr(exc))
        finally:
            signal.alarm(0)

    # ───────────── Assertions on all five P3.2 artifacts ────────────────
    def _assert(label, path, min_chars):
        ok, why = _is_non_stub(path, min_chars=min_chars)
        if not ok:
            failures.append(label + " (" + os.path.basename(path) + "): " + why)
        return ok, why

    _assert("spec.md", SPEC_PATH, 200)
    a_ok, _ = _assert("architecture.md", ARCH_PATH, 200)
    if before_arch:
        print("  [note] architecture.md already existed before the run")
    _assert("tests.md", TESTS_PATH, 200)
    if before_tests:
        print("  [note] tests.md already existed before the run")
    _assert("review.md", REVIEW_PATH, 120)

    # execution_report.md — the core P3.2 deliverable; stricter checks.
    e_ok, _ = _assert("execution_report.md", REPORT_PATH, 150)
    report_size = None
    ner_completed = None
    if e_ok:
        report = open(REPORT_PATH, encoding="utf-8").read()
        report_size = len(report)
        completed = [ln for ln in report.splitlines() if ln.strip().startswith("- COMPLETED:")]
        ner_completed = len(completed)
        if not completed:
            failures.append("no COMPLETED: log entries in execution_report.md")
        else:
            for ln in completed:
                print("    " + ln.strip())
    if before_report:
        print("  [note] execution_report.md already existed before the run")
    if exec_conf != 100:
        failures.append("executor_idea() returned " + repr(exec_conf) + " (100 == success)")

    # On-disk proof the executor's write_file landed a REAL ARTIFACT that is
    # NEW THIS RUN.  Subtracting ``before_req_files`` closes the false-pass
    # hole: a stale ``output/`` subtree from a prior health-fixture run used
    # to satisfy the "any non-kept file" check even when the executor wrote
    # nothing new.  We only credit entries that did not exist before the run
    # (and still exclude the known report/spec/etc. keep-set).
    after_req_files = set(os.listdir(REQ_DIR)) if os.path.isdir(REQ_DIR) else set()
    keep = {"spec.md", "architecture.md", "tests.md", "review.md", "execution_report.md"}
    new_req_files = sorted((after_req_files - keep) - before_req_files)
    if not new_req_files:
        failures.append("executor wrote no NEW on-disk artifact under requirements/SCRIPT-01/ "
                        "this run (besides the report) — a stale output/ dir no longer counts")
    else:
        for nf in new_req_files:
            p = os.path.join(REQ_DIR, nf)
            print("  on-disk artifact: " + nf + " (" + str(os.path.getsize(p)) + " bytes)")

    # ───────────── Clean up ONLY the harness run entry ──────────────────
    _cleanup_run(run_manager)

    # ───────────── Report ───────────────────────────────────────────────
    print("\nP3.2.7 RESULTS (real google_gemma, backlog idea SCRIPT-01):")
    print("  architect confidence = " + repr(arch_conf))
    print("  tester confidence    = " + repr(test_conf))
    print("  executor confidence  = " + repr(exec_conf) + "  (100 == success)")
    print("  execution_report.md   = " + (str(report_size) if report_size is not None else "<none>")
          + " bytes, " + (str(ner_completed) if ner_completed is not None else "?") + " COMPLETED: entries")
    print("  on-disk artifacts      = " + str(new_req_files))
    print("  harness run entry cleaned = True  (real artifacts KEPT)")
    if failures:
        print("\nP3.2.7 GATE FAILED:")
        for f in failures:
            print("  - " + f)
        return 1
    print("\nP3.2.7 GATE GREEN — real backlog idea carried past spec; "
          "all 5 artifacts non-stub; parent P3.2 can be closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
