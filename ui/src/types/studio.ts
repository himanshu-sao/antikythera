// Studio Graph & Type Definitions (Slice 1 - Phase 1)
//
// This module defines the shared type system between the interactive Studio authoring surface
// and the headless PathStepGraphEngine. It is the single source of truth for node archetypes,
// graph structure, skills, and execution types.
//
// Decisions implemented (see docs/plans/mighty-greeting-cookie.md Appendix):
// - dec #3: Supersedes WorkflowArchitect/BlueprintArchitect surface
// - dec #5, #6: Hybrid save = durable headless template + undefined queue
// - dec #8, #19: Condition-first routing with reserved signature for Phase 2 AI fallback
// - dec #9, #10: Model tiers / capability declaration on graph and nodes
// - dec #12: Author-time capability + suggested_model_tier emitted per proposal
// - dec #13, #18: Skill = persisted AI-transform node (disk-backed)
// - dec #17: Shared model defs via api.models.studio import (no shared-evaluator extraction)
// - dec #20: Undefined queue cap = 100/graph, no auto-expiry
// - dec #21: Replay history = 50 run logs + perpetual aggregate
// - dec #22: Single shared ui/src/types/studio.ts (this file)
// - dec #23: Delete dead endpoints /api/automation/templates, GET /api/automation/state
// - dec #28: List/vector query actions on adapters (fetch_resource returns 1, never a list)

import { z } from 'zod';

// -----------------------------------------------------------------------------
// Primitive References (used across node types)
// -----------------------------------------------------------------------------

export type AdapterRef = string;      // e.g., "jira_adapter", "github_adapter", "internal_adapter"
export type InputRef = string;        // Dot-path into execution state, e.g., "jira_tickets"
export type OutputRef = string;       // Dot-path for writing output, e.g., "extracted_fields.os_distro"
export type SkillRef = string;        // skill_id reference to persisted Skill
export type LoopOverSpec = {          // {"source": "jira_tickets", "iterator_var": "ticket"}
  source: string;
  iterator_var: string;
};

// -----------------------------------------------------------------------------
// Capability & Model Tier System (dec #9, #10)
// -----------------------------------------------------------------------------

export enum CapabilityTier {
  CLASSIFY = 'classify',           // 4-8B local: constrained yes/no classification
  GENERATE = 'generate',           // Current default: general generation
  REASON_OVER_CODE = 'reason_over_code'  // 20B/27B+: complex reasoning over code
}

// Default tier for graphs/nodes that declare no tier (dec #10: "Default unchanged")
export const DEFAULT_CAPABILITY: CapabilityTier = CapabilityTier.GENERATE;

// -----------------------------------------------------------------------------
// Node Archetypes (dec #0, #27, #28)
// -----------------------------------------------------------------------------

export enum NodeArchetype {
  QUERY = 'query',                 // Fetch live data (list/vector) from adapter
  FAN_OUT = 'fan_out',             // Loop: one branch per item (OperatorRegistry.loop_over)
  AI_TRANSFORM = 'ai_transform',   // One-off script OR saved Skill (SafeExecutor mode=SCRIPT)
  CONDITIONAL_ACTION = 'conditional_action'  // Condition-first routing + optional signature
}

export enum ExecutionMode {
  ADAPTER = 'adapter',     // Native adapter call (OperatorRegistry operator_map)
  SCRIPT = 'script'        // SafeExecutor Python snippet (AITransform always SCRIPT)
}

export enum RoutingStrategy {
  CONDITION_FIRST = 'condition_first',      // Exact condition match (free)
  SIGNATURE_FALLBACK = 'signature_fallback'  // Phase 2: 4-8B classifier on signature corpus
}

export enum FailureFlavor {
  UNDEFINED = 'undefined',           // "Don't recognize, cheap to triage" (dec #11)
  ESCALATED = 'escalated'            // "Recognize but can't safely complete" (dec #11)
}

// -----------------------------------------------------------------------------
// Condition Expression (shared with OperatorRegistry.Condition/ConditionLogic)
// -----------------------------------------------------------------------------

export enum ConditionType {
  EQUALS = 'equals',
  CONTAINS = 'contains',
  REGEX_MATCH = 'regex_match',
  IN_LIST = 'in_list',
  EXISTS = 'exists'
}

