import os
import json
import logging
import shlex
import subprocess
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# P3.2.6 Phase 1 — the executor no longer verifies its own work.  Verification
# of *correctness* is a separate concern (Phase 2 will run the spec's own
# tests against what the executor built).  In Phase 1 the executor's only
# honest assertion is "the artifact I was asked to write landed on disk and is
# not a stub/placeholder".  These markers and the size floor gate that
# assertion so a model can't false-complete a task by writing an obvious
# stand-in.  Deterministic and inspectable — not an LLM judgement.
# P3.2.6 Fix #1 — the executor judges "done" by (a) a stub-marker scan and
# (b) an on-disk read-back, NOT by a content byte floor.  An earlier
# ``_MIN_ARTIFACT_BYTES = 30`` floor rejected legitimate *small* artifacts
# (a 6-byte ``VERSION`` file, a one-line ``.gitignore``) as "stubs", which is
# what made the live gate's "Create VERSION file" task loop to exhaustion —
# the model kept emitting the correct (small) content, the tool kept rejecting
# it, and diagnostics kept suggesting a ``terminal echo`` (which can never
# complete a task either).  The right anti-stub axis is the substring scan
# below (genuine stand-ins) plus a trivial non-empty check, not a byte count.
_STUB_MARKERS = ("stub response", "# TODO", "placeholder", "notimplementederror")


def _is_stub_content(content: str) -> bool:
    """True if ``content`` is empty/whitespace or carries a stub/placeholder
    marker.  A small-but-real artifact (e.g. ``"0.1.0\\n"``) is NOT a stub.

    Fix #1 removed the blanket byte floor: a ``VERSION`` / one-line config
    *should* be small, and rejecting it on size alone produced the
    guaranteed-unwinnable loop seen in the 2026-07-15 live gate.  Marker
    matching is case-insensitive (markers lowered once here against the
    lowered content) so a ``"# TODO fill this in"`` comment is flagged
    regardless of the capitalisation of the marker constant.
    """
    if not content or not content.strip():
        return True
    lowered = content.lower()
    return any(m.lower() in lowered for m in _STUB_MARKERS)


# Root of the per-item requirements directories (``<root>/<item_id>/``).
# ``None`` (the default) means "derive it from the process cwd at call time",
# which is the historical behaviour: ``<cwd>/automation-ideas/requirements``.
# Tests (conftest ``isolate_data_dir``) set it to a tmp dir so the executor can
# never write into the real data folder; production code leaves it ``None``.
REQUIREMENTS_ROOT = None


def requirements_root() -> str:
    """Directory holding the per-item requirement folders.

    Returns :data:`REQUIREMENTS_ROOT` when set, else
    ``<cwd>/automation-ideas/requirements`` (resolved at call time).
    """
    if REQUIREMENTS_ROOT:
        return str(REQUIREMENTS_ROOT)
    return os.path.join(os.getcwd(), "automation-ideas", "requirements")


def item_requirements_dir(item_id: str) -> str:
    """``requirements_root()/<item_id>``: where an item's artifacts live."""
    return os.path.join(requirements_root(), item_id)


def _is_within(path: str, root: str) -> bool:
    """True if ``path`` equals ``root`` or lies beneath it (both already real)."""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives / mixed absolute+relative
        return False


