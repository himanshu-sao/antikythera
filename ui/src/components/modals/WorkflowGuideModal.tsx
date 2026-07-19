import React from 'react';

// Workflow Guide modal shown from the board ("How it works" button).
// Re-implemented (P3.8.4/#3): the "How it works" affordance previously existed
// only on WorkflowDiagram.tsx (workflow view), not on the /pipeline board the
// e2e suite exercises. This modal gives the board its own guided-tour surface.
// The h2 text "Workflow Guide" and the ✕ close button are deliberate to match
// the pipeline.spec "should open and close workflow guide" assertions.
const STAGE_GUIDE: { stage: string; title: string; description: string }[] = [
  { stage: 'INTAKE', title: 'Intake', description: 'New automation ideas are captured and logged.' },
  { stage: 'REFINEMENT', title: 'Refinement', description: 'Ideas are analyzed, scoped, and detailed.' },
  { stage: 'REVIEW_SPEC', title: 'Review Spec', description: 'The detailed specification is reviewed for correctness.' },
  { stage: 'ARCHITECTURE', title: 'Architecture', description: 'Technical design and system architecture are defined.' },
  { stage: 'REVIEW_ARCH', title: 'Review Arch', description: 'Architecture is reviewed by the team for viability.' },
  { stage: 'TESTING', title: 'Testing', description: 'Test cases and verification strategies are developed.' },
  { stage: 'REVIEW_TEST', title: 'Review Test', description: 'The test plan is reviewed and approved.' },
  { stage: 'APPROVED', title: 'Approved', description: 'The item is fully vetted and ready for implementation.' },
  { stage: 'EXECUTING', title: 'Executing', description: 'The automation is being actively developed.' },
  { stage: 'DONE', title: 'Done', description: 'Implementation is complete, verified, and deployed.' },
];

export const WorkflowGuideModal = ({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-[60]">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-900">Workflow Guide</h2>
          <button
            onClick={onClose}
            aria-label="✕"
            className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
          >
            ✕
          </button>
        </div>
        <div className="p-6">
          <p className="text-gray-600 mb-4">How an idea transforms into a completed automation.</p>
          <ol className="space-y-3">
            {STAGE_GUIDE.map((s, i) => (
              <li key={s.stage} className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--accent)] text-white flex items-center justify-center text-xs font-bold">
                  {i + 1}
                </span>
                <div>
                  <div className="font-semibold text-gray-900 text-sm">{s.title}</div>
                  <div className="text-sm text-gray-500">{s.description}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
};
