// Studio API client — thin fetch wrapper for /api/studio (dec #5/#6/#13/#14/#20/#21).
//
// Convention matches usePipelineState.ts / useArtifacts.ts: direct fetch, no axios.
// Every response that has a matching studio.ts zod schema is validated with it;
// metadata-only list endpoints (GraphResponse/SkillResponse carry node_count/
// edge_count but no nodes/edges) use light local types and pass through.
//
// This module is the first real consumer of ui/src/types/studio.ts (Step 2),
// unblocking its commit (Step 5).

import { apiUrl } from '../config';
import {
  StudioGraphSchema,
  SkillSchema,
  GraphRunLogSchema,
  type StudioGraph,
  type StudioGraphAPI,
  type Skill,
  type SkillAPI,
  type GraphRunLog,
  type GraphRunLogAPI,
  type CapabilityTier,
  type NodeArchetype,
  type ConditionExpr,
  type GraphEdge,
  type StudioNode,
} from '../types/studio';

// -----------------------------------------------------------------------------
// List-endpoint response shapes (metadata superset that backend adds counts to)
// -----------------------------------------------------------------------------

export interface GraphMeta {
  graph_id: string;
  name: string;
  description: string;
  version: string;
  created_at: string;
  updated_at: string;
  required_capability: string;
  cron_schedule: string | null;
  cron_enabled: boolean;
  undefined_queue_cap: number;
  max_run_logs: number;
  node_count: number;
  edge_count: number;
}

export interface SkillMeta {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  required_capability: string;
}

export interface RunSummary {
  run_id: string;
  graph_id: string;
  status: string;
  started_at: string;
}

export interface UndefinedQueue {
  graph_id: string;
  items: Record<string, unknown>[];
  cap: number;
}

export interface IntegrationStatus {
  name: string;
  type: string;
  adapter_module?: string | null;
  status: string;
  connected: boolean;
}

// -----------------------------------------------------------------------------
// Low-level fetch helper
// -----------------------------------------------------------------------------

async function studioFetch<T>(
  path: string,
  init?: RequestInit,
  // Schemas infer their own output type (z.output), which may differ slightly
  // from the local StudioGraph/Skill interfaces (e.g. created_at optionality).
  // Callers pass the schema; we cast its parsed output to the declared return T.
  schema?: { parse: (v: unknown) => unknown },
): Promise<T> {
  const res = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = `Request to ${path} failed (${res.status})`;
    try {
      const err = await res.json();
      if (typeof err.detail === 'string') detail = err.detail;
    } catch { /* non-JSON error body */ }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as unknown as T;
  const data = await res.json();
  return schema ? (schema.parse(data) as T) : (data as T);
}

// -----------------------------------------------------------------------------
// Graphs
// -----------------------------------------------------------------------------

export async function listGraphs(): Promise<GraphMeta[]> {
  return studioFetch<GraphMeta[]>('/api/studio/graphs');
}

export async function getGraph(graphId: string): Promise<StudioGraph> {
  // Detail endpoint returns { ...meta, nodes[], edges[] }; validate the graph
  // body via StudioGraphSchema (tolerates the metadata extras — schema is loose).
  return studioFetch<StudioGraph>(`/api/studio/graphs/${graphId}`, undefined, StudioGraphSchema);
}

export interface SaveGraphInput {
  name: string;
  description?: string;
  version?: string;
  nodes: StudioNode[];
  edges: GraphEdge[];
  required_capability?: CapabilityTier;
  cron_schedule?: string;
  cron_enabled?: boolean;
  undefined_queue_cap?: number;
  max_run_logs?: number;
}

