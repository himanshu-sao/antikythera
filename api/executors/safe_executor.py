"""SafeExecutor: run untrusted Python snippets in a separate, short-lived process.

D7 hardening.  Each call to :meth:`SafeExecutor.execute`:

1. Parses the snippet and applies the static checks in the parent: the import
   allowlist (``WHITELIST`` / ``BLOCKLIST``) and a ban on dunder attribute
   access (``().__class__.__subclasses__()`` style escapes).
2. Writes a small runner script to a private temp directory and starts the
   venv interpreter as ``python -I runner.py in.json out.json``.  ``-I`` ignores
   environment variables, the user site and the script directory, and the child
   gets an empty environment and a temp working directory.
3. The child applies best-effort rlimits (CPU, file size, and address space
   where the OS allows it), re-runs the attribute check, builds a restricted
   ``__builtins__`` (no ``eval``/``exec``/``open``/``getattr``...) with a safe
   ``__import__``, executes the snippet with the ``{input, state, loop}``
   context, and writes the result to ``out.json``.
4. The parent kills the whole process group if the run exceeds
   :attr:`SafeExecutor.TIMEOUT_SECONDS` (default 10 s) and raises
   :class:`SafeExecutorError`.

The result crosses the process boundary as JSON with a small tagged encoding
so that tuples, sets, frozensets, bytes and non-string dict keys keep their
types.  Any other value is rejected with :class:`SafeExecutorError`.  Nothing
is unpickled, so the child cannot hand the parent an object to execute.

The public API is unchanged: ``SafeExecutor.execute(code, context)``, the
``SafeExecutorError`` / ``SecurityError`` / ``DependencyRequiredError``
classes, and the ``extract_imports`` classmethod.
"""
import ast
import base64
import builtins  # noqa: F401  (kept for parity with older imports)
import inspect
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SafeExecutorError(Exception):
    """Base exception for SafeExecutor."""
    pass


class SecurityError(SafeExecutorError):
    """Raised when a dangerous operation is attempted."""
    pass


class DependencyRequiredError(SafeExecutorError):
    """Raised when an import is not in the whitelist."""
    def __init__(self, module_name: str):
        self.module_name = module_name
        super().__init__(f"Required dependency not installed: {module_name}")


# ---------------------------------------------------------------------------
# Tagged JSON codec.  Shared by the parent and the child: the child receives
# these functions as source text (see ``_RUNNER_BODY``), so the two sides
# cannot drift apart.
# ---------------------------------------------------------------------------

_TAG = "__sx__"


class _Unencodable(Exception):
    """A value cannot be represented across the process boundary."""


def _encode(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value) and _TAG not in value:
            return {k: _encode(v) for k, v in value.items()}
        return {_TAG: "dict", "v": [[_encode(k), _encode(v)] for k, v in value.items()]}
    if isinstance(value, tuple):
        return {_TAG: "tuple", "v": [_encode(v) for v in value]}
    if isinstance(value, frozenset):
        return {_TAG: "frozenset", "v": [_encode(v) for v in value]}
    if isinstance(value, set):
        return {_TAG: "set", "v": [_encode(v) for v in value]}
    if isinstance(value, (bytes, bytearray)):
        return {_TAG: "bytes", "v": base64.b64encode(bytes(value)).decode("ascii")}
    raise _Unencodable(type(value).__name__)


def _decode(value):
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, dict):
        if _TAG not in value:
            return {k: _decode(v) for k, v in value.items()}
        tag = value[_TAG]
        if tag == "tuple":
            return tuple(_decode(v) for v in value["v"])
        if tag == "set":
            return {_decode(v) for v in value["v"]}
        if tag == "frozenset":
            return frozenset(_decode(v) for v in value["v"])
        if tag == "bytes":
            return base64.b64decode(value["v"])
        if tag == "dict":
            return {_decode(k): _decode(v) for k, v in value["v"]}
        raise ValueError(f"unknown tag {tag!r}")
    return value


# ---------------------------------------------------------------------------
# Static attribute check.  Shared by the parent and the child.
# ---------------------------------------------------------------------------

