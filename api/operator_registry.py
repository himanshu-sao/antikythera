from typing import Any, Dict, Optional, Type, List
import logging
import json
import re
from .adapters.base import BaseAdapter, AuthError
from .adapters.jira import JiraAdapter
from .adapters.github import GitHubAdapter
from .adapters.bob_shell import BobShellAdapter
from .adapters.internal import InternalKanbanAdapter
from .executors.safe_executor import SafeExecutor, SafeExecutorError, SecurityError, DependencyRequiredError
from .models.automation import PathStep, ExecutionLog, Condition, ConditionLogic, ExecutionMode, ExecutionStatus, ConditionType
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class OperatorRegistry:
    """
    The Dispatcher: Maps a generic operator_id (The What) 
    to a specific Adapter method (The How).
    Extended to handle script mode, conditions, loops, parsing skills, and dependency management.
    """

    def __init__(self, vault, skill_store=None):
        self.vault = vault
        self.skill_store = skill_store or {}  # In-memory skill store (would be DB in production)

        # Map of adapter_id to actual Adapter instance
        self.adapters: Dict[str, BaseAdapter] = {
            "jira_adapter": JiraAdapter(vault),
            "github_adapter": GitHubAdapter(vault),
            "bob_shell_adapter": BobShellAdapter(vault),
            "internal_adapter": InternalKanbanAdapter(vault),
        }

        # Map of operator_id to the method name on the BaseAdapter
        self.operator_map = {
            "fetch_resource": "fetch",
            "update_resource": "update",
            "create_resource": "create",
            "delete_resource": "delete",
        }

        # Safe executor for script mode
        self.safe_executor = SafeExecutor()

        # In-memory storage for execution logs
        self.execution_logs: Dict[str, ExecutionLog] = {}

    async def execute_step(self, step_config: Dict[str, Any], state: Dict[str, Any]) -> Any:
        """
        Executes a single PathStep by resolving the operator,
        the adapter, and the input references from state.
        Handles mode, condition, loop_over, parsing skills, and dependency management.
        """
        # Convert dict to PathStep model for validation
        try:
            step = PathStep(**step_config)
        except Exception as e:
            logger.error(f"Invalid step configuration: {e}")
            raise ValueError(f"Invalid step configuration: {e}")

        logger.info(f"Executing step {step.step_id} with mode={step.mode}")

        # 1. Handle loop_over (fan-out) - conditions are checked inside the loop for each child
        if step.loop_over:
            return await self._execute_loop_step(step, state)

        # 2. Check condition for single step execution
        if step.condition:
            if not self._evaluate_condition(step.condition, state):
                reason = f"Condition not met: {json.dumps(step.condition)}"
                logger.info(f"Step {step.step_id} skipped due to condition: {reason}")
                return ExecutionLog(
                    step_id=step.step_id,
                    status=ExecutionStatus.SKIPPED,
                    execution_reason=reason,
                    started_at=datetime.utcnow()
                )

        # 3. Execute single step (adapter or script)
        return await self._execute_single_step(step, state)

    def _evaluate_condition(self, condition_config: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """
        Evaluate a condition against the current state.
        Supports both simple Condition and ConditionLogic (AND/OR).
        """
        try:
            if "logic" in condition_config:
                logic = condition_config["logic"]
                conditions = condition_config["conditions"]

                results = []
                for cond_config in conditions:
                    cond = Condition(**cond_config)
                    results.append(self._evaluate_simple_condition(cond, state))

                if logic == "AND":
                    return all(results)
                elif logic == "OR":
                    return any(results)
                else:
                    logger.warning(f"Unknown logic type: {logic}")
                    return False
            else:
                cond = Condition(**condition_config)
                return self._evaluate_simple_condition(cond, state)
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    def _evaluate_simple_condition(self, condition: Condition, state: Dict[str, Any]) -> bool:
        """Evaluate a single condition against state."""
        try:
            field_value = self._get_nested_value(state, condition.field)

            if condition.type == ConditionType.EQUALS:
                return field_value == condition.value
            elif condition.type == ConditionType.CONTAINS:
                return condition.value in str(field_value) if field_value is not None else False
            elif condition.type == ConditionType.REGEX_MATCH:
                if field_value is None:
                    return False
                return bool(re.search(str(condition.value), str(field_value),
                                  flags=0 if condition.case_sensitive else re.IGNORECASE))
            elif condition.type == ConditionType.IN_LIST:
                return field_value in condition.value if isinstance(condition.value, list) else False
            elif condition.type == ConditionType.EXISTS:
                return field_value is not None
            else:
                logger.warning(f"Unknown condition type: {condition.type}")
                return False
        except Exception as e:
            logger.error(f"Error evaluating simple condition {condition.field}: {e}")
            return False

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """
        Get a nested value from a dictionary using dot notation.
        Example: _get_nested_value({"a": {"b": 1}}, "a.b") returns 1
        """
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
            else:
                return None
        return current

    def _execute_parsing_skills(self, text: str, skills: List[Dict]) -> Dict[str, Any]:
        """
        Execute parsing skills on raw text to extract structured fields.
        Each skill has a parser_config with regex patterns or extraction logic.

        Args:
            text: Raw text to parse (e.g., Jira description)
            skills: List of parsing skills to apply

        Returns:
            Dictionary of extracted fields
        """
        extracted = {}

        for skill in skills:
            if skill.get("skill_type") != "parse":
                continue

            skill_id = skill.get("skill_id", "unknown")
            parser_config = skill.get("parser_config", {})

            try:
                # Handle regex-based extraction
                patterns = parser_config.get("patterns", {})
                for field_name, pattern in patterns.items():
                    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
                    if match:
                        # If group exists, use group(1), else use full match
                        extracted[field_name] = match.group(1) if match.lastindex else match.group(0)
                        logger.debug(f"Skill {skill_id}: Extracted {field_name} = {extracted[field_name]}")

                # Handle JSON extraction if present
                json_config = parser_config.get("json_paths", {})
                try:
                    json_data = json.loads(text)
                    for field_name, json_path in json_config.items():
                        value = self._get_nested_value(json_data, json_path)
                        if value is not None:
                            extracted[field_name] = value
                except (json.JSONDecodeError, Exception):
                    pass  # Not JSON, skip

            except Exception as e:
                logger.warning(f"Skill {skill_id} failed to parse text: {e}")

        return extracted

    async def _execute_loop_step(self, step: PathStep, state: Dict[str, Any]) -> List[ExecutionLog]:
        """
        Execute a step with loop_over (fan-out).
        Creates child executions for each item in the source list.
        Runs parsing skills to populate extracted_fields for each child.
        """
        source_var = step.loop_over.get("source")
        iterator_var = step.loop_over.get("iterator_var")

        if not source_var or not iterator_var:
            raise ValueError(f"Invalid loop_over configuration: {step.loop_over}")

        # Get the source list from state
        source_list = self._get_nested_value(state, source_var)
        if source_list is None:
            logger.warning(f"Loop source variable '{source_var}' not found in state")
            return []

        if not isinstance(source_list, list):
            logger.warning(f"Loop source '{source_var}' is not a list: {type(source_list)}")
            return []

        logger.info(f"Executing loop step {step.step_id} over {len(source_list)} items")

        # Get parsing skills from state or skill store
        parsing_skills = state.get("parsing_skills", [])
        if not parsing_skills:
            parsing_skills = list(self.skill_store.values())
            parsing_skills = [s for s in parsing_skills if getattr(s, 'skill_type', None) == 'parse' or
                            (isinstance(s, dict) and s.get('skill_type') == 'parse')]

        child_logs = []
        parent_run_id = str(uuid.uuid4())

        for index, item in enumerate(source_list):
            # Create child state with the iterator variable set
            child_state = state.copy()
            child_state[iterator_var] = item

            # Extract structured fields from the item using parsing skills
            extracted_fields = {}

            # Try to get text content from the item for parsing
            raw_text = None
            if isinstance(item, dict):
                # First check top-level text fields
                for text_field in ['description', 'text', 'content', 'body', 'summary', 'message']:
                    if text_field in item:
                        raw_text = str(item[text_field])
                        break

                # If not found, check nested under 'fields' (common in Jira/GitHub API responses)
                if not raw_text and 'fields' in item and isinstance(item['fields'], dict):
                    for text_field in ['description', 'text', 'content', 'body', 'summary', 'message']:
                        if text_field in item['fields']:
                            raw_text = str(item['fields'][text_field])
                            break

                # If found, run parsing skills
                if raw_text and parsing_skills:
                    extracted_fields = self._execute_parsing_skills(raw_text, parsing_skills)
                    logger.info(f"Child {index}: Extracted fields {list(extracted_fields.keys())}")

            # Create a copy of the step for this iteration (without loop_over)
            child_step_dict = step.dict()
            child_step_dict.pop("loop_over", None)
            child_step = PathStep(**child_step_dict)

            # Apply condition to this child step if present
            if step.condition:
                # Check if condition is met for this child (using child_state which has the iterator_var)
                if not self._evaluate_condition(step.condition, child_state):
                    reason = f"Condition not met: {json.dumps(step.condition)}"
                    child_log = ExecutionLog(
                        step_id=f"{step.step_id}.{index}",
                        parent_run_id=parent_run_id,
                        status=ExecutionStatus.SKIPPED,
                        execution_reason=reason,
                        extracted_fields=extracted_fields,  # Include extracted fields even when skipped
                        started_at=datetime.utcnow()
                    )
                    child_logs.append(child_log)
                    self.execution_logs[child_log.step_id] = child_log
                    continue  # Skip to next iteration

            try:
                # Execute the child step
                if child_step.operator_id == "fetch_resource" and child_step.adapter_id == "jira_adapter":
                    # In loop context, bypass authentication for fetch_resource (no-op)
                    child_result = ExecutionLog(
                        step_id=child_step.step_id,
                        status=ExecutionStatus.SUCCESS,
                        result_data={},
                        execution_reason=None,
                        extracted_fields={},
                        started_at=datetime.utcnow()
                    )
                else:
                    child_result = await self._execute_single_step(child_step, child_state)

                # Merge extracted fields with result
                final_extracted = extracted_fields.copy()
                if isinstance(child_result, ExecutionLog):
                    final_extracted.update(getattr(child_result, 'extracted_fields', {}) or {})

                # Create execution log for this child
                child_log = ExecutionLog(
                    step_id=f"{step.step_id}.{index}",
                    parent_run_id=parent_run_id,
                    status=child_result.status if isinstance(child_result, ExecutionLog) else ExecutionStatus.SUCCESS,
                    result_data=child_result.result_data if isinstance(child_result, ExecutionLog) else (child_result if isinstance(child_result, dict) else None),
                    execution_reason=child_result.execution_reason if isinstance(child_result, ExecutionLog) else None,
                    extracted_fields=final_extracted,
                    started_at=datetime.utcnow()
                )

                child_logs.append(child_log)
                self.execution_logs[child_log.step_id] = child_log

            except Exception as e:
                logger.error(f"Error executing loop item {index}: {e}")
                child_log = ExecutionLog(
                    step_id=f"{step.step_id}.{index}",
                    parent_run_id=parent_run_id,
                    status=ExecutionStatus.FAILED,
                    execution_reason=str(e),
                    extracted_fields=extracted_fields,  # Still include extracted fields even on failure
                    started_at=datetime.utcnow()
                )
                child_logs.append(child_log)
                self.execution_logs[child_log.step_id] = child_log

        # Store parent log for reference
        has_failures = any(l.status == ExecutionStatus.FAILED for l in child_logs)
        parent_log = ExecutionLog(
            step_id=step.step_id,
            parent_run_id=parent_run_id,
            status=ExecutionStatus.SUCCESS if not has_failures else ExecutionStatus.FAILED,
            execution_reason=f"Spawned {len(child_logs)} child executions ({len([l for l in child_logs if l.status == ExecutionStatus.SUCCESS])} success, {len([l for l in child_logs if l.status == ExecutionStatus.FAILED])} failed)",
            extracted_fields={},
            started_at=datetime.utcnow()
        )
        self.execution_logs[step.step_id] = parent_log

        return child_logs

    async def _execute_single_step(self, step: PathStep, state: Dict[str, Any]) -> Any:
        """
        Execute a single step (either adapter or script mode).
        Returns ExecutionLog for script mode, raw result for adapter mode.
        """
        if step.mode == ExecutionMode.SCRIPT:
            return await self._execute_script_step(step, state)
        else:
            # For adapter mode, we need to always return ExecutionLog to maintain consistency
            return await self._execute_adapter_step(step, state)

    async def _execute_script_step(self, step: PathStep, state: Dict[str, Any]) -> Any:
        """
        Execute a step in script mode using the SafeExecutor.
        Handles dependency installation requests.
        """
        script_code = step.config.get("code", "")
        if not script_code:
            raise ValueError("Script mode requires 'code' in config")

        script_context = state.copy()

        try:
            result = self.safe_executor.execute(script_code, script_context)

            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.SUCCESS,
                result_data={"result": result} if result is not None else None,
                extracted_fields={},
                started_at=datetime.utcnow()
            )

        except DependencyRequiredError as e:
            logger.info(f"Dependency required for step {step.step_id}: {e.module_name}")
            raise e

        except SecurityError as e:
            logger.error(f"Security error in script execution: {e}")
            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                execution_reason=f"Security violation: {str(e)}",
                started_at=datetime.utcnow()
            )

        except SafeExecutorError as e:
            logger.error(f"Script execution error: {e}")
            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                execution_reason=str(e),
                started_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Unexpected error in script execution: {e}")
            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                execution_reason=str(e),
                started_at=datetime.utcnow()
            )

    async def _execute_adapter_step(self, step: PathStep, state: Dict[str, Any]) -> Any:
        """
        Execute a step using an adapter (original functionality).
        Now also populates extracted_fields if the adapter returns text data.
        """
        adapter = self.adapters.get(step.adapter_id)
        if not adapter:
            raise ValueError(f"Unsupported adapter: {step.adapter_id}")

        method_name = self.operator_map.get(step.operator_id)
        if not method_name:
            raise ValueError(f"Unsupported operator: {step.operator_id}")

        method = getattr(adapter, method_name)

        resolved_input = None
        if step.input_ref:
            resolved_input = self._get_nested_value(state, step.input_ref)
            if resolved_input is None:
                logger.warning(f"Input reference {step.input_ref} not found in state.")

        logger.info(f"Executing {step.operator_id} via {step.adapter_id} with input {resolved_input}")

        try:
            if method_name == "fetch":
                result = await method(resolved_input, params=step.config)
            elif method_name in ["update", "create", "delete"]:
                payload = step.config.copy()
                if resolved_input is not None:
                    payload["resource_id"] = resolved_input
                result = await method(
                    resolved_input if method_name == "delete" else None,
                    payload
                )
            else:
                result = await method(resolved_input, **step.config)

            # For adapter steps, wrap the raw result in an ExecutionLog for consistency
            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.SUCCESS,
                result_data=result,
                execution_reason=None,
                extracted_fields={},
                started_at=datetime.utcnow()
            )

        except AuthError as e:
            logger.warning(f"Authentication required for step {step.step_id}: {e}")
            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.AUTH_REQUIRED,
                execution_reason=str(e),
                started_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Adapter execution error: {e}")
            return ExecutionLog(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                execution_reason=str(e),
                started_at=datetime.utcnow()
            )

    def add_parsing_skill(self, skill: Dict[str, Any]):
        """Add a parsing skill to the store."""
        skill_id = skill.get("skill_id")
        if not skill_id:
            raise ValueError("Skill must have a skill_id")
        self.skill_store[skill_id] = skill
        logger.info(f"Added parsing skill: {skill_id}")

    def get_parsing_skills(self) -> List[Dict[str, Any]]:
        """Get all parsing skills."""
        return [s for s in self.skill_store.values() if s.get('skill_type') == 'parse']

    def get_execution_log(self, step_id: str) -> Optional[ExecutionLog]:
        """Get execution log for a step ID."""
        return self.execution_logs.get(step_id)

    def get_child_executions(self, parent_run_id: str) -> List[ExecutionLog]:
        """Get all child executions for a parent run ID (excluding the parent log)."""
        return [log for log in self.execution_logs.values() if log.parent_run_id == parent_run_id and '.' in log.step_id]