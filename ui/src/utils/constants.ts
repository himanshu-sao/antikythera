// Constants for the application
export const STAGES = [
  "INTAKE", 
  "REFINEMENT", 
  "REVIEW_SPEC", 
  "ARCHITECTURE",
  "REVIEW_ARCH", 
  "TESTING", 
  "REVIEW_TEST", 
  "APPROVED", 
  "EXECUTING", 
  "DONE"
];

export const STAGE_TITLES: Record<string, string> = {
  INTAKE: 'Intake',
  REFINEMENT: 'Refinement',
  REVIEW_SPEC: 'Review Spec',
  ARCHITECTURE: 'Architecture',
  REVIEW_ARCH: 'Review Arch',
  TESTING: 'Testing',
  REVIEW_TEST: 'Review Test',
  APPROVED: 'Approved',
  EXECUTING: 'Executing',
  DONE: 'Done',
};