export type ConditionExpr =
  | {
      // Simple condition
      type: ConditionType;
      field: string;       // Dot-path, e.g., "extracted_fields.os_distro"
      value: unknown;
      case_sensitive?: boolean;
      logic?: never;
      conditions?: never;
    }
  | {
      // Compound condition (AND/OR)
      logic: 'AND' | 'OR';
      conditions: ConditionExpr[];
      type?: never;
      field?: never;
      value?: never;
      case_sensitive?: never;
    };

export const isCompoundCondition = (cond: ConditionExpr): boolean =>
  'logic' in cond && cond.logic !== undefined;

// -----------------------------------------------------------------------------
// Base Node (all executable nodes share these)
// -----------------------------------------------------------------------------

export interface BaseNode {
  node_id: string;
  archetype: NodeArchetype;
  name: string;
  description?: string;

  // Capability declaration (dec #9, #12)
  required_capability?: CapabilityTier;
  suggested_model_tier?: CapabilityTier;  // Emitted by proposer (dec #12)

  // Reserved for Phase 2 AI routing fallback (dec #19)
  signature?: string;  // Short NL signature, max 200 chars

  // Visual/authoring metadata (not used by headless engine)
  position?: { x: number; y: number };
}

// -----------------------------------------------------------------------------
// Executable Node Types (discriminated union via archetype)
// -----------------------------------------------------------------------------

export interface QueryNode extends BaseNode {
  archetype: NodeArchetype.QUERY;
  adapter: AdapterRef;
  action: string;                    // List action on adapter (returns vector, not single)
  params?: Record<string, unknown>;
  output_ref: OutputRef;

  // For UI: show adapter status, integration health
  adapter_status?: string;
}

export interface FanOutNode extends BaseNode {
  archetype: NodeArchetype.FAN_OUT;
  loop_over: LoopOverSpec;  // {"source": "jira_tickets", "iterator_var": "ticket"}

  // Children are defined by graph edges from this node (source_handle = "loop")
}

export interface AITransformNode extends BaseNode {
  archetype: NodeArchetype.AI_TRANSFORM;
  execution_mode: ExecutionMode;  // Always SCRIPT for AI transform

  // One of: inline script OR saved skill reference
  script?: string;           // Python code for SafeExecutor
  skill_ref?: SkillRef;      // Persisted Skill to reuse

  input_ref: InputRef;
  output_ref: OutputRef;

  // Model tier hint for this specific transform (dec #9)
  suggested_model_tier?: CapabilityTier;
}

export interface ConditionalActionNode extends BaseNode {
  archetype: NodeArchetype.CONDITIONAL_ACTION;
  condition: ConditionExpr;
  routing_strategy?: RoutingStrategy;

  // True branch: adapter action to execute when condition matches
  true_action?: AdapterRef;
  true_action_config?: Record<string, unknown>;
  true_output_ref?: OutputRef;

  // False branch: optional adapter action
  false_action?: AdapterRef;
  false_action_config?: Record<string, unknown>;
  false_output_ref?: OutputRef;

  // Phase 2: NL signature for 4-8B classifier (dec #19: short labeled examples)
  signature?: string;
}

// Discriminated union for all executable node types
export type StudioNode =
  | QueryNode
  | FanOutNode
  | AITransformNode
  | ConditionalActionNode;

// Type guards
export const isQueryNode = (node: StudioNode): node is QueryNode =>
  node.archetype === NodeArchetype.QUERY;

export const isFanOutNode = (node: StudioNode): node is FanOutNode =>
  node.archetype === NodeArchetype.FAN_OUT;

export const isAITransformNode = (node: StudioNode): node is AITransformNode =>
  node.archetype === NodeArchetype.AI_TRANSFORM;

export const isConditionalActionNode = (node: StudioNode): node is ConditionalActionNode =>
  node.archetype === NodeArchetype.CONDITIONAL_ACTION;

// -----------------------------------------------------------------------------
// Collapse / Pick Specification (NOT a graph node — scope narrowing, dec #0)
// -----------------------------------------------------------------------------

export interface CollapseSpec {
  type: 'pick_first' | 'pick_n' | 'filter';
  n?: number;                 // For pick_n
  filter_condition?: ConditionExpr;  // For filter
}

// -----------------------------------------------------------------------------
// Graph Structure
// -----------------------------------------------------------------------------