def _find_blocked_attribute(code_string):
    """Return the first dunder attribute (or ``__builtins__`` name) the snippet
    uses, or None.  Blocks the ``__class__`` / ``__subclasses__`` escape family.

    P1-1: also inspects CALL ARGUMENTS.  ``operator.attrgetter`` /
    ``operator.itemgetter`` take attribute names as *strings*, which the
    ``Attribute``-node scan above never sees; a string argument containing a
    double underscore reaches the same dunder attributes, so any call spelled
    ``attrgetter(...)`` / ``itemgetter(...)`` (attribute or bare name) with
    such a string is refused too.
    """
    tree = ast.parse(code_string)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                return node.attr
        elif isinstance(node, ast.Name) and node.id == "__builtins__":
            return node.id
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                fname = func.attr
            elif isinstance(func, ast.Name):
                fname = func.id
            else:
                fname = None
            if fname in ("attrgetter", "itemgetter"):
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                            and "__" in arg.value):
                        return f"{fname}({arg.value!r})"
    return None


# ---------------------------------------------------------------------------
# Child-side runner.  Written to a temp file and executed with ``python -I``.
# The codec and attribute check are pulled in as source, not re-typed.
# ---------------------------------------------------------------------------

_RUNNER_BODY = r'''
import ast, base64, builtins, json, sys


class _SecurityViolation(Exception):
    pass


class _MissingDependency(Exception):
    def __init__(self, module_name):
        self.module_name = module_name
        super().__init__(module_name)


def _apply_limits(limits):
    """Best effort: lower the rlimits that this OS allows.  Unsupported or
    refused limits are skipped silently (macOS refuses RLIMIT_AS / RLIMIT_DATA)."""
    try:
        import resource
    except ImportError:
        return
    targets = {
        "cpu": ("RLIMIT_CPU",),
        "fsize": ("RLIMIT_FSIZE",),
        "mem": ("RLIMIT_AS", "RLIMIT_DATA"),
    }
    for key, names in targets.items():
        value = limits.get(key)
        if not value:
            continue
        for name in names:
            lim = getattr(resource, name, None)
            if lim is None:
                continue
            try:
                resource.setrlimit(lim, (value, value))
            except (ValueError, OSError):
                continue


def _make_globals(cfg):
    dangerous = set(cfg["dangerous_builtins"])
    whitelist = set(cfg["whitelist"])
    blocklist = set(cfg["blocklist"])

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        top = name.split(".")[0]
        if top in blocklist:
            raise _SecurityViolation(f"Blocked import due to security policy: {top}")
        if top not in whitelist:
            raise _MissingDependency(top)
        return __import__(name, globals, locals, fromlist, level)

    safe_builtins = {n: getattr(builtins, n) for n in dir(builtins) if n not in dangerous}
    safe_builtins["__import__"] = _safe_import
    g = {"__builtins__": safe_builtins}
    for module in sorted(whitelist):
        try:
            g[module] = __import__(module)
        except ImportError:
            pass
    return g


def _main(in_path, out_path):
    with open(in_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    _apply_limits(payload.get("limits", {}))
    try:
        blocked = _find_blocked_attribute(payload["code"])
        if blocked:
            raise _SecurityViolation(f"Blocked attribute access: {blocked}")
        code = compile(payload["code"], "<string>", "exec")
        g = _make_globals(payload)
        g.update(_decode(payload["context"]))
        exec(code, g)
        reply = {"status": "ok", "result": _encode(g.get("result", None))}
    except _MissingDependency as exc:
        reply = {"status": "error", "kind": "dependency", "module": exc.module_name,
                 "message": f"Required dependency not installed: {exc.module_name}"}
    except _SecurityViolation as exc:
        reply = {"status": "error", "kind": "security", "message": str(exc)}
    except SyntaxError as exc:
        reply = {"status": "error", "kind": "syntax", "message": f"Invalid Python syntax: {exc}"}
    except _Unencodable as exc:
        reply = {"status": "error", "kind": "runtime",
                 "message": f"Error during execution: result of type {exc} cannot be returned from the script"}
    except Exception as exc:  # noqa: BLE001 - every script error is reported
        reply = {"status": "error", "kind": "runtime", "message": f"Error during execution: {exc}"}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(reply, fh)


if __name__ == "__main__":
    _main(sys.argv[1], sys.argv[2])
'''

