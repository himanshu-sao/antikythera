import React from 'react';

interface Proposal {
  id: string;
  description: string;
}

interface Props {
  proposal?: Proposal | null;
  onProceed?: () => void;
  onModify?: (text: string) => void;
}

export const TransactionPanel: React.FC<Props> = ({ proposal, onProceed, onModify }) => {
  const header = (
    <div className="px-6 py-4 border-b border-[#d8d3ca] flex items-center justify-between">
      <h3 className="font-semibold text-base">Proposed Transaction</h3>
    </div>
  );

  if (!proposal) {
    return (
      <div className="bg-white border border-[#d8d3ca] rounded-2xl shadow-sm overflow-hidden">
        {header}
        <div className="p-6 text-center text-gray-400 italic">
          No active transaction proposal. Waiting for agent to suggest a step...
        </div>
        <div className="px-6 py-4 bg-gray-50 border-t border-[#d8d3ca] flex justify-end gap-3">
          <button
            disabled
            className="px-6 py-2 rounded-full text-sm font-bold bg-gray-300 text-gray-500 cursor-not-allowed"
          >
            Proceed
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#d8d3ca] rounded-2xl shadow-sm overflow-hidden">
      {header}
      <div className="p-6">
        <p className="font-medium">{proposal.id}: {proposal.description}</p>
      </div>
      <div className="px-6 py-4 bg-gray-50 border-t border-[#d8d3ca] flex justify-end gap-3">
        <button
          className="px-6 py-2 rounded-full text-sm font-bold bg-indigo-600 text-white hover:bg-indigo-700 transition"
          onClick={onProceed}
        >
          Proceed
        </button>
        <button
          className="px-6 py-2 rounded-full text-sm font-bold bg-gray-200 text-gray-800 hover:bg-gray-300 transition"
          onClick={() => onModify && onModify('')}
        >
          Modify
        </button>
      </div>
    </div>
  );
};