export interface GraphEdge {
  edge_id: string;
  source: string;  // source node_id
  target: string;  // target node_id
  source_handle?: string;  // For FanOut: "loop" | "true" | "false"
  target_handle?: string;  // For FanOut entry point
}

export interface StudioGraph {
  graph_id: string;
  name: string;
  description?: string;
  version?: string;
  created_at: string;  // ISO 8601
  updated_at: string;  // ISO 8601

  // Nodes and edges
  nodes: StudioNode[];
  edges: GraphEdge[];

  // Graph-level capability declaration (dec #9)
  required_capability?: CapabilityTier;

  // Cron scheduling (dec #7) — simple graphs only in Slice 1
  cron_schedule?: string;  // e.g., "0 9 * * 1-5"
  cron_enabled?: boolean;

  // Undefined queue config (dec #20)
  undefined_queue_cap?: number;

  // Replay history config (dec #21)
  max_run_logs?: number;
}

// -----------------------------------------------------------------------------
// Execution Types (for headless PathStepGraphEngine)
// -----------------------------------------------------------------------------

export interface ExecutionState {
  graph_id: string;
  run_id: string;
  started_at: string;  // ISO 8601
  current_node_id?: string;
  state: Record<string, unknown>;  // All node outputs keyed by output_ref
  loop_stack: Record<string, unknown>[];  // For nested fan-out
  undefined_queue: Record<string, unknown>[];
  run_log: Record<string, unknown>[];
}

export interface NodeExecutionResult {
  node_id: string;
  status: 'success' | 'skipped' | 'failed' | 'undefined' | 'escalated';
  output?: Record<string, unknown>;
  error?: string;
  failure_flavor?: FailureFlavor;
  execution_time_ms?: number;
  matched_branch?: 'true' | 'false';  // For ConditionalAction
}

export interface GraphRunLog {
  run_id: string;
  graph_id: string;
  started_at: string;  // ISO 8601
  ended_at?: string;   // ISO 8601
  status: 'running' | 'completed' | 'failed' | 'partial';
  node_results: NodeExecutionResult[];
  undefined_items: Record<string, unknown>[];
  escalated_items: Record<string, unknown>[];

  // Aggregate counters for perpetual dashboard
  total_matched?: number;
  total_undefined?: number;
  total_escalated?: number;
}

// -----------------------------------------------------------------------------
// Skill Persistence (dec #13, #18)
// -----------------------------------------------------------------------------

export interface Skill {
  skill_id: string;
  name: string;
  description: string;
  script: string;  // Python code for SafeExecutor
  input_schema?: Record<string, unknown>;  // JSON schema for input_ref
  output_schema?: Record<string, unknown>; // JSON schema for output_ref
  version?: string;
  created_at: string;  // ISO 8601
  updated_at: string;  // ISO 8601
  tags?: string[];

  // Capability tier this skill requires (dec #9)
  required_capability?: CapabilityTier;
}

// -----------------------------------------------------------------------------
// Storage Paths & Constants
// -----------------------------------------------------------------------------

export const STUDIO_GRAPHS_DIR = 'studio_graphs';
export const SKILLS_DIR = 'skills';
export const STUDIO_RUNS_DIR = 'studio_runs';

// -----------------------------------------------------------------------------
// Zod Schemas for Runtime Validation (API boundaries)
// -----------------------------------------------------------------------------

export const CapabilityTierSchema = z.nativeEnum(CapabilityTier);
export const NodeArchetypeSchema = z.nativeEnum(NodeArchetype);
export const ExecutionModeSchema = z.nativeEnum(ExecutionMode);
export const RoutingStrategySchema = z.nativeEnum(RoutingStrategy);
export const FailureFlavorSchema = z.nativeEnum(FailureFlavor);
export const ConditionTypeSchema = z.nativeEnum(ConditionType);

export const LoopOverSpecSchema = z.object({
  source: z.string(),
  iterator_var: z.string(),
});

export const ConditionExprSchema: z.ZodType<ConditionExpr> = z.lazy(() =>
  z.union([
    // Simple condition
    z.object({
      type: ConditionTypeSchema,
      field: z.string(),
      value: z.unknown(),
      case_sensitive: z.boolean().optional(),
    }),
    // Compound condition
    z.object({
      logic: z.enum(['AND', 'OR']),
      conditions: z.array(ConditionExprSchema),
    }),
  ])
);

