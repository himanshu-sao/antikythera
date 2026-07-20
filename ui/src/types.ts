export interface LifecyclePhaseData {
  phase: LifecyclePhase;
  goal: string;
  verification: string;
}

// The 7 lifecycle stages the Workflow Architect (Lifecycle Orchestrator) drives an item
// through via /api/orchestrator/transition. Matches LIFECYCLE_PIPELINE below.
export type LifecyclePhase =
  | 'DISCOVERY'
  | 'BLUEPRINT'
  | 'IMPLEMENTATION'
  | 'UNIT_TEST'
  | 'INTEGRATION_TEST'
  | 'SYSTEM_VALIDATION'
  | 'HANDOVER';

// Matches the Proposal shape consumed by TransactionPanel.tsx.
// The orchestrator (GET /api/orchestrator/{id}) may return a richer object under
// `current_proposal`; only id+description are rendered. Extra optional fields are
// tolerated so backend-supplied proposals don't fail the prop type.
export interface TransactionProposal {
  id: string;
  description: string;
  context?: string[];
  plan?: string;
  verification?: string;
}

export const LIFECYCLE_PIPELINE: LifecyclePhaseData[] = [
  { 
    phase: 'DISCOVERY', 
    goal: 'Context Audit – Complete map of affected files and a clear problem statement', 
    verification: 'Requirements document approved' 
  },
  { 
    phase: 'BLUEPRINT', 
    goal: 'Signed-off interface, spec, or component', 
    verification: 'Architecture diagram and design spec completed' 
  },
  { 
    phase: 'IMPLEMENTATION', 
    goal: 'Single, modular, and functional code unit – Code Inspection', 
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
