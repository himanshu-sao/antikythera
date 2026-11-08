import pytest
from api.executors.safe_executor import SafeExecutor, SafeExecutorError, SecurityError, DependencyRequiredError

def test_safe_executor_whitelisted_import():
    """Test that whitelisted imports work."""
    code = """
import json
import re
data = {"hello": "world"}
result = json.dumps(data)
"""
    output = SafeExecutor.execute(code)
    assert output == '{"hello": "world"}'

def test_safe_executor_blocked_import():
    """Test that blocked imports raise SecurityError."""
    code = """
import os
result = os.listdir('.')
"""
    with pytest.raises(SecurityError, match="Blocked import due to security policy: os"):
        SafeExecutor.execute(code)

def test_safe_executor_dangerous_builtin():
    """Test that dangerous builtins are blocked."""
    code = """
result = eval("1+1")
"""
    with pytest.raises(SafeExecutorError): # Will raise SafeExecutorError during exec
        SafeExecutor.execute(code)

def test_safe_executor_syntax_error():
    """Test that syntax errors are caught."""
    code = """
import json
data = {"test": 
"""
    with pytest.raises(SafeExecutorError, match="Invalid Python syntax"):
        SafeExecutor.execute(code)

def test_safe_executor_context():
    """Test that context variables are available."""
    code = """
result = input_data * 2
"""
    context = {"input_data": 21}
    output = SafeExecutor.execute(code, context)
    assert output == 42

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# ---------------------------------------------------------------------------
# D7 — subprocess isolation.  Every call below runs the real child process.
# ---------------------------------------------------------------------------
import time

from api.executors import safe_executor as se


def test_result_types_survive_the_process_boundary():
    """The JSON protocol keeps tuples, sets, bytes and non-string keys."""
    code = """
result = {"t": (1, "a"), "s": {3}, "b": b"\\x00\\xff", "k": {1: "one"}, "fs": frozenset([2])}
"""
    out = SafeExecutor.execute(code)
    assert out["t"] == (1, "a") and isinstance(out["t"], tuple)
    assert out["s"] == {3} and isinstance(out["s"], set)
    assert out["b"] == b"\x00\xff" and isinstance(out["b"], bytes)
    assert out["k"] == {1: "one"}
    assert out["fs"] == frozenset([2]) and isinstance(out["fs"], frozenset)


def test_context_types_survive_the_process_boundary():
    code = """
result = [isinstance(input, tuple), isinstance(state, dict), loop]
"""
    context = {"input": (1, 2), "state": {"x": {"y": 1}}, "loop": {"item": b"z"}}
    out = SafeExecutor.execute(code, context)
    assert out == [True, True, {"item": b"z"}]


def test_unencodable_result_is_a_safe_executor_error():
    code = """
import json
result = object()
"""
    with pytest.raises(SafeExecutorError, match="cannot be returned"):
        SafeExecutor.execute(code)


def test_unencodable_context_is_rejected_in_the_parent():
    with pytest.raises(SafeExecutorError, match="cannot be passed"):
        SafeExecutor.execute("result = 1", {"bad": object()})


def test_script_without_result_returns_none():
    assert SafeExecutor.execute("x = 1") is None


def test_script_runs_in_a_separate_process(monkeypatch):
    """The child is a different process; the parent's pid is not visible."""
    seen = {}
    real_run = se.subprocess.Popen

    class _Spy(real_run):
        def __init__(self, argv, **kw):
            seen["argv"] = argv
            seen["kw"] = kw
            super().__init__(argv, **kw)

    monkeypatch.setattr(se.subprocess, "Popen", _Spy)
    assert SafeExecutor.execute("result = 7") == 7
    assert seen["argv"][0] == se.sys.executable
    assert seen["argv"][1] == "-I"
    assert seen["kw"]["env"] == {}
    assert seen["kw"]["start_new_session"] is True


def test_runtime_error_message_is_preserved():
    with pytest.raises(SafeExecutorError, match="division by zero"):
        SafeExecutor.execute("result = 1 / 0")


# --- T6: class-hierarchy escape ------------------------------------------------

_ESCAPE_PAYLOADS = [
    "result = ().__class__.__base__.__subclasses__()",
    "x = [c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'catch_warnings']\nresult = x",
    "result = (lambda: 0).__globals__",
    "result = getattr((), '__class__')",
    "result = __builtins__",
]


@pytest.mark.parametrize("payload", _ESCAPE_PAYLOADS)
def test_class_hierarchy_escape_raises_safe_executor_error(payload):
    """T6: a dunder/subclass walk is refused and no object leaks back."""
    with pytest.raises(SafeExecutorError):
        SafeExecutor.execute(payload)


def test_escape_is_blocked_by_the_child_even_if_the_parent_check_is_skipped():
    """Defence in depth: send the escape straight to the child, bypassing the
    parent's AST check.  The child must refuse it."""
    payload = {
        "code": "result = ().__class__.__base__.__subclasses__()",
        "context": {},
        "limits": {},
        "whitelist": sorted(SafeExecutor.WHITELIST),
        "blocklist": sorted(SafeExecutor.BLOCKLIST),
        "dangerous_builtins": sorted(SafeExecutor.DANGEROUS_BUILTINS),
    }
    with pytest.raises(SecurityError, match="Blocked attribute access"):
        SafeExecutor._run_in_subprocess(payload)


def test_getattr_is_not_available_in_the_child():
    """getattr is removed, so a string cannot reach a dunder attribute."""
    with pytest.raises(SafeExecutorError):
        SafeExecutor.execute("result = getattr(1, 'real')")


# --- T7: timeout ---------------------------------------------------------------

