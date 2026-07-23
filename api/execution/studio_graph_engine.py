"""
PathStepGraphEngine — Dedicated headless execution engine for Studio Graphs.

This is a NEW engine (dec #17) that leaves the two existing engines untouched
(zero regression risk to just-shipped WorkflowArchitect/BlueprintArchitect work).

Slice 1 scope (deterministic, no LLM at cron):
- Condition-first routing with reserved `signature: str` (dec #19)
- Fan-out via OperatorRegistry.loop_over
- AI-transform via SafeExecutor (mode=SCRIPT)
- Undefined queue (cap 100/graph, no auto-expiry, dec #20)
- Replay history (50 run logs + perpetual aggregate, dec #21)
- Cron wiring for simple graphs only (dec #7, #9)
- Real Jira writes at end of slice 1 (dec #16)

Shares model defs via api.models.studio import (dec #17).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from api.managers.studio_graph_manager import StudioGraphManager
from api.managers.skill_manager import SkillManager
from api.managers.run_manager import RunManager
from api.models.studio import (
    StudioGraph,
    StudioNode,
    GraphRunLog,
    NodeExecutionResult,
    ExecutionState,
    QueryNode,
    FanOutNode,
    AITransformNode,
    ConditionalActionNode,
    GraphEdge,
    CapabilityTier,
    FailureFlavor,
    NodeArchetype,
    ExecutionMode,
    ConditionExpr,
    Condition,
    ConditionLogic,
    ConditionType,
    STUDIO_RUNS_DIR,
)
from api.operator_registry import OperatorRegistry
from api.executors.safe_executor import SafeExecutor, SafeExecutorError, SecurityError, DependencyRequiredError

logger = logging.getLogger(__name__)


class PathStepGraphEngine:
    """
    Headless execution engine for Studio Graphs.

    Executes a StudioGraph as a deterministic workflow:
    - Query nodes fetch live data (list/vector) from adapters
    - FanOut nodes loop over items, creating child executions
    - AITransform nodes execute inline scripts or saved Skills via SafeExecutor
    - ConditionalAction nodes route based on exact condition match (Phase 1)

    Stores run logs and undefined queue items per graph.
    """

    def __init__(
        self,
        base_dir: str,
        operator_registry: OperatorRegistry,
        studio_graph_manager: StudioGraphManager,
        skill_manager: SkillManager,
        run_manager: RunManager,
    ):
        self.base_dir = base_dir
        self.operator_registry = operator_registry
        self.studio_graph_manager = studio_graph_manager
        self.skill_manager = skill_manager
        self.run_manager = run_manager

        # Directory for run logs
        self.runs_dir = f"{base_dir}/{STUDIO_RUNS_DIR}"
        os.makedirs(self.runs_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def start_run(self, graph_id: str, inputs: Dict[str, Any], dry_run: bool = False) -> str:
        """
        Start a new graph run.

        Args:
            graph_id: ID of the StudioGraph to execute
            inputs: Initial inputs for the run
            dry_run: dec #16 — when True, condition-routed branches that would
                fire a live adapter write (update_resource) are short-circuited
                to a logged "would-have-run" result. Reads still execute, so
                routing + undefined-queue + run-logs can be verified without
                side effects before the single real write at slice-1 end.

        Returns:
            run_id of the started execution
        """
        graph = self.studio_graph_manager.get_graph(graph_id)
        if not graph:
            raise ValueError(f"StudioGraph {graph_id} not found")

        run_id = f"studio_run_{uuid.uuid4().hex[:12]}"

        # Initialize execution state
        exec_state = ExecutionState(
            graph_id=graph_id,
            run_id=run_id,
            state=inputs.copy(),
            run_log=[],
            undefined_queue=[],
            loop_stack=[],
            dry_run=dry_run,
        )

        # Save initial run log
        run_log = GraphRunLog(
            run_id=run_id,
            graph_id=graph_id,
            started_at=datetime.utcnow(),
            status="running",
            node_results=[],
            undefined_items=[],
            escalated_items=[],
        )
        self._save_run_log(run_log)

        # Start execution asynchronously
        # In slice 1, we run synchronously for simplicity; async in Phase 2
        asyncio.create_task(self._execute_graph(exec_state, graph))

        return run_id

    def get_run_log(self, run_id: str) -> Optional[GraphRunLog]:
        """Load a run log by ID."""
        path = f"{self.runs_dir}/{run_id}.json"
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return GraphRunLog.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load run log {run_id}: {e}")
            return None

    def list_run_logs(self, graph_id: str, limit: int = 50) -> List[GraphRunLog]:
        """List recent run logs for a graph (dec #21: last 50)."""
        logs = []
        for filename in os.listdir(self.runs_dir):
            if filename.endswith(".json"):
                run_id = filename[:-5]
                log = self.get_run_log(run_id)
                if log and log.graph_id == graph_id:
                    logs.append(log)
        # Sort by started_at descending, take most recent
        logs.sort(key=lambda l: l.started_at, reverse=True)
        return logs[:limit]

    def get_undefined_queue(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get undefined queue items for a graph (cap 100, dec #20)."""
        # Load from the most recent completed/partial run
        logs = self.list_run_logs(graph_id, limit=1)
        if not logs:
            return []
        return logs[0].undefined_items[:100]

    # -------------------------------------------------------------------------
    # Interactive Preview (Slice 1 authoring — live-results-led compiler)
    # -------------------------------------------------------------------------

    async def preview_node(
        self,
        node: StudioNode,
        execution_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a single draft node against the in-progress execution_state and
        return its result. Powers the interactive turn-by-turn authoring loop:
        the UI calls preview-node at each turn so the human reacts to *real*
        returned data (dec #0, dec #2).

        Semantics intentionally mirror headless execution: we build an ephemeral
        one-node graph + an ExecutionState seeded from the client's
        execution_state, then dispatch to the SAME per-node handlers the headless
        engine uses (_execute_query_node / _execute_ai_transform_node /
        _execute_conditional_action_node). No parallel evaluator is introduced —
        preview == headless (dec #17 discipline). The route is async so we can
        `await` these handlers directly (they use the adapter / SafeExecutor).

        FanOut produces no value itself; in preview we surface the sampled
        source list so the UI can render one card per item. Downstream turns
        iterate via the real (headless) loop when the graph runs after save.

        Returns:
            {
                "result": <node output or None>,
                "updated_state": <execution_state after writing output_ref>,
                "status": "success" | "failed" | "undefined" | "skipped",
                "error": <str | None>,
                "matched_branch": <"true" | "false" | None>,  # ConditionalAction
            }
        """
        # Seed an ephemeral ExecutionState from the client-supplied state.
        # run_id is synthetic — preview never persists a run log.
        exec_state = ExecutionState(
            graph_id=f"preview:{node.node_id}",
            run_id=f"preview_{uuid.uuid4().hex[:8]}",
            state=dict(execution_state),  # copy; never mutate the caller's dict
            run_log=[],
            undefined_queue=[],
            loop_stack=[],
        )

        # Ephemeral one-node graph so the shared handlers can resolve adjacency;
        # no edges → no successor recursion runs.
        preview_graph = StudioGraph(
            graph_id=exec_state.graph_id,
            name="preview",
            nodes=[node],
            edges=[],
        )
        adjacency = self._build_adjacency(preview_graph)

        start_time = datetime.utcnow()
        status = "success"
        error: Optional[str] = None
        matched_branch: Optional[str] = None
        result: Any = None

        try:
            if node.archetype == NodeArchetype.QUERY:
                result = await self._execute_query_node(exec_state, node)
            elif node.archetype == NodeArchetype.AI_TRANSFORM:
                result = await self._execute_ai_transform_node(exec_state, node)
            elif node.archetype == NodeArchetype.CONDITIONAL_ACTION:
                result = await self._execute_conditional_action_node(
                    exec_state, node
                )
                # _execute_conditional_action_node returns {"matched": bool, ...}
                if isinstance(result, dict) and "matched" in result:
                    matched_branch = "true" if result["matched"] else "false"
            elif node.archetype == NodeArchetype.FAN_OUT:
                # No children to iterate in preview; surface the source list so
                # the UI can render cards (one per item).
                source = node.loop_over.get("source", "")
                result = self._get_nested_value(exec_state.state, source)
            else:
                raise ValueError(f"Unknown node archetype: {node.archetype}")

            # Write output to state the same way headless does (dec #17 parity).
            if result is not None and getattr(node, "output_ref", None):
                self._write_to_state(exec_state.state, node.output_ref, result)

        except Exception as e:
            logger.error(f"preview_node {node.node_id} failed: {e}")
            status = "failed"
            error = str(e)
            result = None

        exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.info(f"preview_node {node.node_id}: status={status}, {exec_time}ms")

        return {
            "result": result,
            "updated_state": exec_state.state,
            "status": status,
            "error": error,
            "matched_branch": matched_branch,
        }

    # -------------------------------------------------------------------------
    # Core Execution Logic
    # -------------------------------------------------------------------------

    async def _execute_graph(self, exec_state: ExecutionState, graph: StudioGraph):
        """Main execution loop for a graph."""
        run_id = exec_state.run_id

        try:
            # Build adjacency list for traversal
            adjacency = self._build_adjacency(graph)

            # Find entry nodes (no incoming edges)
            entry_nodes = self._find_entry_nodes(graph, adjacency)

            # Execute from entry points
            for node_id in entry_nodes:
                await self._execute_node(exec_state, graph, node_id, adjacency)

            # Mark run as completed
            await self._finalize_run(exec_state, graph, "completed")

        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            await self._finalize_run(exec_state, graph, "failed", str(e))

    def _build_adjacency(self, graph: StudioGraph) -> Dict[str, List[GraphEdge]]:
        """Build adjacency list from graph edges."""
        adj = {node.node_id: [] for node in graph.nodes}
        for edge in graph.edges:
            if edge.source in adj:
                adj[edge.source].append(edge)
        return adj

    def _find_entry_nodes(self, graph: StudioGraph, adjacency: Dict[str, List[GraphEdge]]) -> List[str]:
        """Find nodes with no incoming edges."""
        has_incoming = set()
        for node_id, edges in adjacency.items():
            for edge in edges:
                has_incoming.add(edge.target)
        return [node.node_id for node in graph.nodes if node.node_id not in has_incoming]

    async def _execute_node(
        self,
        exec_state: ExecutionState,
        graph: StudioGraph,
        node_id: str,
        adjacency: Dict[str, List[GraphEdge]],
        loop_context: Optional[Dict[str, Any]] = None,
    ):
        """Execute a single node and recurse to successors."""
        node = self._get_node(graph, node_id)
        if not node:
            logger.warning(f"Node {node_id} not found in graph")
            return

        exec_state.current_node_id = node_id
        start_time = datetime.utcnow()

        try:
            # Dispatch to node-type-specific handler
            if node.archetype == NodeArchetype.QUERY:
                result = await self._execute_query_node(exec_state, node, loop_context)
            elif node.archetype == NodeArchetype.FAN_OUT:
                result = await self._execute_fan_out_node(exec_state, graph, node, adjacency, loop_context)
            elif node.archetype == NodeArchetype.AI_TRANSFORM:
                result = await self._execute_ai_transform_node(exec_state, node, loop_context)
            elif node.archetype == NodeArchetype.CONDITIONAL_ACTION:
                result = await self._execute_conditional_action_node(exec_state, node, loop_context)
            else:
                raise ValueError(f"Unknown node archetype: {node.archetype}")

            # Record success
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            exec_state.run_log.append({
                "node_id": node_id,
                "status": "success",
                "output": result,
                "execution_time_ms": exec_time,
            })

            # Write output to state
            if result and node.output_ref:
                self._write_to_state(exec_state.state, node.output_ref, result)

            # Recurse to successors
            for edge in adjacency.get(node_id, []):
                await self._execute_node(exec_state, graph, edge.target, adjacency, loop_context)

        except Exception as e:
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(f"Node {node_id} failed: {e}")

            exec_state.run_log.append({
                "node_id": node_id,
                "status": "failed",
                "error": str(e),
                "execution_time_ms": exec_time,
            })

            # For conditional action, we might continue on false branch
            # For other nodes, failure propagates
            if node.archetype == NodeArchetype.CONDITIONAL_ACTION:
                # Continue to false branch if exists
                false_edge = next((e for e in adjacency.get(node_id, []) if e.source_handle == "false"), None)
                if false_edge:
                    await self._execute_node(exec_state, graph, false_edge.target, adjacency, loop_context)

    # -------------------------------------------------------------------------
    # Node Type Handlers
    # -------------------------------------------------------------------------

    async def _execute_query_node(
        self,
        exec_state: ExecutionState,
        node: QueryNode,
        loop_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a Query node - fetch list/vector data from adapter.

        dec #28: Query actions are list/vector adapter methods (list_tickets,
        list_projects, list_repos, list_pull_requests, list_items). The legacy
        OperatorRegistry dispatches on operator_id (-> fetch) and never consults
        node.action, so list/vector actions were unreachable there. Resolve the
        adapter directly and call the named action coroutine; fall back to the
        fetch_resource->fetch path only for single-resource (non-list) actions.
        """
        # Resolve params from state
        params = self._resolve_params(node.params, exec_state.state, loop_context)

        # List/vector dispatch: call the adapter's action coroutine directly.
        adapter = self.operator_registry.adapters.get(node.adapter)
        if adapter is not None and self._is_list_vector_action(adapter, node.action):
            method = getattr(adapter, node.action)
            result = await method(**params) if inspect.iscoroutinefunction(method) else method(**params)
            logger.info(
                f"QueryNode {node.node_id}: dispatched list/vector action "
                f"{node.action} on {node.adapter} -> output_ref {node.output_ref}"
            )
            return result

        # Single-resource fallback: route through OperatorRegistry (fetch_resource).
        step_config = {
            "step_id": node.node_id,
            "operator_id": "fetch_resource",
            "adapter_id": node.adapter,
            "mode": ExecutionMode.ADAPTER.value,
            "config": {**params, "action": node.action},
            "input_ref": None,
            "output_ref": node.output_ref,
        }

        # Execute via OperatorRegistry
        result = await self.operator_registry.execute_step(step_config, exec_state.state)

        # OperatorRegistry returns ExecutionLog; extract result_data
        if hasattr(result, 'result_data'):
            return result.result_data
        return result

    @staticmethod
    def _is_list_vector_action(adapter: Any, action: str) -> bool:
        """True if `action` is a list/vector adapter method (dec #28), i.e. a
        real callable attribute on the adapter that is neither a single-resource
        OperatorRegistry operator (fetch/update/create/delete) nor a private
        dunder name. Single-resource actions keep the legacy fetch_resource path.
        """
        if not action or action.startswith("_"):
            return False
        if action in {"fetch", "update", "create", "delete"}:
            return False
        method = getattr(adapter, action, None)
        return callable(method) and (
            inspect.iscoroutinefunction(method) or inspect.isfunction(method)
        )

    async def _execute_fan_out_node(
        self,
        exec_state: ExecutionState,
        graph: StudioGraph,
        node: FanOutNode,
        adjacency: Dict[str, List[GraphEdge]],
        loop_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a FanOut node - loop over items, creating child executions."""
        source_path = node.loop_over["source"]
        iterator_var = node.loop_over["iterator_var"]

        # Get source list from state (with loop_context precedence)
        source_state = {**exec_state.state, **(loop_context or {})}
        source_list = self._get_nested_value(source_state, source_path)

        if source_list is None:
            logger.warning(f"FanOut source '{source_path}' not found in state")
            return []

        if not isinstance(source_list, list):
            logger.warning(f"FanOut source '{source_path}' is not a list: {type(source_list)}")
            return []

        logger.info(f"FanOut {node.node_id} iterating over {len(source_list)} items")

        child_results = []
        parent_run_id = str(uuid.uuid4())

        # Push loop context
        exec_state.loop_stack.append({
            "node_id": node.node_id,
            "iterator_var": iterator_var,
            "parent_run_id": parent_run_id,
        })

        try:
            for index, item in enumerate(source_list):
                # Create child loop context
                child_loop_context = {**(loop_context or {}), iterator_var: item}

                # Execute subgraph for this item
                # Find the "loop" edge from this FanOut node
                loop_edges = [e for e in adjacency.get(node.node_id, []) if e.source_handle == "loop"]

                for edge in loop_edges:
                    # Execute the target node with child context
                    await self._execute_node(exec_state, graph, edge.target, adjacency, child_loop_context)

                # Collect output for this iteration
                iteration_output = {iterator_var: item}
                child_results.append(iteration_output)

        finally:
            exec_state.loop_stack.pop()

        return child_results

    async def _execute_ai_transform_node(
        self,
        exec_state: ExecutionState,
        node: AITransformNode,
        loop_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute an AITransform node - inline script or saved Skill via SafeExecutor."""
        # Resolve input
        source_state = {**exec_state.state, **(loop_context or {})}
        input_data = self._get_nested_value(source_state, node.input_ref)

        if node.skill_ref:
            # Load persisted Skill
            skill = self.skill_manager.get_skill(node.skill_ref)
            if not skill:
                raise ValueError(f"Skill {node.skill_ref} not found")
            script = skill.script
        elif node.script:
            script = node.script
        else:
            raise ValueError("AITransform node has neither script nor skill_ref")

        # Prepare script context
        script_context = {
            "input": input_data,
            "state": source_state,
            "loop": loop_context or {},
        }

        # Execute via SafeExecutor
        try:
            result = self.operator_registry.safe_executor.execute(script, script_context)
            return result
        except DependencyRequiredError as e:
            logger.info(f"Dependency required for {node.node_id}: {e.module_name}")
            # In slice 1, we treat missing deps as undefined (dec #11)
            raise
        except SecurityError as e:
            logger.error(f"Security error in {node.node_id}: {e}")
            raise
        except SafeExecutorError as e:
            logger.error(f"Script execution error in {node.node_id}: {e}")
            raise

    async def _execute_conditional_action_node(
        self,
        exec_state: ExecutionState,
        node: ConditionalActionNode,
        loop_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a ConditionalAction node - condition-first routing (dec #8, #19)."""
        source_state = {**exec_state.state, **(loop_context or {})}

        # Evaluate condition
        condition_met = self._evaluate_condition(node.condition, source_state)

        # Record matched branch
        matched_branch = "true" if condition_met else "false"
        logger.info(f"ConditionalAction {node.node_id}: condition={condition_met}, branch={matched_branch}")

        # dec #16 dry-run gate: short-circuit the live adapter write (the only
        # side-effecting surface in slice 1) to a logged "would-have-run"
        # summary. Reads already ran during the Query turns, so the routing,
        # condition-match, and undefined-queue all populate normally — only the
        # destructive update_resource call is suppressed. This is what lets the
        # acceptance run replay a graph dry first and flip dry_run=False for the
        # single real Jira write at slice-1 end (plan §6 "after dry-run logging").
        if exec_state.dry_run:
            dry_run_summary = self._dry_run_would_have_run(
                condition_met, node
            )
            logger.info(
                f"ConditionalAction {node.node_id}: DRY-RUN short-circuit on "
                f"branch={matched_branch} -> would_have_run={dry_run_summary['adapter']} "
                f"action={dry_run_summary['action']!r}"
            )
            return {
                "matched": condition_met,
                "dry_run": True,
                "would_have_run": dry_run_summary,
            }

        # Execute the matching branch's adapter action if present
        if condition_met and node.true_action:
            step_config = {
                "step_id": f"{node.node_id}.true",
                "operator_id": "update_resource",
                "adapter_id": node.true_action,
                "mode": ExecutionMode.ADAPTER.value,
                "config": node.true_action_config,
                "input_ref": None,
                "output_ref": node.true_output_ref,
            }
            result = await self.operator_registry.execute_step(step_config, exec_state.state)
            if hasattr(result, 'result_data'):
                return {"matched": True, "result": result.result_data}
            return {"matched": True, "result": result}

        elif not condition_met and node.false_action:
            step_config = {
                "step_id": f"{node.node_id}.false",
                "operator_id": "update_resource",
                "adapter_id": node.false_action,
                "mode": ExecutionMode.ADAPTER.value,
                "config": node.false_action_config,
                "input_ref": None,
                "output_ref": node.false_output_ref,
            }
            result = await self.operator_registry.execute_step(step_config, exec_state.state)
            if hasattr(result, 'result_data'):
                return {"matched": False, "result": result.result_data}
            return {"matched": False, "result": result}

        # No action on this branch - just pass through
        return {"matched": condition_met}

    @staticmethod
    def _dry_run_would_have_run(condition_met: bool, node: ConditionalActionNode) -> Dict[str, Any]:
        """Summarize the adapter write a conditional branch WOULD have fired.

        Used only when exec_state.dry_run is True (dec #16). Returns a
        JSON-serializable description of the suppressed write so the run log
        records intent without touching the target system. Selects the branch
        matching the evaluated condition; when that branch has no configured
        action, returns an explicit ``noop`` marker.
        """
        if condition_met and node.true_action:
            return {
                "branch": "true",
                "adapter": node.true_action,
                "action": "update_resource",
                "config": node.true_action_config,
                "output_ref": node.true_output_ref,
            }
        if not condition_met and node.false_action:
            return {
                "branch": "false",
                "adapter": node.false_action,
                "action": "update_resource",
                "config": node.false_action_config,
                "output_ref": node.false_output_ref,
            }
        return {
            "branch": "true" if condition_met else "false",
            "adapter": None,
            "action": "noop",
            "config": None,
            "output_ref": None,
        }

    # -------------------------------------------------------------------------
    # Condition Evaluation (shared with OperatorRegistry)
    # -------------------------------------------------------------------------

    def _evaluate_condition(self, condition: ConditionExpr, state: Dict[str, Any]) -> bool:
        """Evaluate a condition against state."""
        if isinstance(condition, ConditionLogic):
            # Compound condition (AND/OR)
            results = [self._evaluate_condition(c, state) for c in condition.conditions]
            if condition.logic == "AND":
                return all(results)
            elif condition.logic == "OR":
                return any(results)
            return False
        elif isinstance(condition, Condition):
            # Simple condition
            return self._evaluate_simple_condition(condition, state)
        return False

    def _evaluate_simple_condition(self, condition: Condition, state: Dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        field_value = self._get_nested_value(state, condition.field)

        if condition.type == ConditionType.EQUALS:
            return field_value == condition.value
        elif condition.type == ConditionType.CONTAINS:
            if field_value is None:
                return False
            return condition.value in str(field_value)
        elif condition.type == ConditionType.REGEX_MATCH:
            if field_value is None:
                return False
            import re
            flags = 0 if condition.case_sensitive else re.IGNORECASE
            return bool(re.search(str(condition.value), str(field_value), flags=flags))
        elif condition.type == ConditionType.IN_LIST:
            if not isinstance(condition.value, list):
                return False
            return field_value in condition.value
        elif condition.type == ConditionType.EXISTS:
            return field_value is not None
        return False

    # -------------------------------------------------------------------------
    # State Helpers
    # -------------------------------------------------------------------------

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get a nested value using dot notation (e.g., 'extracted_fields.os_distro')."""
        if not key:
            return data

        keys = key.split('.')
        current = data
        for k in keys:
            if isinstance(current, dict):
                if k in current:
                    current = current[k]
                elif 'fields' in current and isinstance(current['fields'], dict) and k in current['fields']:
                    current = current['fields'][k]
                else:
                    return None
            elif isinstance(current, list):
                # Support array index access
                try:
                    idx = int(k)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def _write_to_state(self, state: Dict[str, Any], path: str, value: Any):
        """Write a value to state using dot notation."""
        keys = path.split('.')
        current = state
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def _resolve_params(self, params: Dict[str, Any], state: Dict[str, Any], loop_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolve {{variable}} placeholders in params from state."""
        import re

        def replace(match):
            var_name = match.group(1)
            # Priority: loop_context -> state
            if loop_context and var_name in loop_context:
                return str(loop_context[var_name])
            return str(self._get_nested_value(state, var_name)) or match.group(0)

        resolved = json.dumps(params)
        resolved = re.sub(r"\{\{(.*?)\}\}", replace, resolved)
        return json.loads(resolved)

    def _get_node(self, graph: StudioGraph, node_id: str) -> Optional[StudioNode]:
        """Find a node by ID."""
        for node in graph.nodes:
            if node.node_id == node_id:
                return node
        return None

    # -------------------------------------------------------------------------
    # Run Log Persistence
    # -------------------------------------------------------------------------

    async def _finalize_run(
        self,
        exec_state: ExecutionState,
        graph: StudioGraph,
        status: str,
        error: Optional[str] = None,
    ):
        """Finalize run and persist log with undefined queue handling."""
        run_id = exec_state.run_id

        # Convert run_log to NodeExecutionResult objects
        node_results = []
        undefined_items = []
        escalated_items = []
        total_matched = 0
        total_undefined = 0
        total_escalated = 0

        for log_entry in exec_state.run_log:
            node_result = NodeExecutionResult(
                node_id=log_entry["node_id"],
                status=log_entry["status"],
                output=log_entry.get("output"),
                error=log_entry.get("error"),
                execution_time_ms=log_entry.get("execution_time_ms", 0),
                matched_branch=log_entry.get("matched_branch"),
            )
            node_results.append(node_result)

            if log_entry["status"] == "success":
                if log_entry.get("matched_branch") in ("true", "false"):
                    total_matched += 1

        # Handle undefined queue from execution state
        for item in exec_state.undefined_queue:
            undefined_items.append(item)
            total_undefined += 1
            # Cap at 100 (dec #20)
            if total_undefined >= graph.undefined_queue_cap:
                break

        for item in exec_state.run_log:
            if item.get("failure_flavor") == FailureFlavor.ESCALATED:
                escalated_items.append(item)
                total_escalated += 1

        run_log = GraphRunLog(
            run_id=run_id,
            graph_id=graph.graph_id,
            started_at=exec_state.started_at,
            ended_at=datetime.utcnow(),
            status=status,
            node_results=node_results,
            undefined_items=undefined_items,
            escalated_items=escalated_items,
            total_matched=total_matched,
            total_undefined=total_undefined,
            total_escalated=total_escalated,
        )

        self._save_run_log(run_log)
        logger.info(f"Run {run_id} finalized: status={status}, matched={total_matched}, undefined={total_undefined}")

    def _save_run_log(self, run_log: GraphRunLog):
        """Save run log to disk (atomic write)."""
        path = f"{self.runs_dir}/{run_log.run_id}.json"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(run_log.model_dump(mode="json"), f, indent=2, default=str)
            os.replace(tmp_path, path)
        except Exception as e:
            logger.error(f"Failed to save run log {run_log.run_id}: {e}")

    # -------------------------------------------------------------------------
    # Cron Scheduling Support (dec #7)
    # -------------------------------------------------------------------------

    def get_schedulable_graphs(self) -> List[StudioGraph]:
        """Get all graphs that have cron enabled and are simple (Slice 1)."""
        all_graphs = self.studio_graph_manager.list_graphs_full()
        schedulable = []
        for graph in all_graphs:
            if graph.cron_enabled and graph.cron_schedule:
                # Slice 1: simple graphs only (dec #9)
                if graph.required_capability == CapabilityTier.CLASSIFY or graph.required_capability == CapabilityTier.GENERATE:
                    schedulable.append(graph)
        return schedulable