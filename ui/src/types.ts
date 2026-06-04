/** Canonical Board Models */

export enum Stage {
  INTAKE = "INTAKE",
  REFINEMENT = "REFINEMENT",
  REVIEW_SPEC = "REVIEW_SPEC",
  ARCHITECTURE = "ARCHITECTURE",
  REVIEW_ARCH = "REVIEW_ARCH",
  TESTING = "TESTING",
  REVIEW_TEST = "REVIEW_TEST",
  APPROVED = "APPROVED",
  EXECUTING = "EXECUTING",
  DONE = "DONE"
}

export interface PipelineItem {
  id: string;
  stage: Stage;
  title: string;
  description?: string;
  goal?: string;
  priority: "low" | "medium" | "high";
  blocked?: boolean;
  blockedReason?: string;
  confidence?: number;
  confidenceUp: boolean;
  confidenceDown: boolean;
  tags?: string[];
  tagsDown: string[];
  tagsUp: string[];
  comments?: Comment[];
  artifacts?: Record<string, Artifact>;
  inlineOutput?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Comment {
  id: string;
  author: string;
  body: string;
  createdAt: string;
}

export interface Artifact {
  name: string;
  content: string;
  contentType?: string;
  createdAt: string;
}

export enum Priority {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high"
}

export interface BoardState {
  columns: Record<Stage, PipelineItem[]>;
}

// --- Automation Types (Low-Code Compiler) ---

export enum ExecutionMode {
  ADAPTER = "adapter",
  SCRIPT = "script"
}

export enum ExecutionStatus {
  PENDING = "pending",
  RUNNING = "running",
  SUCCESS = "success",
  FAILED = "failed",
  SKIPPED = "skipped"
}

export enum ConditionType {
  EQUALS = "equals",
  CONTAINS = "contains",
  REGEX_MATCH = "regex_match",
  IN_LIST = "in_list",
  EXISTS = "exists"
}

export interface Condition {
  type: ConditionType;
  field: string;
  value: any;
  case_sensitive?: boolean;
}

export interface ConditionLogic {
  logic: "AND" | "OR";
  conditions: Condition[];
}

export interface PathStep {
  step_id: string;
  operator_id: string;
  adapter_id: string;
  config: Record<string, any>;
  input_ref?: string;
  output_ref?: string;
  mode?: ExecutionMode;
  condition?: Record<string, any>; // ConditionDict or ConditionLogic
  loop_over?: { source: string; iterator_var: string };
}

export interface Path {
  path_id: string;
  pipeline_id: string;
  name: string;
  steps: PathStep[];
  is_active: boolean;
  created_at: string;
}

export interface Pipeline {
  pipeline_id: string;
  name: string;
  description?: string;
  paths: string[];
  trigger: { type: "CRON" | "WEBHOOK" | "MANUAL"; schedule?: string };
  global_context?: Record<string, string>;
  status: string;
  created_at: string;
}

export interface ExecutionLog {
  run_id?: string;
  pipeline_id?: string;
  step_id: string;
  parent_run_id?: string;
  started_at: string;
  ended_at?: string;
  status: ExecutionStatus;
  execution_reason?: string;
  extracted_fields: Record<string, any>;
  result_data?: Record<string, any>;
  error_detail?: string;
  duration_ms?: number;
}

export interface PipelineRun {
  run_id: string;
  pipeline_id: string;
  started_at: string;
  ended_at?: string;
  status: string;
  error?: string;
  duration_ms?: number;
  logs: ExecutionLog[];
}

// Skill Models
export enum SkillCategory {
  EXTRACTION = "EXTRACTION",
  TRANSFORMATION = "TRANSFORMATION",
  CLASSIFICATION = "CLASSIFICATION",
  PARSING = "PARSING"
}

export interface Skill {
  skill_id: string;
  name: string;
  category: SkillCategory;
  few_shot_prompt: string;
  output_schema: Record<string, any>;
  version?: string;
  created_at?: string;
  skill_type?: "action" | "parse";
  parser_config?: Record<string, any>;
}

// --- Lifecycle Pipeline Models (for WorkflowArchitect) ---

export type LifecyclePhase = 
  | 'DISCOVERY' 
  | 'BLUEPRINT' 
  | 'IMPLEMENTATION' 
  | 'UNIT_TEST' 
  | 'INTEGRATION_TEST' 
  | 'SYSTEM_VALIDATION' 
  | 'HANDOVER';

export interface LifecyclePhaseData {
  phase: LifecyclePhase;
  goal: string;
  verification: string;
}

export const LIFECYCLE_PIPELINE: LifecyclePhaseData[] = [
  { 
    phase: 'DISCOVERY', 
    goal: 'Understand the problem domain and gather requirements', 
    verification: 'Requirements document approved' 
  },
  { 
    phase: 'BLUEPRINT', 
    goal: 'Design the architecture and system components', 
    verification: 'Architecture diagram and design spec completed' 
  },
  { 
    phase: 'IMPLEMENTATION', 
    goal: 'Develop the solution based on the blueprint', 
    verification: 'Code completed and linted' 
  },
  { 
    phase: 'UNIT_TEST', 
    goal: 'Write and pass unit tests for all components', 
    verification: 'All unit tests passing with >80% coverage' 
  },
  { 
    phase: 'INTEGRATION_TEST', 
    goal: 'Verify components work together correctly', 
    verification: 'Integration tests passing' 
  },
  { 
    phase: 'SYSTEM_VALIDATION', 
    goal: 'Validate the complete system meets requirements', 
    verification: 'System validation checklist completed' 
  },
  { 
    phase: 'HANDOVER', 
    goal: 'Prepare and deliver the final solution', 
    verification: 'Documentation and delivery artifacts complete' 
  }
];

export interface TransactionProposal {
  proposal_id: string;
  phase: LifecyclePhase;
  description: string;
  actions: TransactionAction[];
  confidence?: number;
  created_at?: string;
}

export interface TransactionAction {
  type: 'create_file' | 'modify_file' | 'run_command' | 'create_pr';
  target?: string;
  content?: string;
  description: string;
}