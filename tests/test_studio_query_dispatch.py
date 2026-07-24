"""T5-pre1 / Gap 2: headless Query node must honor node.action + list/vector dispatch.

Gap (verified at HEAD 9a89fe7): `_execute_query_node` hardcoded `operator_id:
"fetch_resource"` and packed `node.action` into `config`, but OperatorRegistry
dispatches on `operator_id` (-> `fetch`) and never consults `action`. So the dec #28
list/vector actions added to the adapters (jira.list_tickets, internal.list_items,
...) were unreachable on the headless AND interactive preview path — FanOut would
see a non-list and iterate nothing.

These tests pin the fix: a Query node with action=`list_tickets` must call
`adapter.list_tickets(**params)` directly and store the returned list under
`output_ref`, so a downstream FanOut iterates real items. The dict-shaped
`list_items` return (`{"items": [...]}`) is reachable via a dot-path source.
"""
import asyncio
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    QueryNode,
    NodeArchetype,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _make_engine():
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)
    import tempfile

    base_dir = tempfile.mkdtemp(prefix="studio_engine_test_")
    # Managers aren't exercised by the node handlers under test; pass them None
    # — the handlers only touch operator_registry + exec_state.
    engine = PathStepGraphEngine(
        base_dir=base_dir,
        operator_registry=registry,
        studio_graph_manager=None,
        skill_manager=None,
        run_manager=None,
    )
    return engine, registry


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestQueryNodeActionDispatch(unittest.TestCase):
    def setUp(self):
        self.engine, self.registry = _make_engine()

    def test_list_tickets_action_calls_adapter_method_not_fetch(self):
        """A Query node with action=list_tickets must dispatch to the adapter's
        list_tickets coroutine directly, not via fetch_resource->fetch."""
        adapter = self.registry.adapters["jira_adapter"]
        calls = {"fetch": 0, "list_tickets": 0}

        async def fake_fetch(resource_id=None, params=None):
            calls["fetch"] += 1
            return {}

        async def fake_list_tickets(jql="order by created DESC", max_results=50):
            calls["list_tickets"] += 1
            return [{"key": "PROJ-1"}, {"key": "PROJ-2"}]

        adapter.fetch = fake_fetch
        adapter.list_tickets = fake_list_tickets

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_tickets",
            params={"jql": "project = PROJ", "max_results": 5},
            output_ref="tickets",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )

        result = _run(self.engine._execute_query_node(exec_state, node))

        self.assertEqual(calls["fetch"], 0, "fetch must NOT be called for a list action")
        self.assertEqual(calls["list_tickets"], 1, "list_tickets must be called once")
        self.assertEqual(result, [{"key": "PROJ-1"}, {"key": "PROJ-2"}])
        # Engine caller writes result under output_ref; verify it lands in state.
        self.engine._write_to_state(exec_state.state, node.output_ref, result)
        self.assertEqual(exec_state.state["tickets"], [{"key": "PROJ-1"}, {"key": "PROJ-2"}])

    def test_list_items_dict_shape_reachable_via_dot_path(self):
        """internal.list_items returns {"items": [...]}. A FanOut whose source
        is '<output_ref>.items' must reach the list through _get_nested_value."""
        adapter = self.registry.adapters["internal_adapter"]

        async def fake_list_items(stage=None):
            return {"items": [{"id": "A"}, {"id": "B"}, {"id": "C"}]}

        adapter.list_items = fake_list_items

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="internal_adapter",
            action="list_items",
            params={},
            output_ref="board",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        result = _run(self.engine._execute_query_node(exec_state, node))
        self.engine._write_to_state(exec_state.state, node.output_ref, result)

        # FanOut resolves source "board.items" -> the list inside the dict.
        resolved = self.engine._get_nested_value(exec_state.state, "board.items")
        self.assertEqual(resolved, [{"id": "A"}, {"id": "B"}, {"id": "C"}])
        self.assertIsInstance(resolved, list, "dot-path must resolve to the list FanOut can iterate")

    def test_unknown_action_falls_back_to_fetch_path(self):
        """An action that isn't a list/vector adapter method keeps the legacy
        fetch_resource->fetch path (do not break single-resource queries)."""
        adapter = self.registry.adapters["jira_adapter"]

        async def fake_fetch(resource_id=None, params=None):
            return {"key": "PROJ-1"}

        adapter.fetch = fake_fetch

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_resources",
            params={},
            output_ref="one",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        result = _run(self.engine._execute_query_node(exec_state, node))
        self.assertEqual(result, {"key": "PROJ-1"})

    # --- SC-Q1a extension: sync list/vector dispatch ---------------------------
    # The 3 tests above exercise the *coroutine* half of line 510
    # (`await method(**params) if inspect.iscoroutinefunction(method) else ...`).
    # The list/vector actions shipped on the real adapters are all async
    # coroutines, so the synchronous `else` branch (a plain-function adapter
    # method) is unexercised, as are {{var}} param resolution and the
    # adapter-absent fallback. These three tests close those gaps.

    def test_sync_list_action_uses_non_coroutine_branch(self):
        """A list/vector action that is a plain (non-coroutine) function must
        take the `else method(**params)` branch — it is called synchronously,
        not awaited. Pins the inspect.iscoroutinefunction()==False half of
        the dispatch ternary at studio_graph_engine.py:510."""
        adapter = self.registry.adapters["jira_adapter"]

        def fake_list_projects(project_key="*"):  # plain function, NOT async
            return [{"key": f"{project_key}-1"}, {"key": f"{project_key}-2"}]

        adapter.list_projects = fake_list_projects

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_projects",
            params={"project_key": "ENG"},
            output_ref="projects",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        result = _run(self.engine._execute_query_node(exec_state, node))
        self.assertEqual(result, [{"key": "ENG-1"}, {"key": "ENG-2"}])
        # _is_list_vector_action must still recognize the sync function (it
        # checks `inspect.isfunction(method)` — a coroutine is NOT a bare
        # function, a plain def IS).
        self.assertTrue(
            self.engine._is_list_vector_action(adapter, "list_projects"),
            "a plain function adapter method must qualify as a list/vector action",
        )

    def test_param_resolution_substitutes_state_and_loop_context(self):
        """{{var}} placeholders in node.params are resolved from state (and
        loop_context takes priority over state when both name a key). This
        exercises _resolve_params at studio_graph_engine.py:504/843 — the
        real-adapter tests above pass params literally, never templated."""
        adapter = self.registry.adapters["jira_adapter"]

        seen = {}

        async def fake_list_tickets(**kwargs):
            seen.update(kwargs)
            return [{"key": "PROJ-1"}]

        adapter.list_tickets = fake_list_tickets

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_tickets",
            # jql carries a {{project_key}} placeholder; max_results carries
            # {{cap}}. project_key + cap both come from state, but project_key
            # is ALSO loop_context — loop_context must win.
            params={"jql": "project = {{project_key}}", "max_results": "{{cap}}"},
            output_ref="tickets",
        )
        exec_state = ExecutionState(
            graph_id="g",
            run_id="r",
            state={"project_key": "STATE-PROJ", "cap": 5},
            run_log=[],
            undefined_queue=[],
            loop_stack=[],
        )
        # loop_context provides project_key (priority over state); cap is
        # state-only.
        loop_context = {"project_key": "LOOP-PROJ"}

        result = _run(self.engine._execute_query_node(exec_state, node, loop_context))
        self.assertEqual(result, [{"key": "PROJ-1"}])
        self.assertEqual(seen["jql"], "project = LOOP-PROJ", "loop_context must win over state")
        self.assertEqual(seen["max_results"], "5", "state-only var resolves from state")

        # Edge: a {{var}} absent from both loop_context and state → _get_nested_value
        # returns None → `str(None)` → "None" (the regex replacer falls back
        # to that rather than dropping the placeholder). Pin this so a future
        # refactor that changes the fallback is caught.
        node2 = QueryNode(
            node_id="q2",
            name="q2",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_tickets",
            params={"jql": "x = {{missing}}"},
            output_ref="t2",
        )
        exec_state2 = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        _run(self.engine._execute_query_node(exec_state2, node2))
        self.assertEqual(seen["jql"], "x = None", "unresolved var must become 'None', not be dropped")
        # Dot-path state resolution: {{cfg.team}} reads state["cfg"]["team"].
        node3 = QueryNode(
            node_id="q3",
            name="q3",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_tickets",
            params={"jql": "team = {{cfg.team}}"},
            output_ref="t3",
        )
        exec_state3 = ExecutionState(
            graph_id="g", run_id="r", state={"cfg": {"team": "CORE"}}, run_log=[],
            undefined_queue=[], loop_stack=[],
        )
        _run(self.engine._execute_query_node(exec_state3, node3))
        self.assertEqual(seen["jql"], "team = CORE", "dot-path var must resolve through nested state")

    def test_adapter_not_registered_falls_through_to_fetch_and_raises(self):
        """A Query node whose node.adapter is NOT in registry.adapters has
        adapter==None, so _is_list_vector_action is skipped (its guard is
        `adapter is not None and ...`). The handler then falls through to the
        fetch_resource->fetch path, which (in _execute_single_step) raises
        ValueError("Unsupported adapter: ...") — NOT a KeyError from the
        list branch. Pins that the absent-adapter case is handled by the
        fallback, not by dereferencing a None adapter."""
        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="ghost_adapter",  # not in registry.adapters
            action="list_tickets",
            params={"jql": "project = X"},
            output_ref="tickets",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )

        # The list branch guard fails on adapter is None, so it never touches
        # _is_list_vector_action with a None adapter (that would be an
        # AttributeError on getattr(None, action)). Confirm the dispatch
        # reaches OperatorRegistry, which rejects the unknown adapter.
        with self.assertRaises(ValueError) as cm:
            _run(self.engine._execute_query_node(exec_state, node))
        self.assertIn("ghost_adapter", str(cm.exception))
        # And the engine genuinely skipped the list branch: confirm
        # _is_list_vector_action would be a no-op here because the caller's
        # `adapter is not None` guard short-circuits before it.
        self.assertNotIn("ghost_adapter", self.registry.adapters)


if __name__ == "__main__":
    unittest.main()
