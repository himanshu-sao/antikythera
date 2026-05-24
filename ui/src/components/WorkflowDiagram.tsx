import React from 'react';

const STAGE_DETAILS = {
  INTAKE: {
    title: 'Intake',
    description: 'New automation ideas are captured and logged.',
    color: 'bg-blue-500',
  },
  REFINEMENT: {
    title: 'Refinement',
    description: 'Ideas are analyzed, scoped, and detailed.',
    color: 'bg-cyan-500',
  },
  REVIEW_SPEC: {
    title: 'Review Spec',
    description: 'The detailed specification is reviewed for correctness.',
    color: 'bg-indigo-500',
  },
  ARCHITECTURE: {
    title: 'Architecture',
    description: 'Technical design and system architecture are defined.',
    color: 'bg-purple-500',
  },
  REVIEW_ARCH: {
    title: 'Review Arch',
    description: 'Architecture is reviewed by the team for viability.',
    color: 'bg-fuchsia-500',
  },
  TESTING: {
    title: 'Testing',
    description: 'Test cases and verification strategies are developed.',
    color: 'bg-pink-500',
  },
  REVIEW_TEST: {
    title: 'Review Test',
    description: 'The test plan is reviewed and approved.',
    color: 'bg-rose-500',
  },
  APPROVED: {
    title: 'Approved',
    description: 'The item is fully vetted and ready for implementation.',
    color: 'bg-orange-500',
  },
  EXECUTING: {
    title: 'Executing',
    description: 'The automation is being actively developed.',
    color: 'bg-yellow-500',
  },
  DONE: {
    title: 'Done',
    description: 'Implementation is complete, verified, and deployed.',
    color: 'bg-green-500',
  },
};

const STAGES = Object.keys(STAGE_DETAILS);

export function WorkflowDiagram({ onClose }: { onClose: () => void }) {
  return (
    <div className="p-6 overflow-y-auto">
      <div className="mb-8 text-center">
        <h3 className="text-2xl font-bold text-gray-900 mb-2">Pipeline Workflow</h3>
        <p className="text-gray-500">How an idea transforms into a completed automation</p>
      </div>

      <div className="flex flex-col gap-8 relative">
        {STAGES.map((stage, index) => (
          <div key={stage} className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-full ${STAGE_DETAILS[stage].color} text-white flex items-center justify-center font-bold shrink-0 shadow-md`}>
              {index + 1}
            </div>
            <div className="flex-1 bg-white border border-gray-200 p-4 rounded-xl shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-gray-900">{STAGE_DETAILS[stage].title}</span>
                <span className="text-xs font-mono text-gray-400">{stage}</span>
              </div>
              <p className="text-sm text-gray-600">{STAGE_DETAILS[stage].description}</p>
            </div>
          </div>
        ))}

        {/* Connecting Line (SVG) */}
        <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-gray-200 -z-10" />
      </div>

      <div className="mt-12 p-4 bg-indigo-50 rounded-xl border border-indigo-100">
        <h4 className="font-semibold text-indigo-900 mb-2 flex items-center gap-2">
          <span>ℹ️</span> How it works
        </h4>
        <ul className="text-sm text-indigo-700 space-y-2 list-disc list-inside">
          <li>Items start in <strong>Intake</strong>.</li>
          <li>They move sequentially through refinement and review gates.</li>
          <li>Each review stage (Spec, Arch, Test) acts as a quality gate before moving forward.</li>
          <li>Once <strong>Approved</strong>, the item enters the <strong>Executing</strong> phase for build.</li>
          <li>The process ends when the item is marked as <strong>Done</strong>.</li>
        </ul>
      </div>
    </div>
  );
}
