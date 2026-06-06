import React, { useState, useEffect } from 'react';
import { LIFECYCLE_PIPELINE, LifecyclePhase, TransactionProposal } from '../types';
import { TransactionPanel } from './TransactionPanel';
import { apiUrl } from '../config';

interface WorkflowArchitectProps {
  itemId?: string;
  onPhaseChange: (phase: LifecyclePhase) => void;
  currentPhase?: LifecyclePhase;
  initialProposal?: TransactionProposal | null;
}

const PhaseTimeline = ({ currentPhase, onPhaseChange }: { currentPhase: LifecyclePhase, onPhaseChange: (p: LifecyclePhase) => void }) => {
  return (
    <div className="flex items-center justify-between w-full mb-8 px-2">
      {LIFECYCLE_PIPELINE.map((item, index) => {
        const isActive = item.phase === currentPhase;
        const isCompleted = LIFECYCLE_PIPELINE.findIndex(p => p.phase === currentPhase) > index;
        
        return (
          <React.Fragment key={item.phase}>
            <div className="flex flex-col items-center relative group cursor-pointer" onClick={() => onPhaseChange(item.phase)}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all z-10 ${
                isActive ? 'bg-[#0b6b72] text-white ring-4 ring-teal-100' : 
                isCompleted ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                {isCompleted ? '✓' : index + 1}
              </div>
              <span className={`absolute -bottom-6 text-[10px] font-medium whitespace-nowrap transition-colors ${
                isActive ? 'text-[#0b6b72] font-bold' : 'text-gray-400'
              }`}>
                {item.phase.replace('_', ' ')}
              </span>
            </div>
            {index < LIFECYCLE_PIPELINE.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 ${isCompleted ? 'bg-green-500' : 'bg-gray-200'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

const GoalDisplay = ({ phase }: { phase: LifecyclePhase }) => {
  const goalData = LIFECYCLE_PIPELINE.find(p => p.phase === phase);
  if (!goalData) return null;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-6">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold uppercase text-gray-400 tracking-wider">Current Phase Goal</span>
        <div className="h-px flex-1 bg-gray-200" />
      </div>
      <p className="text-gray-800 font-medium mb-3">{goalData.goal}</p>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="font-semibold">Verification:</span>
        <span className="bg-white px-2 py-0.5 rounded border border-gray-200">{goalData.verification}</span>
      </div>
    </div>
  );
};

export const WorkflowArchitect = ({ 
  itemId = 'default', 
  onPhaseChange, 
  currentPhase: propPhase, 
  initialProposal 
}: WorkflowArchitectProps) => {
  const [currentPhase, setCurrentPhase] = useState<LifecyclePhase>(propPhase || 'DISCOVERY');
  const [proposal, setProposal] = useState<TransactionProposal | null>(initialProposal || null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (propPhase) {
      setCurrentPhase(propPhase);
    }
  }, [propPhase]);

  useEffect(() => {
    if (initialProposal !== undefined) {
      setProposal(initialProposal);
    }
  }, [initialProposal]);

  useEffect(() => {
    fetchOrchestratorState();
    // Poll for new proposals every 5 seconds
    const interval = setInterval(fetchOrchestratorState, 5000);
    return () => clearInterval(interval);
  }, [itemId]);

  const fetchOrchestratorState = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/orchestrator/${itemId}`);
      if (res.ok) {
        const data = await res.json();
        setCurrentPhase(data.current_phase);
        setProposal(data.proposal);
      }
    } catch (e) {
      console.error("Failed to fetch orchestrator state", e);
    }
  };

  const handleTransition = async (targetPhase: LifecyclePhase) => {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/orchestrator/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, target_phase: targetPhase })
      });
      if (res.ok) {
        setCurrentPhase(targetPhase);
        onPhaseChange(targetPhase);
        setProposal(null);
      }
    } catch (e) {
      console.error("Transition failed", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto p-4">
      <div className="text-center mb-10">
        <h2 className="text-2xl font-bold text-[#231f19] mb-1">Lifecycle Orchestrator</h2>
        <p className="text-sm text-gray-500 mb-4">Atomic Task Management & Verification</p>
        
        <div className="max-w-2xl mx-auto bg-teal-50 border border-teal-100 rounded-xl p-4 text-left">
          <div className="flex items-start gap-3">
            <div className="p-1.5 bg-teal-100 rounded-lg text-[#0b6b72]">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            </div>
            <div>
              <h4 className="text-xs font-bold text-teal-900 uppercase tracking-wider mb-1">The Collaboration Track</h4>
              <p className="text-xs text-teal-800 leading-relaxed">
                Use this for high-stakes architectural decisions and error recovery. Move tasks through the 7-stage pipeline 
                <span className="font-bold"> (Discovery &rarr; Handover)</span> to ensure technical alignment. 
                Review and approve agent proposals in the Transaction Panel to advance the task safely.
              </p>
            </div>
          </div>
        </div>
      </div>

      <PhaseTimeline currentPhase={currentPhase} onPhaseChange={handleTransition} />
      <GoalDisplay phase={currentPhase} />
      
      <div className="mt-8 border-t border-gray-100 pt-8">
        <TransactionPanel 
          proposal={proposal} 
          onProceed={() => {
            // When proceeding via a proposal, we typically transition to the next logical phase
            // or mark the current proposal as completed.
            handleTransition(LIFECYCLE_PIPELINE.find(p => p.phase === currentPhase)?.phase === 'HANDOVER' ? 'DISCOVERY' : 'IMPLEMENTATION' as any);
          }}
          onModify={(text) => console.log('Modifying transaction:', text)}
        />
      </div>
    </div>
  );
};
