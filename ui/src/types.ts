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
export type DragEndHandler = (event: {
  active: { id: string };
  over: { id: string } | null;
}) => void | Promise<void>;