def _resolve_item_path(path: str, item_id: str) -> str:
    """Resolve a tool path to a real path INSIDE the item's requirements dir.

    D7 confinement.  Every file tool (``write_file``, ``patch``,
    ``read_file``) funnels through here.  The rules:

    * An empty / ``None`` path is returned unchanged so the callers' existing
      ``if not path`` guards still fire.
    * An ABSOLUTE path is rejected outright (``ValueError``).  The executor
      used to pass these through, which let a model write anywhere the process
      could.  Relative paths are anchored at
      ``automation-ideas/requirements/<item_id>/``.
    * The joined path is resolved with :func:`os.path.realpath`, so ``..``
      segments AND symlinks (an in-dir link pointing at ``/etc``, or a
      dangling link whose target is outside) are followed before the
      containment check.  The result must stay inside the item dir, and the
      item dir itself must resolve to a direct child of the requirements root
      (so a hostile ``item_id`` such as ``../x`` or a symlinked item dir cannot
      widen the sandbox).

    The check is path-based, so a symlink swapped in between this check and the
    later open (TOCTOU) is not defended against; the executor is single-threaded
    per item and the item dir is not model-writable except through these tools,
    which never create symlinks.

    Raises ``ValueError`` with a reason; ``execute_tool`` turns it into the
    usual ``ERROR:`` result.
    """
    if not path:
        return path
    if os.path.isabs(path):
        raise ValueError(
            f"absolute path {path!r} is not allowed; use a path relative to the "
            f"item directory for {item_id}"
        )
    if not item_id or item_id in (".", "..") or os.sep in item_id or (os.altsep and os.altsep in item_id):
        raise ValueError(f"invalid item id {item_id!r}")

    root_real = os.path.realpath(requirements_root())
    item_real = os.path.realpath(os.path.join(root_real, item_id))
    if item_real == root_real or not _is_within(item_real, root_real):
        raise ValueError(f"item directory for {item_id} resolves outside the requirements root")

    resolved = os.path.realpath(os.path.join(item_real, path))
    if not _is_within(resolved, item_real):
        raise ValueError(
            f"path {path!r} escapes the item directory for {item_id}; "
            "use a path inside it"
        )
    return resolved


# --- terminal tool: no shell, program allowlist -----------------------------
# D7: the terminal tool never goes through a shell.  The command string is
# split with shlex and run as an argv list (shell=False), so pipes, redirects,
# ``;``, ``&&``, backticks and ``$(...)`` have no meaning: they would reach the
# program as literal arguments.  Only the programs below may be started.
ALLOWED_PROGRAMS = frozenset({"python", "python3", "pytest", "pip", "ls", "cat", "echo"})
# ``git`` is allowed only with one of these read-only subcommands, and the
# subcommand must be the first argument (so ``git -c ... status`` is refused).
ALLOWED_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log"})
# git options that write files, run external programs or redirect the repo.
_GIT_BLOCKED_OPTION_PREFIXES = (
    "--output", "--ext-diff", "--textconv", "--exec", "--git-dir",
    "--work-tree", "--no-index", "-c",
)
# Tokens that are shell operators on their own.  They would be inert here, but
# an LLM that emits them expects shell semantics, so refuse with a clear reason
# instead of silently passing them to the program as arguments.
_SHELL_OPERATOR_TOKENS = frozenset({
    "|", "||", "&", "&&", ";", ";;", ">", ">>", "<", "<<", "<<<", "2>", "2>>",
    "&>", "2>&1", ">&", "|&", "(", ")",
})
TERMINAL_TIMEOUT_SECONDS = 300


def _terminal_argv(command: Any) -> Tuple[List[str], str]:
    """Validate ``command`` and return ``(argv, "")`` or ``([], reason)``."""
    if not isinstance(command, str):
        return [], "command must be a string"
    try:
        argv = shlex.split(command)
    except ValueError as exc:  # unbalanced quote, trailing backslash, ...
        return [], f"could not parse command ({exc})"
    if not argv:
        return [], "empty command"
    program = argv[0]
    if program not in ALLOWED_PROGRAMS and program != "git":
        return [], (
            f"program {program!r} is not allowed; allowed: "
            f"{', '.join(sorted(ALLOWED_PROGRAMS))}, git (status/diff/log only)"
        )
    for tok in argv[1:]:
        if tok in _SHELL_OPERATOR_TOKENS:
            return [], (
                f"shell operator {tok!r} is not supported: commands run without a "
                "shell, so run one program per call and no pipes, redirects or separators"
            )
    if program == "git":
        sub = argv[1] if len(argv) > 1 else ""
        if sub not in ALLOWED_GIT_SUBCOMMANDS:
            return [], (
                f"git subcommand {sub!r} is not allowed; only "
                f"{', '.join(sorted(ALLOWED_GIT_SUBCOMMANDS))}"
            )
        for tok in argv[2:]:
            if tok.startswith(_GIT_BLOCKED_OPTION_PREFIXES):
                return [], f"git option {tok!r} is not allowed"
    return argv, ""

