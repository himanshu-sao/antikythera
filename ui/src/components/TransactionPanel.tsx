import React from 'react';
import { TransactionProposal, LifecyclePhase } from '../types';

interface TransactionPanelProps {
  proposal: TransactionProposal | null;
  onProceed: () => void;
  onModify: (text: string) => void;
}

export const TransactionPanel = ({ proposal, onProceed, onModify }: TransactionPanelProps) => {
  if (!proposal) {
    return (
      <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-2xl">
        <p className="text-gray-400 text-sm italic">No active transaction proposal. Waiting for agent to suggest a step...</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#d8d3ca] rounded-2xl shadow-sm overflow-hidden">
      <div className="bg-gray-50 px-6 py-3 border-b border-[#d8d3ca] flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase text-gray-500 tracking-wider">Proposed Transaction</span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
            proposal.status === 'PROPOSED' ? 'bg-blue-100 text-blue-600' : 
            proposal.status === 'EXECUTING' ? 'bg-amber-100 text-amber-600' : 'bg-green-100 text-green-600'
          }`}>
            {proposal.status}
          </span>
        </div>
        <span className="text-xs text-gray-400 font-mono">{proposal.id}</span>
      </div>

      <div className="p-6 space-y-6">
        {/* Context Bundle */}
        <div>
          <label className="text-[10px] font-bold text-gray-400 uppercase block mb-2">Working Context Bundle</label>
          <div className="flex flex-wrap gap-2">
            {proposal.context.map(file => (
              <span key={file} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded border border-gray-200 font-mono">
                {file}
              </span>
            ))}
          </div>
        </div>

        {/* Implementation Plan */}
        <div>
          <label className="text-[10px] font-bold text-gray-400 uppercase block mb-2">Implementation Plan</label>
          <div className="bg-gray-50 p-3 rounded-lg text-sm text-gray-700 whitespace-pre-wrap border border-gray-100 leading-relaxed">
            {proposal.plan}
          </div>
        </div>

        {/* Verification Plan */}
        <div>
          <label className="text-[10px] font-bold text-gray-400 uppercase block mb-2">Verification Strategy</label>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <div className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
            {proposal.verification}
          </div>
        </div>
      </div>

      <div className="px-6 py-4 bg-gray-50 border-t border-[#d8d3ca] flex justify-end gap-3">
        <button 
          onClick={() => onModify('Please adjust the plan to...')}
          className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
        >
          Modify
        </button>
        <button 
          onClick={onProceed}
          disabled={proposal.status === 'EXECUTING'}
          className={`px-6 py-2 rounded-full text-sm font-bold transition-all shadow-sm ${
            proposal.status === 'EXECUTING' 
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
            : 'bg-[#0b6b72] text-white hover:bg-[#0a5c62]'
          }`}
        >
          {proposal.status === 'EXECUTING' ? 'Executing...' : 'Proceed'}
        </button>
      </div>
    </div>
  );
};
