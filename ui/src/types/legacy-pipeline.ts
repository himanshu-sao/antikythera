// Legacy pipeline types — board-scoped ONLY (dec #22 / §7 Correction A).
//
// These are NOT Studio types. They restore the symbols the Kanban board's
// pipeline-detail view (PipelineDashboard, PipelineFlowchart, usePipelineState)
// imports from `../types`, which were dropped from `src/types.ts` in a prior
// half-finished refactor (pre-existing breakage, unrelated to the Studio work).
//
// Field shapes mirror the backend models in `api/models/automation.py`
// (PathStep / Path / Pipeline) and the live `pipeline-state.json` item shape
// (PipelineItem / PipelineState) returned by GET /api/state (board_router).
//
// Studio node/graph types live in `./studio.ts` and are never used by the board.

// --- PathStep / Path / Pipeline (from /api/pipelines/{id} → { pipeline, paths }) ---

export interface PathStep {
  step_id: string;
  operator_id: string;
  adapter_id: string;
  config: Record<string, unknown>;
  input_ref?: string;
  output_ref?: string;
  mode?: string;            // ExecutionMode; kept loose for the board
  condition?: Record<string, unknown>;
  loop_over?: { source: string; iterator_var: string };
}

export interface Path {
  path_id: string;
  pipeline_id?: string;
  name: string;
  steps: PathStep[];
  is_active?: boolean;
  created_at?: string;
}

export interface Pipeline {
  pipeline_id?: string;
  name: string;
  description?: string;
  paths: string[];          // list of path_ids (backend stores ids; detail view enriches)
  trigger: { type: string; config?: Record<string, unknown> };
  global_context?: Record<string, string>;
  status: string;
}

// --- PipelineItem / PipelineState (from GET /api/state → pipeline-state.json) ---

export interface PipelineItemComment {
  author?: string;
  body?: string;
  comment_id?: string;
  created_at?: string;
}

export interface PipelineItemHistoryEntry {
  stage: string;
  at: string;            // ISO 8601
  agent?: string;
}

export interface PipelineItem {
  title: string;
  stage: string;
  priority?: string;
  confidence_score?: number;
  description?: string;
  created_at?: string;
  updated_at?: string;
  comments?: PipelineItemComment[];
  history?: PipelineItemHistoryEntry[];
  assigned_agent?: string | null;
  complexity?: string;
  goal?: string;
  source_type?: string;
  source_value?: string;
  due_date?: string;
  inline_output?: string;
  order?: number;
}

export interface PipelineState {
  items: Record<string, PipelineItem>;
}
