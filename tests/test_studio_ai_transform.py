"""SC-Q1c: _execute_ai_transform_node direct coverage tests.

Target lines: studio_graph_engine.py:610-652

These tests cover the AITransform node handler:
- Inline-script success (result = input)
- Skill-ref success (loads persisted Skill.script)
- Skill not found -> ValueError
- No script and no skill_ref -> ValueError
- DependencyRequiredError (import pandas)
- SecurityError (import os)
- SafeExecutorError (result = 1/0)
- Context wiring: {"input", "state", "loop"} passed to SafeExecutor
"""
import asyncio
import tempfile
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    AITransformNode,
    NodeArchetype,
    Skill,
    CapabilityTier,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault
from api.managers.skill_manager import SkillManager
from api.executors.safe_executor import (
    SafeExecutorError,
    SecurityError,
    DependencyRequiredError,
)


def _make_engine_with_skill_manager():
    """Create engine with a real SkillManager backed by a temp dir."""
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)

    base_dir = tempfile.mkdtemp(prefix="studio_ai_transform_test_")
    skill_manager = SkillManager(base_dir)

    engine = PathStepGraphEngine(
        base_dir=base_dir,
        operator_registry=registry,
        studio_graph_manager=None,
        skill_manager=skill_manager,
        run_manager=None,
    )
    return engine, registry, skill_manager, base_dir


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestAITransformNodeExecution(unittest.TestCase):
    """Tests for _execute_ai_transform_node covering lines 610-652."""

    def setUp(self):
        self.engine, self.registry, self.skill_manager, self.base_dir = _make_engine_with_skill_manager()

    def _make_exec_state(self, state=None):
        """Create an ExecutionState with optional state (loop_context passed separately to the method)."""
        return ExecutionState(
            graph_id="g", run_id="r", state=state or {},
            run_log=[], undefined_queue=[], loop_stack=[],
        )

    # -------------------------------------------------------------------------
    # Inline script tests
    # -------------------------------------------------------------------------
    def test_inline_script_success_returns_input(self):
        """Inline script `result = input` returns the input value."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="result = input",
            skill_ref=None,
            input_ref="data",
            output_ref="transformed",
        )
        exec_state = self._make_exec_state(state={"data": {"key": "value", "count": 42}})

        result = _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertEqual(result, {"key": "value", "count": 42})

    def test_inline_script_can_access_state(self):
        """Inline script can read from `state` context variable."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="result = state.get('config', {}).get('multiplier', 1) * input['value']",
            skill_ref=None,
            input_ref="data",
            output_ref="transformed",
        )
        exec_state = self._make_exec_state(state={
            "data": {"value": 10},
            "config": {"multiplier": 3}
        })

        result = _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertEqual(result, 30)

    def test_inline_script_can_access_loop_context(self):
        """Inline script can read from `loop` context variable."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="result = loop['item']['id'] + '_processed'",
            skill_ref=None,
            input_ref="data",
            output_ref="transformed",
        )
        exec_state = self._make_exec_state(state={})

        result = _run(self.engine._execute_ai_transform_node(exec_state, node, loop_context={"item": {"id": "TICKET-123"}}))

        self.assertEqual(result, "TICKET-123_processed")

    def test_inline_script_all_three_context_vars_available(self):
        """All three context vars (input, state, loop) are available simultaneously."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script=(
                "result = {"
                "  'from_input': input['raw'],"
                "  'from_state': state.get('global_setting'),"
                "  'from_loop': loop.get('item_id')"
                "}"
            ),
            skill_ref=None,
            input_ref="source",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"global_setting": "GLOBAL-VAL", "source": {"raw": "INPUT-VAL"}})

        result = _run(self.engine._execute_ai_transform_node(exec_state, node, loop_context={"item_id": "LOOP-VAL"}))

        self.assertEqual(result, {
            "from_input": "INPUT-VAL",
            "from_state": "GLOBAL-VAL",
            "from_loop": "LOOP-VAL"
        })

    # -------------------------------------------------------------------------
    # Skill reference tests
    # -------------------------------------------------------------------------
    def test_skill_ref_success_loads_persisted_script(self):
        """Saved Skill is loaded from SkillManager and its script executes."""
        skill = Skill(
            skill_id="skill-123",
            name="Test Skill",
            description="Doubles the input",
            script="result = input * 2",
            input_schema={},
            output_schema={},
        )
        self.skill_manager.save_skill(skill)

        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script=None,
            skill_ref="skill-123",
            input_ref="data",
            output_ref="transformed",
        )
        exec_state = self._make_exec_state(state={"data": 21})

        result = _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertEqual(result, 42)

    def test_skill_ref_not_found_raises_value_error(self):
        """Referencing a non-existent skill_id raises ValueError."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script=None,
            skill_ref="nonexistent_skill",
            input_ref="data",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"data": "x"})

        with self.assertRaises(ValueError) as cm:
            _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertIn("Skill nonexistent_skill not found", str(cm.exception))

    def test_neither_script_nor_skill_ref_raises_value_error(self):
        """AITransform node with neither script nor skill_ref raises ValueError."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script=None,
            skill_ref=None,
            input_ref="data",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"data": "x"})

        with self.assertRaises(ValueError) as cm:
            _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertIn("neither script nor skill_ref", str(cm.exception))

    # -------------------------------------------------------------------------
    # SafeExecutor error propagation tests
    # -------------------------------------------------------------------------
    def test_dependency_required_error_propagates(self):
        """Import of non-whitelisted module (pandas) raises DependencyRequiredError."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="import pandas\nresult = 'unused'",
            skill_ref=None,
            input_ref="data",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"data": "x"})

        with self.assertRaises(DependencyRequiredError) as cm:
            _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertEqual(cm.exception.module_name, "pandas")

    def test_security_error_propagates(self):
        """Import of blocklisted module (os) raises SecurityError."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="import os\nresult = 'unused'",
            skill_ref=None,
            input_ref="data",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"data": "x"})

        with self.assertRaises(SecurityError) as cm:
            _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertIn("Blocked import due to security policy: os", str(cm.exception))

    def test_safe_executor_error_propagates(self):
        """Runtime error in script (division by zero) raises SafeExecutorError."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="result = 1 / 0",
            skill_ref=None,
            input_ref="data",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"data": "x"})

        with self.assertRaises(SafeExecutorError) as cm:
            _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertIn("Error during execution", str(cm.exception))
        self.assertIn("division by zero", str(cm.exception).lower())

    def test_syntax_error_raises_safe_executor_error(self):
        """Syntax error in script raises SafeExecutorError with context."""
        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="result = ",  # Invalid syntax
            skill_ref=None,
            input_ref="data",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"data": "x"})

        with self.assertRaises(SafeExecutorError) as cm:
            _run(self.engine._execute_ai_transform_node(exec_state, node))

        self.assertIn("Invalid Python syntax", str(cm.exception))

    # -------------------------------------------------------------------------
    # Context wiring integration test
    # -------------------------------------------------------------------------
    def test_context_wiring_includes_input_state_loop(self):
        """The script context dict has exactly input, state, loop keys.
        This pins the dict construction at studio_graph_engine.py:636-640."""
        # Capture what context was passed to SafeExecutor
        captured_context = {}

        original_execute = self.registry.safe_executor.execute

        def capturing_execute(code_string, context=None):
            captured_context.update(context or {})
            return original_execute(code_string, context)

        self.registry.safe_executor.execute = capturing_execute

        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script="result = 'ok'",
            skill_ref=None,
            input_ref="source",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"global": "STATE-VAL", "source": {"inner": "INPUT-VAL"}})

        _run(self.engine._execute_ai_transform_node(exec_state, node, loop_context={"item": "LOOP-VAL"}))

        # Verify all three context keys are present
        self.assertIn("input", captured_context)
        self.assertIn("state", captured_context)
        self.assertIn("loop", captured_context)

        # Verify their values
        self.assertEqual(captured_context["input"], {"inner": "INPUT-VAL"})
        self.assertEqual(captured_context["state"]["global"], "STATE-VAL")
        self.assertEqual(captured_context["state"]["source"], {"inner": "INPUT-VAL"})
        self.assertEqual(captured_context["loop"], {"item": "LOOP-VAL"})

    def test_skill_ref_context_wiring_same_as_inline(self):
        """Skill-ref execution uses the same context wiring as inline script."""
        skill = Skill(
            skill_id="skill-ctx",
            name="Context Test",
            description="",
            script="result = {'input_keys': list(input.keys()) if input else [], 'has_loop': bool(loop)}",
            input_schema={},
            output_schema={},
        )
        self.skill_manager.save_skill(skill)

        node = AITransformNode(
            node_id="ai1",
            name="ai1",
            archetype=NodeArchetype.AI_TRANSFORM,
            script=None,
            skill_ref="skill-ctx",
            input_ref="source",
            output_ref="out",
        )
        exec_state = self._make_exec_state(state={"global": "STATE-VAL", "source": {"a": 1}})

        result = _run(self.engine._execute_ai_transform_node(exec_state, node, loop_context={"item": "LOOP-VAL"}))

        self.assertEqual(result["input_keys"], ["a"])
        self.assertTrue(result["has_loop"])


if __name__ == "__main__":
    unittest.main()