# Hard cap on how many workspace file entries get baked into an executor prompt.
# A multi-hundred-line file list (the old os.walk behaviour) ballooned every
# ``_perform_task_multi_turn`` prompt and is the most likely cause of the
# 60–120s ``bob`` timeouts/hangs observed during P3.2.  Keep this bounded.
WORKSPACE_FILES_CAP = 60

# Directories that are never useful workspace context for the executor —
# build/cache/dependency trees that only bloat the prompt.
_EXCLUDED_DIRS = {
    "venv", "node_modules", ".git", ".ui",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "dist", "build", "playwright-report", "test-results",
    ".cache", ".tox", ".nox",
}


def get_workspace_files(root: str = None) -> List[str]:
    """
    Return a bounded, relevant set of workspace file paths for the executor
    prompt — top-level files plus the ``api/`` source tree, sorted and
    capped at :data:`WORKSPACE_FILES_CAP` entries.

    The old implementation ``os.walk``-ed the whole repo (minus
    venv/node_modules/.git), baking a multi-hundred-line file list into every
    ``_perform_task_multi_turn`` turn.  That giant per-turn context is the
    most plausible cause of the 60–120s ``bob`` timeouts/hangs seen during
    P3.2, so this returns a small, predictable set instead.

    ``root`` defaults to ``os.getcwd()`` so the existing call site
    (``agents/executor.py``) is unchanged; passing an explicit ``root`` makes
    the function testable without depending on the process cwd.

    Exclude ``venv/``, ``node_modules/``, ``.git/``, ``.ui/`` and other
    build/cache dirs (see :data:`_EXCLUDED_DIRS`).  The result is sorted and
    truncated to :data:`WORKSPACE_FILES_CAP`.
    """
    root = os.path.abspath(root or os.getcwd())
    selected: List[str] = []

    def _rel(path: str) -> str:
        return os.path.relpath(path, root)

    def _excluded(entry: str) -> bool:
        return entry in _EXCLUDED_DIRS or os.path.basename(entry) in _EXCLUDED_DIRS

    # 1. Non-directory files at the top level (VERSION, README, Makefile, …).
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if os.path.isfile(full) and not _excluded(entry):
            selected.append(_rel(full))

    # 2. The api/ source tree — the executor's primary surface.  Prune
    #    excluded dirs from the descent so os.walk never enters them.
    api_root = os.path.join(root, "api")
    if os.path.isdir(api_root):
        for dirpath, dirs, files in os.walk(api_root):
            dirs[:] = sorted(d for d in dirs if d not in _EXCLUDED_DIRS)
            for f in sorted(files):
                if not _excluded(f):
                    selected.append(_rel(os.path.join(dirpath, f)))

    # 3. Dedup, sort, and cap.
    unique_sorted = sorted(set(selected))
    return unique_sorted[:WORKSPACE_FILES_CAP]

def get_tools_description() -> str:
    """
    Returns a string description of available tools for the LLM.
    """
    return """
Available Tools:
- `terminal(command)`: Run ONE program (no shell: no pipes, redirects, `;` or `&&`). Allowed programs: python, python3, pytest, pip, ls, cat, echo, and git with status/diff/log only. Returns stdout/stderr.
- `write_file(path, content)`: Write content to a file. The path must be RELATIVE (it is anchored at the item's requirements directory; absolute paths and `..` escapes are rejected).
- `patch(path, old_string, new_string)`: Find and replace text in a file (relative path, same rules).
- `read_file(path)`: Read the contents of a file (relative path, same rules).

You must respond with a JSON object representing the tool call.
Example response:
{"tool": "terminal", "args": {"command": "ls -la"}}
"""