def test_default_timeout_is_ten_seconds():
    assert SafeExecutor.TIMEOUT_SECONDS == 10.0


def test_infinite_loop_is_killed_within_the_timeout(monkeypatch):
    """T7: ``while True`` is killed and reported as SafeExecutorError."""
    monkeypatch.setattr(SafeExecutor, "TIMEOUT_SECONDS", 2.0)
    started = time.monotonic()
    with pytest.raises(SafeExecutorError, match="timed out"):
        SafeExecutor.execute("while True:\n    pass\nresult = 1")
    elapsed = time.monotonic() - started
    assert elapsed < 10, f"kill took {elapsed:.1f}s"


def test_sleeping_script_is_killed(monkeypatch):
    """A blocking call that is not CPU-bound is also killed (time is wall-clock)."""
    monkeypatch.setattr(SafeExecutor, "TIMEOUT_SECONDS", 2.0)
    with pytest.raises(SafeExecutorError, match="timed out"):
        SafeExecutor.execute("import time\ntime.sleep(60)\nresult = 1")


# --- Import policy still enforced at the boundary ------------------------------

def test_child_refuses_a_blocked_import_even_without_the_parent_check():
    payload = {
        "code": "import os\nresult = 1",
        "context": {},
        "limits": {},
        "whitelist": sorted(SafeExecutor.WHITELIST),
        "blocklist": sorted(SafeExecutor.BLOCKLIST),
        "dangerous_builtins": sorted(SafeExecutor.DANGEROUS_BUILTINS),
    }
    with pytest.raises(SecurityError, match="Blocked import due to security policy: os"):
        SafeExecutor._run_in_subprocess(payload)


def test_relative_import_is_not_treated_as_a_dependency():
    """``from . import x`` is local; the old extractor ignored it and so do we."""
    assert SafeExecutor.extract_imports("from . import x") == set()


# --- P1-1: operator.attrgetter escape ------------------------------------------

def test_attrgetter_escape_payload_raises_safe_executor_error():
    """P1-1: ``operator.attrgetter`` takes dunder names as STRINGS, which the
    Attribute-node scan never saw.  The full escape (walk ``()`` to its class,
    to ``object``, to ``__subclasses__``) must be refused, not executed."""
    payload = (
        "import operator\n"
        "ag = operator.attrgetter\n"
        "cls = ag('__class__')(())\n"
        "base = ag('__base__')(cls)\n"
        "subclasses = ag('__subclasses__')(base)()\n"
        "result = len(subclasses)\n"
    )
    with pytest.raises(SafeExecutorError):
        SafeExecutor.execute(payload)


def test_operator_and_types_are_not_whitelisted():
    """P1-1: ``operator`` (attrgetter/itemgetter reach dunders by string) and
    ``types`` are off the whitelist; importing them is a dependency error."""
    assert "operator" not in SafeExecutor.WHITELIST
    assert "types" not in SafeExecutor.WHITELIST
    with pytest.raises(DependencyRequiredError):
        SafeExecutor.execute("import operator\nresult = 1")
    with pytest.raises(DependencyRequiredError):
        SafeExecutor.execute("import types\nresult = 1")


def test_type_is_not_available_in_the_child():
    """P1-1: ``type`` is removed from the child builtins, so ``type(x)`` can no
    longer be used to reach class internals (``type(x).__subclasses__()``)."""
    with pytest.raises(SafeExecutorError, match="name 'type' is not defined"):
        SafeExecutor.execute("result = type(1) is type('x')")


def test_itemgetter_dunder_string_is_rejected_by_the_parent(monkeypatch):
    """P1-1: the static check inspects CALL ARGUMENTS, not just Attribute
    nodes.  A dunder string passed to itemgetter is refused even if the import
    were somehow allowed (here: operator temporarily re-whitelisted)."""
    monkeypatch.setattr(SafeExecutor, "WHITELIST", SafeExecutor.WHITELIST | {"operator"})
    with pytest.raises(SecurityError, match="Blocked attribute access"):
        SafeExecutor.execute("import operator\nresult = operator.itemgetter('__class__')(())")


def test_attrgetter_dunder_string_is_rejected_by_the_child():
    """Defence in depth: the child re-runs the call-argument check even when
    the parent's import whitelist is bypassed entirely."""
    payload = {
        "code": "import operator\nresult = operator.attrgetter('__class__')(())",
        "context": {},
        "limits": {},
        "whitelist": sorted(SafeExecutor.WHITELIST | {"operator"}),
        "blocklist": sorted(SafeExecutor.BLOCKLIST),
        "dangerous_builtins": sorted(SafeExecutor.DANGEROUS_BUILTINS),
    }
    with pytest.raises(SecurityError, match="Blocked attribute access"):
        SafeExecutor._run_in_subprocess(payload)


def test_dunder_string_outside_attrgetter_calls_is_allowed():
    """A dunder-looking string literal on its own reaches no attribute; only
    attrgetter/itemgetter arguments turn it into an access."""
    assert SafeExecutor.execute('result = "__class__" in "x__class__y"') is True
    assert se._find_blocked_attribute("g = operator.itemgetter('name')") is None


def test_operator_free_script_still_runs():
    """The tightened whitelist/builtins must not break legitimate scripts."""
    code = """
import json, re, itertools
data = {"values": [1, 2, 3]}
result = {
    "sum": sum(data["values"]),
    "slug": re.sub(r"\\s+", "_", "a b c"),
    "pairs": list(itertools.combinations([1, 2], 2)),
    "dump": json.dumps(data),
}
"""
    out = SafeExecutor.execute(code)
    assert out == {
        "sum": 6,
        "slug": "a_b_c",
        "pairs": [(1, 2)],
        "dump": '{"values": [1, 2, 3]}',
    }
