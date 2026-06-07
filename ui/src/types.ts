export const LIFECYCLE_PIPELINE: LifecyclePhaseData[] = [
  { 
    phase: 'DISCOVERY', 
    goal: 'Complete map of affected files and a clear problem statement', 
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
