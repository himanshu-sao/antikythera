import React from 'react';
import { WorkflowManager } from '../WorkflowManager';
import { IntegrationsManager } from '../IntegrationsManager';
import { WorkflowBuilder } from '../WorkflowBuilder';

interface ModalWrapperProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title: string;
}

const ModalWrapper = ({ isOpen, onClose, children, title }: ModalWrapperProps) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl max-h-[90vh] overflow-auto p-6 w-full h-full flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold">{title}</h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full transition-colors">✕</button>
        </div>
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
};

export const WorkflowModal = ({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) => (
  <ModalWrapper isOpen={isOpen} onClose={onClose} title="Workflow Automation">
    <WorkflowManager />
  </ModalWrapper>
);

export const IntegrationsModal = ({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) => (
  <ModalWrapper isOpen={isOpen} onClose={onClose} title="Integration Hub">
    <IntegrationsManager />
  </ModalWrapper>
);

export const BuilderModal = ({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) => (
  <ModalWrapper isOpen={isOpen} onClose={onClose} title="Workflow Architect">
    <WorkflowBuilder />
  </ModalWrapper>
);
