import React, { useState } from 'react';
import { LifecyclePhase } from '../types';
import { WorkflowArchitect } from '../WorkflowArchitect';

// Simple ModalWrapper placeholder for testing purposes
export const ModalWrapper = ({ isOpen, onClose, title, children }: { isOpen: boolean; onClose: () => void; title: string; children: React.ReactNode }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/30 z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-lg w-11/12 max-w-3xl p-4" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold">{title}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800">×</button>
        </div>
        {children}
      </div>
    </div>
  );
};

export const BuilderModal = ({ isOpen, onClose, itemId }: { isOpen: boolean; onClose: () => void; itemId?: string }) => {
  const [phase, setPhase] = useState<LifecyclePhase>('DISCOVERY');
  const mockProposal = {
    id: 'tx-8821',
    status: 'PROPOSED',
    context: ['file1.txt', 'file2.txt'],
    plan: 'Mock plan details',
    verification: 'Mock verification details',
  };

  return (
    <ModalWrapper isOpen={isOpen} onClose={onClose} title="Workflow Architect">
      <WorkflowArchitect itemId={itemId || 'default'} onPhaseChange={setPhase} initialProposal={mockProposal} />
    </ModalWrapper>
  );
};
