import React from 'react';

export function SkeletonCard() {
  return (
    <div className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm mb-3 animate-pulse">
      <div className="h-3 bg-gray-200 rounded w-1/3 mb-3"></div>
      <div className="h-2 bg-gray-100 rounded w-full mb-2"></div>
      <div className="h-2 bg-gray-100 rounded w-5/6 mb-4"></div>
      <div className="flex justify-between items-center">
        <div className="h-2 bg-gray-200 rounded w-1/4"></div>
        <div className="h-2 bg-gray-100 rounded w-1/4"></div>
      </div>
    </div>
  );
}

export function SkeletonBoard() {
  const STAGES = [
    "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
    "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
  ];

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 snap-x">
      {STAGES.map(stage => (
        <div key={stage} className="flex-shrink-0 snap-start w-80">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">{stage}</h3>
            <div className="h-4 w-4 bg-gray-200 rounded-full animate-pulse"></div>
          </div>
          <div className="space-y-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      ))}
    </div>
  );
}