def execute_tool(tool_name: str, args: Dict[str, Any], item_id: str) -> Tuple[bool, str]:
    """
    Executes a specific tool using native Python system calls.

    Returns ``(is_done, result_text)``.  ``is_done=True`` signals the executor
    loop that the current task is complete (a COMPLETED entry is logged and we
    move to the next planned task).

    P3.2.6 Phase 1 — the executor does **not** verify its own work.  These
    done-semantics assert only "the artifact I was asked to write landed on
    disk and is not a stub/placeholder", never "the work is correct".
    Verification of correctness is Phase 2 (a real verifier runs the spec's
    own tests, out of scope here).  Completion semantics per tool:

    * ``write_file``  -> done when the write succeeds, the content passes the
      ``_is_stub_content`` scan (non-empty + free of ``_STUB_MARKERS``), AND a
      read-back confirms the bytes round-tripped to disk.  Small-but-real
      artifacts (a 6-byte ``VERSION`` file) complete — Fix #1 dropped the old
      ``_MIN_ARTIFACT_BYTES`` byte floor that wrongly rejected them.
    * ``patch``       -> done when the patch lands (old_string found and
      replaced).
    * ``terminal``    -> **never** ``is_done``.  A shell command, even a
      successful one, is recon / a side-effect that feeds the next turn —
      it is NOT proof the task is complete.  (Old behaviour ran ``pytest``-
      shape commands as a self-verifier and looped on ``ls``; removed.)
    * ``read_file``   -> never done on its own; information-gathering for the
      next turn.

    Security (D7): ``terminal`` runs an argv list with ``shell=False`` and only
    for allowlisted programs (see :data:`ALLOWED_PROGRAMS`); file tools reject
    absolute paths and anything that resolves outside the item directory (see
    :func:`_resolve_item_path`).  The allowlist is not a sandbox: ``python`` and
    ``pip`` can still run arbitrary code as the current user.
    """
    try:
        if tool_name == "terminal":
            cmd = args.get("command", "ls")
            argv, reason = _terminal_argv(cmd)
            if not argv:
                return False, f"ERROR: terminal command rejected: {reason}"
            # shell=False: the argv list goes straight to execve.
            process = subprocess.run(
                argv, shell=False, capture_output=True, text=True,
                timeout=TERMINAL_TIMEOUT_SECONDS,
            )
            output = process.stdout if process.stdout else ""
            error = process.stderr if process.stderr else ""

            if process.returncode != 0:
                return False, f"ERROR: {error or output}"

            # Never assert done from a shell command (see docstring).  Feed the
            # output back as recon for the next turn.
            return False, f"TOOL RESULT (terminal):\n{output}"

        elif tool_name == "write_file":
            path = _resolve_item_path(args.get("path") or "", item_id)
            content = args.get("content", "")
            if not path: return False, "ERROR: No path provided"

            if _is_stub_content(content):
                return False, (
                    "ERROR: write_file content is empty or a stub/placeholder. "
                    "Write the full intended file contents (a small but real "
                    f"artifact is fine; got {len((content or '').strip())} non-empty bytes)."
                )

            # os.path.dirname("") == "" and makedirs("") raises; guard it.
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            # P3.2.6 Fix #1 — self-verify by read-back.  "Done" is observable
            # from the filesystem, not a content-size heuristic.  A model
            # false-completing by writing a stand-in is already blocked by the
            # ``_is_stub_content`` scan above; this read-back proves the bytes
            # we intended actually round-tripped to disk (catches a path that
            # silently failed to write / a filesystem race).  A small REAL file
            # — the case the old byte floor wrongly rejected — now completes
            # because the stub scan no longer size-gates it.
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    landed = f.read()
            except OSError as exc:
                return False, f"ERROR: wrote {path} but could not read it back: {exc}"
            if landed != content:
                return False, (
                    f"ERROR: write to {path} did not round-trip "
                    f"(wrote {len(content)} bytes, read back {len(landed)})."
                )
            return True, f"SUCCESS: Wrote to {path}"

        elif tool_name == "patch":
            path = _resolve_item_path(args.get("path") or "", item_id)
            old_string = args.get("old_string")
            new_string = args.get("new_string")
            if not path or old_string is None: return False, "ERROR: Path or old_string missing"

            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()

            if old_string not in text:
                return False, f"ERROR: old_string not found in {path}"

            updated_text = text.replace(old_string, new_string)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_text)
            return True, f"SUCCESS: Patched {path}"

        elif tool_name == "read_file":
            path = _resolve_item_path(args.get("path") or "", item_id)
            if not path: return False, "ERROR: No path provided"

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return False, f"FILE CONTENT ({path}):\n{content}"

        else:
            logger.error(f"[{item_id}] Unknown tool: {tool_name}")
            return False, f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"[{item_id}] Tool execution error: {str(e)}")
        return False, f"ERROR: {str(e)}"