export async function saveGraph(input: SaveGraphInput): Promise<GraphMeta> {
  // POST creates (derives graph_id server-side); PUT updates an existing id.
  const payload = {
    name: input.name,
    description: input.description ?? '',
    version: input.version ?? '1.0.0',
    nodes: input.nodes.map((n) => n as unknown as Record<string, unknown>),
    edges: input.edges,
    required_capability: input.required_capability ?? 'generate',
    cron_schedule: input.cron_schedule ?? null,
    cron_enabled: input.cron_enabled ?? false,
    undefined_queue_cap: input.undefined_queue_cap ?? 100,
    max_run_logs: input.max_run_logs ?? 50,
  } as Record<string, unknown>;
  return studioFetch<GraphMeta>('/api/studio/graphs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateGraph(graphId: string, input: Partial<SaveGraphInput>): Promise<GraphMeta> {
  const payload: Record<string, unknown> = {};
  if (input.name !== undefined) payload.name = input.name;
  if (input.description !== undefined) payload.description = input.description;
  if (input.version !== undefined) payload.version = input.version;
  if (input.nodes !== undefined) payload.nodes = input.nodes.map((n) => n as unknown as Record<string, unknown>);
  if (input.edges !== undefined) payload.edges = input.edges;
  if (input.required_capability !== undefined) payload.required_capability = input.required_capability;
  if (input.cron_schedule !== undefined) payload.cron_schedule = input.cron_schedule;
  if (input.cron_enabled !== undefined) payload.cron_enabled = input.cron_enabled;
  if (input.undefined_queue_cap !== undefined) payload.undefined_queue_cap = input.undefined_queue_cap;
  if (input.max_run_logs !== undefined) payload.max_run_logs = input.max_run_logs;
  return studioFetch<GraphMeta>(`/api/studio/graphs/${graphId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteGraph(graphId: string): Promise<void> {
  await studioFetch<void>(`/api/studio/graphs/${graphId}`, { method: 'DELETE' });
}

export async function runGraph(graphId: string, inputs?: Record<string, unknown>): Promise<RunSummary> {
  return studioFetch<RunSummary>(`/api/studio/graphs/${graphId}/run`, {
    method: 'POST',
    body: JSON.stringify({ inputs: inputs ?? {} }),
  });
}

export async function listRuns(graphId: string, limit = 50): Promise<GraphRunLog[]> {
  const logs = await studioFetch<GraphRunLogAPI[]>(
    `/api/studio/graphs/${graphId}/runs?limit=${limit}`,
  );
  // Each log validated on parse; map back to the typed interface.
  return logs.map((log) => GraphRunLogSchema.parse(log) as unknown as GraphRunLog);
}

export async function getUndefinedQueue(graphId: string): Promise<UndefinedQueue> {
  return studioFetch<UndefinedQueue>(`/api/studio/graphs/${graphId}/undefined-queue`);
}

export async function listSchedulable(): Promise<GraphMeta[]> {
  return studioFetch<GraphMeta[]>('/api/studio/schedulable-graphs');
}

// -----------------------------------------------------------------------------
// Interactive preview (Slice 1 authoring loop — live-results-led compiler)
// -----------------------------------------------------------------------------

export interface PreviewNodeInput {
  node: StudioNode;                          // Draft StudioNode to execute
  execution_state: Record<string, unknown>;  // In-progress state (output_ref -> value)
}

export interface PreviewNodeResult {
  result: unknown;
  updated_state: Record<string, unknown>;
  status: 'success' | 'failed' | 'undefined' | 'skipped';
  error: string | null;
  matched_branch: 'true' | 'false' | null;   // ConditionalAction routing
}

export async function previewNode(input: PreviewNodeInput): Promise<PreviewNodeResult> {
  // Synchronous single-draft-node execution against the in-progress state.
  // The backend reuses the headless per-node handlers (dec #17), so preview
  // semantics match a real run; no run log is persisted. 422 on a malformed
  // StudioNode (validated as the discriminated union server-side).
  return studioFetch<PreviewNodeResult>('/api/studio/preview-node', {
    method: 'POST',
    body: JSON.stringify({
      node: input.node as unknown as Record<string, unknown>,
      execution_state: input.execution_state,
    }),
  });
}

// -----------------------------------------------------------------------------
// Skills (dec #13, #18 — persisted to disk)
// -----------------------------------------------------------------------------

export async function listSkills(): Promise<SkillMeta[]> {
  return studioFetch<SkillMeta[]>('/api/studio/skills');
}

export async function getSkill(skillId: string): Promise<Skill> {
  // Detail endpoint returns { ...meta, script, input_schema, output_schema };
  // SkillSchema validates that full shape.
  return studioFetch<Skill>(`/api/studio/skills/${skillId}`, undefined, SkillSchema);
}

export interface SaveSkillInput {
  skill_id: string;
  name: string;
  description: string;
  script: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  version?: string;
  tags?: string[];
  required_capability?: CapabilityTier;
}

export async function saveSkill(input: SaveSkillInput): Promise<SkillMeta> {
  return studioFetch<SkillMeta>('/api/studio/skills', {
    method: 'POST',
    body: JSON.stringify({
      skill_id: input.skill_id,
      name: input.name,
      description: input.description,
      script: input.script,
      input_schema: input.input_schema ?? {},
      output_schema: input.output_schema ?? {},
      version: input.version ?? '1.0.0',
      tags: input.tags ?? [],
      required_capability: input.required_capability ?? 'generate',
    }),
  });
}

export async function deleteSkill(skillId: string): Promise<void> {
  await studioFetch<void>(`/api/studio/skills/${skillId}`, { method: 'DELETE' });
}

// -----------------------------------------------------------------------------
// Integration status (dec #14 — env var credentials, status only, no token)
// -----------------------------------------------------------------------------

export async function getIntegrationStatus(): Promise<IntegrationStatus[]> {
  const data = await studioFetch<{ integrations: IntegrationStatus[] }>(
    '/api/studio/integrations/status',
  );
  return data.integrations ?? [];
}

// Re-export the studio.ts types this client's callers will need, so they can
// import everything from one place.
export type {
  StudioGraph,
  StudioGraphAPI,
  Skill,
  SkillAPI,
  GraphRunLog,
  GraphRunLogAPI,
  CapabilityTier,
  NodeArchetype,
  ConditionExpr,
  GraphEdge,
  StudioNode,
};
