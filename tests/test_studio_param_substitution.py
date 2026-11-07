"""SEC-12 (Studio part): {{var}} substitution in node params.

Defects (verified at HEAD 66340b8, ``_resolve_params``):
- Substitution ran on the ``json.dumps`` text of the whole params dict. A value
  containing a double quote or a backslash broke the JSON (crash) or, worse,
  injected extra keys/params into the adapter call.
- An absent variable was replaced with ``str(None)`` == ``"None"`` (``str(None)``
  is truthy, so the ``or match.group(0)`` fallback never ran). A Jira query with
  ``{{project}}`` absent became ``project = None``.

Fix under test:
- Substitution walks the params recursively and only touches string values; the
  structure and keys are never re-parsed, so values cannot inject params.
- A string that is exactly one placeholder resolves to the raw value (type kept).
- An absent variable keeps its placeholder text unchanged (documented decision:
  the literal ``"None"`` was a silent wrong-query bug; see the test docstrings).
"""
import asyncio
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import ExecutionState, NodeArchetype, QueryNode
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestResolveParams(unittest.TestCase):
    def setUp(self):
        vault = Mock(spec=SecretVault)
        vault.get_secret.return_value = {"access_token": "fake_token"}
        self.base = tempfile.mkdtemp(prefix="studio_params_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base,
            operator_registry=OperatorRegistry(vault=vault),
            studio_graph_manager=None,
            skill_manager=None,
            run_manager=None,
        )

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _resolve(self, params, state=None, loop_context=None):
        return self.engine._resolve_params(params, state or {}, loop_context)

    # -- quotes / backslashes -------------------------------------------------

    def test_value_with_double_quote_does_not_break_or_inject(self):
        state = {"name": 'x", "admin": true, "y": "z'}
        out = self._resolve({"jql": "summary ~ {{name}}"}, state)
        self.assertEqual(out, {"jql": 'summary ~ x", "admin": true, "y": "z'})
        self.assertNotIn("admin", out, "a quoted value must not create new param keys")

    def test_value_with_backslash_is_preserved(self):
        state = {"path": "C:\\temp\\new"}
        out = self._resolve({"q": "p={{path}}"}, state)
        self.assertEqual(out["q"], "p=C:\\temp\\new")

    def test_value_with_newline_and_unicode_preserved(self):
        state = {"text": "line1\nline2 \u2713"}
        out = self._resolve({"q": "{{text}}"}, state)
        self.assertEqual(out["q"], "line1\nline2 \u2713")

    # -- whole-placeholder keeps the raw type ----------------------------------

    def test_whole_placeholder_returns_raw_int(self):
        out = self._resolve({"max_results": "{{cap}}"}, {"cap": 5})
        self.assertEqual(out["max_results"], 5)
        self.assertIsInstance(out["max_results"], int)

    def test_whole_placeholder_returns_raw_list_and_dict(self):
        out = self._resolve({"ids": "{{ids}}", "meta": "{{meta}}"},
                            {"ids": [1, 2], "meta": {"a": "b"}})
        self.assertEqual(out["ids"], [1, 2])
        self.assertEqual(out["meta"], {"a": "b"})

    def test_whole_placeholder_none_value_is_kept_as_none_not_string(self):
        """A variable that exists with an explicit null resolves to None (not the
        string 'None' and not the placeholder text)."""
        out = self._resolve({"x": "{{nullish}}"}, {"nullish": None})
        self.assertIsNone(out["x"])

    def test_embedded_placeholder_stringifies_value(self):
        out = self._resolve({"q": "n = {{cap}}"}, {"cap": 5})
        self.assertEqual(out["q"], "n = 5")

    # -- nested structures -----------------------------------------------------

    def test_nested_dict_and_list_params_are_walked(self):
        params = {
            "filter": {"project": "{{proj}}", "labels": ["{{l1}}", "static"]},
            "limit": 10,
            "flag": True,
        }
        out = self._resolve(params, {"proj": "CORE", "l1": "urgent"})
        self.assertEqual(out, {
            "filter": {"project": "CORE", "labels": ["urgent", "static"]},
            "limit": 10,
            "flag": True,
        })

    def test_non_string_values_pass_through_unchanged(self):
        params = {"n": 3, "f": 1.5, "b": False, "none": None, "lst": [1, "a"]}
        self.assertEqual(self._resolve(params, {"x": "y"}), params)

    def test_keys_are_never_substituted(self):
        out = self._resolve({"{{k}}": "v"}, {"k": "injected"})
        self.assertEqual(out, {"{{k}}": "v"})

    def test_quoted_nested_value_does_not_inject_sibling_keys(self):
        state = {"v": '"}, "other": {"x": 1'}
        out = self._resolve({"outer": {"a": "{{v}}"}}, state)
        self.assertEqual(out, {"outer": {"a": '"}, "other": {"x": 1'}})
        self.assertNotIn("other", out)

    # -- absent variables ------------------------------------------------------

    def test_absent_variable_keeps_placeholder_text(self):
        out = self._resolve({"jql": "project = {{missing}}"}, {})
        self.assertEqual(out["jql"], "project = {{missing}}")
        self.assertNotIn("None", out["jql"])

    def test_absent_whole_placeholder_keeps_placeholder_text(self):
        out = self._resolve({"stage": "{{missing_var}}"}, {"other": "value"})
        self.assertEqual(out["stage"], "{{missing_var}}")

    def test_loop_context_precedence_over_state(self):
        out = self._resolve({"p": "{{k}}"}, {"k": "STATE"}, {"k": "LOOP"})
        self.assertEqual(out["p"], "LOOP")

    def test_dot_path_resolution_still_works(self):
        out = self._resolve({"team": "{{cfg.team}}"}, {"cfg": {"team": "CORE"}})
        self.assertEqual(out["team"], "CORE")

    def test_dot_path_absent_keeps_placeholder(self):
        out = self._resolve({"team": "{{cfg.team}}"}, {"cfg": {}})
        self.assertEqual(out["team"], "{{cfg.team}}")

    def test_falsy_variable_values_are_substituted_not_treated_as_absent(self):
        """0 and "" are real values; they must not fall back to the placeholder."""
        out = self._resolve({"a": "{{zero}}", "b": "x{{empty}}y"}, {"zero": 0, "empty": ""})
        self.assertEqual(out["a"], 0)
        self.assertEqual(out["b"], "xy")


