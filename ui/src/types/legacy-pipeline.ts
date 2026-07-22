// Legacy Pipeline Types (Board-Scoped)
//
// Restored per docs/plans/mighty-greeting-cookie.md §7 Correction A.
// The Kanban board's pipeline-detail view (PipelineDashboard, PipelineFlowchart, usePipelineState)
// imports these symbols. They are NOT shared with the Studio surface (studio.ts).
// This module exists solely to make the board compile again.

export interface PathStep {
  step_id: string;
  name: string;
  operator_id: string;
  adapter_id: string;
  config: Record<string, unknown>;
  next_step?: string;
}

export interface Path {
  path_id: string;
  name: string;
  steps: PathStep[];
}

export interface Pipeline {
  name: string;
  description?: string;
  status: string;
  trigger: { type: string };
  pipeline_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface PipelineItem {
  id: string;
  title: string;
  stage: string;
  order: number;
  priority: 'low' | 'medium' | 'high' | 'critical' | string;
  complexity?: 'trivial' | 'simple' | 'complex' | 'auto' | string;
  goal?: string;
  description?: string;
  source_type?: string;
  source_value?: string;
  due_date?: string;
  confidence_score?: number;
  assigned_agent?: string | null;
  blocked_reason?: string | null;
  // Board adapters read these runtime fields written by api/managers/kanban_state_manager.py
  // and the orchestrator; verified against a live GET /api/state response (Correction A).
  comments?: unknown[];
  history?: unknown[];
  review_status?: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface PipelineState {
  items: Record<string, PipelineItem>;
}

// Board view-model types (derived in ui/src/utils/boardAdapter.ts). These describe the
// column/card shape the Kanban board renders after transforming /api/state; they are NOT
// returned by the backend. Board-scoped, Studio-decoupled (dec #22 / §7 Correction A).
export interface BoardCard {
  id: string;
  title: string;
  description: string;
  status: string;
  order: number;
  priority: string;
  complexity: string;
  confidence_score: number | null;
  comments: unknown[];
  history: unknown[];
  blocked_reason: string | null;
  assigned_agent: string | null;
  review_status: string;
  created_at: string;
  updated_at: string;
}

export interface BoardColumn {
  id: string;
  title: string;
  order: number;
  cards: BoardCard[];
}