export const BaseNodeSchema = z.object({
  node_id: z.string(),
  archetype: NodeArchetypeSchema,
  name: z.string(),
  description: z.string().optional(),
  required_capability: CapabilityTierSchema.optional(),
  suggested_model_tier: CapabilityTierSchema.optional(),
  signature: z.string().max(200).optional(),
  position: z.object({ x: z.number(), y: z.number() }).optional(),
});

export const QueryNodeSchema = BaseNodeSchema.extend({
  archetype: z.literal(NodeArchetype.QUERY),
  adapter: z.string(),
  action: z.string().default('list_resources'),
  params: z.record(z.unknown()).optional(),
  output_ref: z.string(),
  adapter_status: z.string().optional(),
});

export const FanOutNodeSchema = BaseNodeSchema.extend({
  archetype: z.literal(NodeArchetype.FAN_OUT),
  loop_over: LoopOverSpecSchema,
});

export const AITransformNodeSchema = BaseNodeSchema.extend({
  archetype: z.literal(NodeArchetype.AI_TRANSFORM),
  execution_mode: z.literal(ExecutionMode.SCRIPT),
  script: z.string().optional(),
  skill_ref: z.string().optional(),
  input_ref: z.string(),
  output_ref: z.string(),
  suggested_model_tier: CapabilityTierSchema.optional(),
});

export const ConditionalActionNodeSchema = BaseNodeSchema.extend({
  archetype: z.literal(NodeArchetype.CONDITIONAL_ACTION),
  condition: ConditionExprSchema,
  routing_strategy: RoutingStrategySchema.optional(),
  true_action: z.string().optional(),
  true_action_config: z.record(z.unknown()).optional(),
  true_output_ref: z.string().optional(),
  false_action: z.string().optional(),
  false_action_config: z.record(z.unknown()).optional(),
  false_output_ref: z.string().optional(),
  signature: z.string().max(200).optional(),
});

export const StudioNodeSchema = z.union([
  QueryNodeSchema,
  FanOutNodeSchema,
  AITransformNodeSchema,
  ConditionalActionNodeSchema,
]);

export const GraphEdgeSchema = z.object({
  edge_id: z.string(),
  source: z.string(),
  target: z.string(),
  source_handle: z.string().optional(),
  target_handle: z.string().optional(),
});

export const StudioGraphSchema = z.object({
  graph_id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  version: z.string().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  nodes: z.array(StudioNodeSchema),
  edges: z.array(GraphEdgeSchema),
  required_capability: CapabilityTierSchema.optional(),
  cron_schedule: z.string().optional(),
  cron_enabled: z.boolean().optional(),
  undefined_queue_cap: z.number().optional(),
  max_run_logs: z.number().optional(),
});

export const SkillSchema = z.object({
  skill_id: z.string(),
  name: z.string(),
  description: z.string(),
  script: z.string(),
  input_schema: z.record(z.unknown()).optional(),
  output_schema: z.record(z.unknown()).optional(),
  version: z.string().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  tags: z.array(z.string()).optional(),
  required_capability: CapabilityTierSchema.optional(),
});

export const GraphRunLogSchema = z.object({
  run_id: z.string(),
  graph_id: z.string(),
  started_at: z.string(),
  ended_at: z.string().optional(),
  status: z.enum(['running', 'completed', 'failed', 'partial']),
  node_results: z.array(z.object({
    node_id: z.string(),
    status: z.enum(['success', 'skipped', 'failed', 'undefined', 'escalated']),
    output: z.record(z.unknown()).optional(),
    error: z.string().optional(),
    failure_flavor: FailureFlavorSchema.optional(),
    execution_time_ms: z.number().optional(),
    matched_branch: z.enum(['true', 'false']).optional(),
  })),
  undefined_items: z.array(z.record(z.unknown())),
  escalated_items: z.array(z.record(z.unknown())),
  total_matched: z.number().optional(),
  total_undefined: z.number().optional(),
  total_escalated: z.number().optional(),
});

// Type inference from Zod schemas (for API request/response types)
export type StudioGraphAPI = z.infer<typeof StudioGraphSchema>;
export type StudioNodeAPI = z.infer<typeof StudioNodeSchema>;
export type SkillAPI = z.infer<typeof SkillSchema>;
export type GraphRunLogAPI = z.infer<typeof GraphRunLogSchema>;
export type NodeExecutionResultAPI = z.infer<typeof GraphRunLogSchema.shape.node_results.element>;