class TestQueryNodeEndToEndSubstitution(unittest.TestCase):
    """The resolved params reach the adapter unchanged (no re-encoding)."""

    def setUp(self):
        vault = Mock(spec=SecretVault)
        vault.get_secret.return_value = {"access_token": "fake_token"}
        self.registry = OperatorRegistry(vault=vault)
        self.base = tempfile.mkdtemp(prefix="studio_params_e2e_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base,
            operator_registry=self.registry,
            studio_graph_manager=None,
            skill_manager=None,
            run_manager=None,
        )
        self.adapter = self.registry.adapters["jira_adapter"]
        self.adapter.list_tickets = AsyncMock(return_value=[])

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_adapter_receives_quoted_value_verbatim(self):
        node = QueryNode(
            node_id="q1", name="q1", archetype=NodeArchetype.QUERY,
            adapter="jira_adapter", action="list_tickets",
            params={"jql": 'summary ~ "{{term}}"'}, output_ref="t",
        )
        es = ExecutionState(graph_id="g", run_id="r", state={"term": 'a"b\\c'},
                            run_log=[], undefined_queue=[], loop_stack=[])
        _run(self.engine._execute_query_node(es, node))
        self.adapter.list_tickets.assert_awaited_once_with(jql='summary ~ "a"b\\c"')

    def test_adapter_receives_absent_placeholder_not_none(self):
        node = QueryNode(
            node_id="q2", name="q2", archetype=NodeArchetype.QUERY,
            adapter="jira_adapter", action="list_tickets",
            params={"jql": "project = {{project}}"}, output_ref="t",
        )
        es = ExecutionState(graph_id="g", run_id="r", state={},
                            run_log=[], undefined_queue=[], loop_stack=[])
        _run(self.engine._execute_query_node(es, node))
        self.adapter.list_tickets.assert_awaited_once_with(jql="project = {{project}}")


if __name__ == "__main__":
    unittest.main()