_RUNNER_SOURCE = "\n".join([
    "import base64, ast",
    inspect.getsource(_Unencodable),
    inspect.getsource(_encode),
    inspect.getsource(_decode),
    inspect.getsource(_find_blocked_attribute),
    "_TAG = " + repr(_TAG),
    _RUNNER_BODY,
])


def _kill_process_group(proc: "subprocess.Popen") -> None:
    """Kill the child and anything it started (it runs in its own session)."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


class SafeExecutor:
    """
    A safe executor for running untrusted Python code.

    - Parent-side: AST import allowlist and a dunder-attribute ban.
    - Child-side: a separate ``python -I`` process with a timeout, best-effort
      rlimits, an empty environment, and a restricted ``__builtins__``.
    """

    # Wall-clock limit for one script, including interpreter start-up.
    TIMEOUT_SECONDS: float = 10.0
    # Best-effort address-space cap for the child (skipped where unsupported).
    MEMORY_LIMIT_BYTES: int = 512 * 1024 * 1024
    # Largest file the child may write.
    FILE_SIZE_LIMIT_BYTES: int = 16 * 1024 * 1024

    # Whitelist of allowed top-level modules.
    # These are considered safe and do not require explicit installation approval.
    # P1-1: ``operator`` and ``types`` are deliberately ABSENT.  ``operator``
    # exposes ``attrgetter``/``itemgetter``, which take attribute names as
    # strings and so bypass the AST dunder-attribute ban (the static check
    # below also refuses dunder strings in those calls, but the module stays
    # off the whitelist as the primary defence).  ``types`` hands out
    # ``FunctionType``/``MethodType``, another route to class internals.
    WHITELIST: Set[str] = {
        'json', 're', 'httpx', 'datetime', 'yaml', 'typing', 'collections',
        'math', 'random', 'string', 'time', 'csv', 'decimal', 'fractions',
        'statistics', 'itertools', 'functools', 'hashlib', 'base64', 'uuid',
        'ipaddress', 'textwrap', 'difflib', 'pprint', 'copy',
        'enum', 'dataclasses', 'contextlib', 'queue', 'heapq', 'bisect',
        'array', 'weakref', 'keyword', 'tokenize',
    }

    # Blocklist of modules that are never allowed due to security risks.
    BLOCKLIST: Set[str] = {
        'os', 'sys', 'subprocess', 'shutil', 'multiprocessing', 'threading',
        'socket', 'urllib', 'requests', 'http.client', 'ftplib', 'telnetlib',
        'imaplib', 'poplib', 'smtplib', 'ssl', 'signal', 'resource',
        'pickle', 'marshal', 'shelve', 'dbm', 'sqlite3',
        'ctypes', 'imp', 'importlib', 'pkgutil', 'modulefinder',
        'runpy', 'site', 'user', 'builtins', '__main__', 'warnings',
    }

    # Built-ins removed from the child's execution environment.  getattr,
    # setattr and delattr are removed so a string cannot be used to reach a
    # dunder attribute after the static check.  P1-1: ``type`` is removed too
    # (``type(x).__subclasses__()`` is the same class-hierarchy escape).
    DANGEROUS_BUILTINS: Set[str] = {
        'eval', 'exec', 'compile', 'open', 'input', 'help', 'exit', 'quit',
        'copyright', 'credits', 'license', '__import__',
        'getattr', 'setattr', 'delattr', 'globals', 'locals', 'vars', 'breakpoint',
        'type',
    }

    @classmethod
    def extract_imports(cls, code_string: str) -> Set[str]:
        """
        Extract all top-level module names imported in the code string.
        Returns a set of module names (as strings).
        """
        try:
            tree = ast.parse(code_string)
        except SyntaxError as e:
            raise SafeExecutorError(f"Invalid Python syntax: {e}") from e

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    imports.add(module)
            elif isinstance(node, ast.ImportFrom):
                # Relative imports (node.module is None or level > 0) are local.
                if node.module and node.level == 0:
                    module = node.module.split('.')[0]
                    imports.add(module)
        return imports

    @classmethod
    def _check_imports(cls, imports: Set[str]) -> Optional[str]:
        """
        Check a set of imports against the whitelist and blocklist.
        Returns the first problematic module name (for blocklist or not in whitelist) or None if all are safe.
        """
        for module in imports:
            if module in cls.BLOCKLIST:
                return module  # Blocked due to security
            if module not in cls.WHITELIST:
                return module  # Not in whitelist, requires approval
        return None  # All imports are allowed

    @classmethod
    def _limits(cls) -> Dict[str, int]:
        return {
            "cpu": int(cls.TIMEOUT_SECONDS) + 2,
            "fsize": cls.FILE_SIZE_LIMIT_BYTES,
            "mem": cls.MEMORY_LIMIT_BYTES,
        }

    @classmethod
    def _run_in_subprocess(cls, payload: Dict[str, Any]) -> Any:
        """Run ``payload`` (code + context) in a child process and return the
        decoded result.  Raises SafeExecutorError subclasses on any failure.

        Called by :meth:`execute` after the static checks.  Kept separate so
        tests can exercise the child-side checks directly.
        """
        workdir = tempfile.mkdtemp(prefix="safe_executor_")
        try:
            runner_path = os.path.join(workdir, "runner.py")
            in_path = os.path.join(workdir, "in.json")
            out_path = os.path.join(workdir, "out.json")
            with open(runner_path, "w", encoding="utf-8") as fh:
                fh.write(_RUNNER_SOURCE)
            with open(in_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)

            argv = [sys.executable, "-I", runner_path, in_path, out_path]
            proc = subprocess.Popen(
                argv,
                cwd=workdir,
                env={},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=cls.TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                _kill_process_group(proc)
                proc.communicate()
                raise SafeExecutorError(
                    f"Script timed out after {cls.TIMEOUT_SECONDS:g} seconds and was killed"
                )

            if not os.path.exists(out_path):
                tail = (stderr or b"").decode("utf-8", "replace")[-500:]
                raise SafeExecutorError(
                    f"Script process ended without a result (exit code {proc.returncode}): {tail.strip()}"
                )
            try:
                with open(out_path, encoding="utf-8") as fh:
                    reply = json.load(fh)
            except ValueError as exc:
                raise SafeExecutorError(f"Script process returned an unreadable result: {exc}") from exc
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        if reply.get("status") == "ok":
            return _decode(reply.get("result"))
        message = reply.get("message", "Script failed")
        kind = reply.get("kind")
        if kind == "dependency":
            raise DependencyRequiredError(reply.get("module", ""))
        if kind == "security":
            raise SecurityError(message)
        raise SafeExecutorError(message)

    @classmethod
    def execute(cls, code_string: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the given Python code string in a separate sandboxed process.
        Args:
            code_string: The Python code to execute.
            context: A dictionary of variables to make available in the code's namespace.
        Returns:
            The value of the ``result`` variable, or None if the script does not set it.
        Raises:
            SafeExecutorError: If the code is unsafe, fails, or times out.
            SecurityError / DependencyRequiredError: For blocked or missing imports.
        """
        if context is None:
            context = {}

        # Step 1: Extract imports (also reports syntax errors).
        imports = cls.extract_imports(code_string)

        # Step 2: Check for blocked or missing dependencies.
        problematic_module = cls._check_imports(imports)
        if problematic_module:
            if problematic_module in cls.BLOCKLIST:
                raise SecurityError(f"Blocked import due to security policy: {problematic_module}")
            else:
                raise DependencyRequiredError(problematic_module)

        # Step 3: Refuse dunder attribute access (class-hierarchy escapes).
        blocked = _find_blocked_attribute(code_string)
        if blocked:
            raise SecurityError(f"Blocked attribute access: {blocked}")

        # Step 4: Encode the context for the child.
        try:
            encoded_context = _encode(context)
        except _Unencodable as exc:
            raise SafeExecutorError(
                f"Context value of type {exc} cannot be passed to the script"
            ) from exc

        # Step 5: Run in the subprocess.
        payload = {
            "code": code_string,
            "context": encoded_context,
            "limits": cls._limits(),
            "whitelist": sorted(cls.WHITELIST),
            "blocklist": sorted(cls.BLOCKLIST),
            "dangerous_builtins": sorted(cls.DANGEROUS_BUILTINS),
        }
        return cls._run_in_subprocess(payload)


# Example usage (for manual checks):
if __name__ == "__main__":
    code = """
import json
data = {"test": 123}
result = json.dumps(data)
    """
    try:
        output = SafeExecutor.execute(code)
        print(f"Execution successful: {output}")
    except SafeExecutorError as e:
        print(f"Execution failed: {e}")
