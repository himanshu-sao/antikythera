/** Pipeline item as stored in pipeline-state.json */
export interface PipelineItem {
  id: string;
  title: string;
  priority: string;
  stage: string;
  confidence_score?: number;
  updated_at: string;
  created_at?: string;
  assigned_agent?: string | null;
  blocked_reason?: string | null;
  review_status?: string;
  order?: number;
  history?: Array<{ stage: string; at: string; agent?: string }>;
  source_type?: string;
  source_value?: string;
  due_date?: string;
}

/** Pipeline state returned by the API */
export interface PipelineState {
  items: Record<string, PipelineItem>;
  last_heartbeat?: string;
}

/** Canonical Board Models */
export interface BoardColumn {
  id: string;
  title: string;
  order: number;
  cards: BoardCard[];
}

export interface BoardCard {
  id: string;
  title: string;
  description?: string;
  comments?: CardComment[];
  metadata?: Record<string, unknown>;
  status: string;
  order: number;
  priority: string;
  confidence_score?: number;
  history?: Array<{ stage: string; at: string; agent?: string }>;
  blocked_reason?: string | null;
  assigned_agent?: string | null;
  review_status?: string;
  created_at?: string;
  updated_at: string;
  source_type?: string;
  source_value?: string;
  due_date?: string;
}

export interface CardComment {
  id: string;
  author?: string;
  body: string;
  createdAt: string;
}

/** Card data passed to KanbanColumn */
export interface KanbanCardData {
  id: string;
  title: string;
  priority: string;
  confidence_score?: number;
  stage: string;
  order?: number;
  source_type?: string;
  source_value?: string;
  due_date?: string;
  updated_at: string;
}

/** Drag end event handler type */

/** Lifecycle Orchestration Types */
export type LifecyclePhase = 
  | 'DISCOVERY' 
  | 'BLUEPRINT' 
  | 'IMPLEMENTATION' 
  | 'UNIT_VERIFY' 
  | 'INTEGRATION' 
  | 'SYSTEM_VAL' 
  | 'HANDOVER';

export interface PhaseGoal {
  phase: LifecyclePhase;
  goal: string;
  verification: string;
}

export interface TransactionProposal {
  id: string;
  phase: LifecyclePhase;
  context: string[]; // List of active files
  plan: string;
  verification: string;
  status: 'PROPOSED' | 'EXECUTING' | 'COMPLETED' | 'FAILED';
}

export const LIFECYCLE_PIPELINE: PhaseGoal[] = [
  { phase: 'DISCOVERY', goal: 'Complete map of affected files and a clear problem statement.', verification: 'Context Audit' },
  { phase: 'BLUEPRINT', goal: 'Signed-off interface, spec, or component tree.', verification: 'Spec Review' },
  { phase: 'IMPLEMENTATION', goal: 'Single, modular, and functional code unit.', verification: 'Code Inspection' },
  { phase: 'UNIT_VERIFY', goal: '100% pass rate for tests specific to this module.', verification: 'Unit Test Run' },
  { phase: 'INTEGRATION', goal: 'Module interacts correctly with its neighbors.', verification: 'Integration Test' },
  { phase: 'SYSTEM_VAL', goal: 'Zero regressions in the entire project.', verification: 'Full System Suite' },
  { phase: 'HANDOVER', goal: 'Updated TODO.md, README.md, and clear task status.', verification: 'TODO Sync' },
];
