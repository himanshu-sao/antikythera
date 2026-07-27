#!/usr/bin/env python3
"""Create the Twistlock vulnerability triage graph for Slice-1 acceptance test."""

import sys
sys.path.insert(0, "/Users/himanshusao/Work/src/extra/himanshu-sao/antikythera")

from api.managers.studio_graph_manager import StudioGraphManager
from api.models.studio import (
    StudioGraph, StudioNode, GraphEdge,
    QueryNode, FanOutNode, AITransformNode, ConditionalActionNode,
    NodeArchetype, Condition, ConditionType, RoutingStrategy, CapabilityTier,
    ExecutionMode
)
import json

base_dir = "/Users/himanshusao/Work/src/extra/himanshu-sao/antikythera/automation-ideas"
manager = StudioGraphManager(base_dir)

# Create nodes
query_node = QueryNode(
    node_id="query_twistlock",
    name="Query Twistlock Tickets",
    archetype=NodeArchetype.QUERY,
    description="Fetch open Twistlock vulnerability tickets from Jira",
    adapter="jira_adapter",
    action="list_tickets",
    params={"jql": "project = TWISTLOCK AND status = Open ORDER BY created DESC", "max_results": 10},
    output_ref="tickets",
)

fanout_node = FanOutNode(
    node_id="fanout_tickets",
    name="Fan-out per Ticket",
    archetype=NodeArchetype.FAN_OUT,
    description="Create one branch per ticket",
    loop_over={"source": "tickets", "iterator_var": "ticket"},
)

ai_transform_node = AITransformNode(
    node_id="ai_extract",
    name="Extract OS and Component",
    archetype=NodeArchetype.AI_TRANSFORM,
    description="Extract OS, component, and severity from ticket description",
    mode=ExecutionMode.SCRIPT,
    script="""import re
text = input.get('fields', {}).get('description', '') or ''
os_match = re.search(r'OS:\\s*(\\S+)', text)
comp_match = re.search(r'Component:\\s*(\\S+)', text)
sev_match = re.search(r'Severity:\\s*(\\S+)', text)
result = {
    'os': os_match.group(1) if os_match else 'Unknown',
    'component': comp_match.group(1) if comp_match else 'Unknown',
    'severity': sev_match.group(1) if sev_match else 'Unknown',
    'ticket_key': input.get('key', '')
}
""",
    input_ref="ticket",
    output_ref="extracted",
    suggested_model_tier=CapabilityTier.CLASSIFY,
)

cond_node = ConditionalActionNode(
    node_id="cond_escalate",
    name="Escalate Critical Tickets",
    archetype=NodeArchetype.CONDITIONAL_ACTION,
    description="If severity is Critical, transition to Investigating and assign",
    routing_strategy=RoutingStrategy.CONDITION_FIRST,
    condition=Condition(
        type=ConditionType.EQUALS,
        field="extracted.severity",
        value="Critical",
    ),
    true_action="jira_adapter",
    true_action_config={"transition": "Investigating", "assignee": "current_user"},
    true_output_ref="escalated_ticket_id",
    false_action=None,
    false_action_config={},
    false_output_ref=None,
    signature="If ticket severity == Critical, escalate to Investigating and assign to current user",
)

# Create edges
edges = [
    GraphEdge(source="query_twistlock", target="fanout_tickets", source_handle=None, target_handle=None),
    GraphEdge(source="fanout_tickets", target="ai_extract", source_handle="loop", target_handle=None),
    GraphEdge(source="ai_extract", target="cond_escalate", source_handle=None, target_handle=None),
]

# Create graph
graph = StudioGraph(
    graph_id="graph_twistlock_vulnerability_triage",
    name="Twistlock Vulnerability Triage",
    description="Query Jira for open Twistlock tickets, fan-out per ticket, AI-transform to extract fields, conditional action to escalate Critical tickets",
    version="1.0.0",
    nodes=[query_node, fanout_node, ai_transform_node, cond_node],
    edges=edges,
    required_capability=CapabilityTier.GENERATE,
    cron_schedule=None,
    cron_enabled=False,
    undefined_queue_cap=100,
    max_run_logs=50,
)

# Save graph
success = manager.save_graph(graph)
if success:
    print(f"✓ Graph created: {graph.graph_id}")
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Edges: {len(graph.edges)}")
    print()
    # Print as JSON for verification
    print(json.dumps(graph.model_dump(mode="json"), indent=2))
else:
    print("✗ Failed to save graph")
    sys.exit(1)