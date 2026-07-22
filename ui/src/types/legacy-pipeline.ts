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
  priority: 'low' | 'medium' | 'high' | 'critical';
  complexity?: 'trivial' | 'simple' | 'complex' | 'auto';
  goal?: string;
  description?: string;
  source_type?: string;
  source_value?: string;
  due_date?: string;
  confidence_score?: number;
  assigned_agent?: string;
  blocked_reason?: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface PipelineState {
  items: Record<string, PipelineItem>;
}