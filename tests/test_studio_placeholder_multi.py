"""P2-2: several {{placeholders}} in one string must each be substituted.

The whole-string regex used a lazy ``(.*?)`` with anchors, so ``"{{a}} and {{b}}"``
matched as ONE placeholder named ``a}} and {{b`` and the text came back unchanged.
"""
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


class TestMultiPlaceholder(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_multi_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base,
            operator_registry=OperatorRegistry(vault=Mock(spec=SecretVault)),
            studio_graph_manager=None,
            skill_manager=None,
            run_manager=None,
        )

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def r(self, text, state=None, loop=None):
        return self.engine._resolve_params({"x": text}, state or {}, loop)["x"]

    def test_two_placeholders(self):
        self.assertEqual(self.r("{{a}} and {{b}}", {"a": "1", "b": "2"}), "1 and 2")

    def test_one_placeholder_with_text(self):
        self.assertEqual(self.r("project = {{p}} order by x", {"p": "CORE"}), "project = CORE order by x")

    def test_adjacent_placeholders(self):
        self.assertEqual(self.r("{{a}}{{b}}", {"a": "x", "b": "y"}), "xy")

    def test_absent_variable_in_multi_placeholder_string(self):
        self.assertEqual(self.r("{{a}} and {{missing}}", {"a": "1"}), "1 and {{missing}}")

    def test_all_absent_keeps_text(self):
        self.assertEqual(self.r("{{m1}} {{m2}}", {}), "{{m1}} {{m2}}")

    def test_whole_placeholder_keeps_type(self):
        self.assertEqual(self.r("{{n}}", {"n": 7}), 7)
        self.assertEqual(self.r("{{ids}}", {"ids": [1, 2]}), [1, 2])

    def test_whole_placeholder_with_spaces_keeps_type(self):
        self.assertEqual(self.r("{{ n }}", {"n": 7}), 7)

    def test_absent_whole_placeholder_unchanged(self):
        self.assertEqual(self.r("{{missing}}", {}), "{{missing}}")

    def test_mixed_loop_context_and_state(self):
        self.assertEqual(self.r("{{item}}-{{s}}", {"s": "S"}, {"item": "I"}), "I-S")

    def test_two_placeholders_never_collapse_to_whole_match(self):
        # Even when a bogus joined name exists in state, it must not be used.
        self.assertEqual(self.r("{{a}} and {{b}}", {"a": "1", "b": "2", "a}} and {{b": "WRONG"}), "1 and 2")


if __name__ == "__main__":
    unittest.main()
