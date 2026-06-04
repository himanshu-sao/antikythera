import React, { useState, useEffect } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { apiUrl } from '../config';
import { PathStep, Pipeline } from '../types';
import { TextHighlighter } from './TextHighlighter';
import { ModalWrapper } from './modals/ManagementModals';



interface Proposal {
  proposal_id: string;
  suggested_step: PathStep;
  reasoning: string;
}

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (token: string) => void;
  service: string; // jira or github
}

const AuthModal = ({ isOpen, onClose, onSubmit, service }: AuthModalProps) => {
  const [token, setToken] = useState('');
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(token);
  };
  
  if (!isOpen) return null;
  
  return (
    <ModalWrapper isOpen={isOpen} onClose={onClose} title={`Authenticate ${service.toUpperCase()}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Enter your {service.toUpperCase()} Personal Access Token:
          </label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter your token"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
          >
            Submit
          </button>
        </div>
      </form>
    </ModalWrapper>
  );
};

export function AutomationStudio() {
  const [instruction, setInstruction] = useState('');
  const [proposal, setProposal] = useState<any | null>(null);
  const [currentPath, setCurrentPath] = useState<PathStep[]>([]);
  const [sandboxState, setSandboxState] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [selectedText, setSelectedText] = useState<string | null>(null);
  const [isBrainstorming, setIsBrainstorming] = useState(false);
  const [brainstormResult, setBrainstormResult] = useState<any | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authService, setAuthService] = useState<'jira' | 'github' | null>(null);
  const [currentStepForAuth, setCurrentStepForAuth] = useState<PathStep | null>(null);
  const [proposalIdForAuth, setProposalIdForAuth] = useState<string | null>(null);



  const handlePropose = async () => {
    if (!instruction) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/automation/propose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          instruction, 
          current_state: sandboxState,
          path_id: 'recording_session' 
        }),
      });
      if (!res.ok) throw new Error('Failed to get proposal');
      const data = await res.json();
      setProposal(data);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExtract = async (text: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/skills/brainstorm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text_sample: text, 
          target_fields: ['field_1'], // Simplified; user would normally define fields
          suggestion: 'Extract the primary value'
        }),
      });
      if (!res.ok) throw new Error('Brainstorming failed');
      const data = await res.json();
      setBrainstormResult(data);
      setIsBrainstorming(true);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveSkill = async () => {
    if (!brainstormResult) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/skills/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_id: `skill_${Date.now()}`,
          name: 'New Extracted Skill',
          category: 'EXTRACTION',
          few_shot_prompt: brainstormResult.proposed_prompt,
          output_schema: brainstormResult.proposed_schema,
          version: '1.0.0'
        }),
      });
      if (!res.ok) throw new Error('Failed to save skill');
      toast.success('Skill promoted and saved!');
      setIsBrainstorming(false);
      setBrainstormResult(null);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!proposal) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/automation/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          proposal_id: proposal.proposal_id,
          step: proposal.suggested_step 
        }),
      });
      if (!res.ok) throw new Error('Execution failed');
      const data = await res.json();
      
      // Check if we got an AUTH_REQUIRED status
      if (data.executed_result && 
          data.executed_result.status === 'auth_required') {
        // Determine which service needs auth based on the step
        const adapterId = proposal.suggested_step.adapter_id;
        const service = adapterId.includes('jira') ? 'jira' : 
                       adapterId.includes('github') ? 'github' : null;
        
        if (service) {
          setAuthService(service);
          setCurrentStepForAuth(proposal.suggested_step);
          setProposalIdForAuth(proposal.proposal_id);
          setIsAuthModalOpen(true);
          setProposal(null); // Clear the proposal while waiting for auth
          return;
        }
      }
      
      // Update Path and Sandbox State for successful execution
      setCurrentPath([...currentPath, proposal.suggested_step]);
      setSandboxState(data.current_state);
      setProposal(null);
      setInstruction('');
      toast.success('Step accepted and executed in sandbox!');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTokenSubmit = async (token: string) => {
    if (!authService || !proposalIdForAuth || !currentStepForAuth) return;
    
    try {
      // Store the token in the vault
      await fetch(`${apiUrl}/api/automation/store-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          service: authService,
          token: token 
        }),
      });
      
      // Retry the step with the new token
      setIsLoading(true);
      const res = await fetch(`${apiUrl}/api/automation/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          proposal_id: proposalIdForAuth,
          step: currentStepForAuth 
        }),
      });
      
      if (!res.ok) throw new Error('Execution failed after auth');
      const data = await res.json();
      
      // Update Path and Sandbox State
      setCurrentPath([...currentPath, currentStepForAuth]);
      setSandboxState(data.current_state);
      toast.success('Step accepted and executed after authentication!');
    } catch (e: any) {
      toast.error(`Authentication failed: ${e.message}`);
    } finally {
      setIsAuthModalOpen(false);
      setAuthService(null);
      setCurrentStepForAuth(null);
      setProposalIdForAuth(null);
      setIsLoading(false);
    }
  };

  const handleCloseAuthModal = () => {
    setIsAuthModalOpen(false);
    setAuthService(null);
    setCurrentStepForAuth(null);
    setProposalIdForAuth(null);
    // Restore the proposal if needed
    if (proposal) {
      setProposal(proposal);
    }
  };

  return (
    <div className="flex h-full w-full bg-[#f6f4ef] text-[#231f19] overflow-hidden">
      {/* Left: Command Center */}
      <div className="w-1/3 border-r border-[#d8d3ca] bg-[#fcfbf8] p-6 flex flex-col gap-6 overflow-y-auto">
        <div>
          <h2 className="text-xl font-bold mb-2">Automation Studio</h2>
          <p className="text-xs text-gray-500 mb-4">Record your process. The AI compiles it into logic.</p>
        </div>

        <div className="space-y-4">
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-bold uppercase text-gray-400">Your Instruction</label>
            <textarea 
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="e.g. 'Fetch all Jira tickets with status New'..."
              className="w-full h-32 p-3 rounded-xl border border-[#d8d3ca] focus:ring-2 focus:ring-[#0b6b72] focus:border-transparent text-sm outline-none resize-none bg-white"
            />
            <button 
              onClick={handlePropose}
              disabled={isLoading}
              className="px-4 py-2 bg-[#0b6b72] text-white rounded-xl text-sm font-bold hover:bg-[#0a5c62] transition-all disabled:opacity-50"
            >
              {isLoading ? 'Compiling...' : 'Propose Step'}
            </button>
          </div>

          {proposal && (
            <div className="p-4 rounded-xl border-2 border-teal-500 bg-teal-50 animate-in fade-in slide-in-from-bottom-2">
              <h4 className="text-xs font-bold text-teal-900 uppercase mb-2">AI Proposal</h4>
              <p className="text-xs text-teal-800 mb-4 italic">"{proposal.reasoning}"</p>
              
              <div className="bg-white p-3 rounded-lg border border-teal-200 mb-4">
                <div className="text-[10px] font-mono text-gray-400 mb-1">DETERMINISTIC STEP</div>
                <div className="text-xs font-bold text-gray-800">
                  {proposal.suggested_step.operator_id} 
                  <span className="ml-2 text-gray-400">via {proposal.suggested_step.adapter_id}</span>
                </div>
              </div>

              <div className="flex gap-2">
                <button 
                  onClick={handleAccept}
                  className="flex-1 px-3 py-2 bg-[#0b6b72] text-white rounded-lg text-xs font-bold hover:bg-[#0a5c62]"
                >
                  Accept & Play
                </button>
                <button 
                  onClick={() => setProposal(null)}
                  className="px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-500 hover:bg-gray-50"
                >
                  Reject
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="mt-auto">
          <div className="p-4 rounded-xl bg-gray-100 border border-gray-200">
            <h4 className="text-xs font-bold uppercase text-gray-400 mb-2">Current Path Sequence</h4>
            <div className="space-y-2">
              {currentPath.length === 0 && <p className="text-[10px] italic text-gray-400">No steps recorded yet.</p>}
              {currentPath.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-[11px] bg-white p-2 rounded border border-gray-200">
                  <span className="font-bold text-gray-400">{idx + 1}.</span>
                  <span className="font-medium text-gray-700">{step.operator_id}</span>
                  <span className="ml-auto text-[9px] text-gray-400">{step.adapter_id}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Right: Live Result / Sandbox */}
      <div className="flex-1 p-8 overflow-y-auto bg-[#f6f4ef]">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-bold">Live Sandbox State</h3>
          <div className="text-[10px] px-2 py-1 bg-amber-100 text-amber-700 rounded-full font-bold uppercase tracking-tighter">
            Simulation Mode
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6">
          {isBrainstorming && (
            <div className="bg-indigo-50 border-2 border-indigo-200 rounded-2xl p-6 animate-in slide-in-from-top-4">
              <div className="flex justify-between items-center mb-4">
                <h4 className="text-sm font-bold text-indigo-900 uppercase tracking-wider">Skill Brainstormer</h4>
                <button onClick={() => setIsBrainstorming(false)} className="text-indigo-400 hover:text-indigo-600">✕</button>
              </div>
              <div className="space-y-4">
                <div className="bg-white p-3 rounded-lg border border-indigo-100 text-xs font-mono text-indigo-700 whitespace-pre-wrap">
                  {brainstormResult?.proposed_prompt}
                </div>
                <div className="flex justify-between items-center">
                  <p className="text-[10px] text-indigo-500 italic">Proposed schema: {JSON.stringify(brainstormResult?.proposed_schema)}</p>
                  <button 
                    onClick={handleSaveSkill}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 transition-all"
                  >
                    Promote to Skill
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="bg-white rounded-2xl shadow-sm border border-[#d8d3ca] overflow-hidden">
            <div className="px-6 py-3 border-b border-[#d8d3ca] bg-gray-50 flex justify-between items-center">
              <span className="text-xs font-bold uppercase text-gray-500">Active Variables</span>
            </div>
            <div className="p-6 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-[10px] uppercase text-gray-400 border-b border-gray-100">
                    <th className="pb-2 font-medium">Variable</th>
                    <th className="pb-2 font-medium">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(sandboxState).map(([key, val]) => (
                    <tr key={key} className="border-b border-gray-50 group">
                      <td className="py-3 font-mono text-xs text-[#0b6b72] font-bold">{key}</td>
                      <td className="py-3 text-xs text-gray-600 max-w-md">
                        {typeof val === 'object' ? (
                          <TextHighlighter 
                            text={JSON.stringify(val, null, 2)} 
                            onExtract={handleExtract} 
                          />
                        ) : (
                          <TextHighlighter 
                            text={String(val)} 
                            onExtract={handleExtract} 
                          />
                        )}
                      </td>
                    </tr>
                  ))}
                  {Object.keys(sandboxState).length === 0 && (
                    <tr>
                      <td colSpan={2} className="py-12 text-center text-xs text-gray-400 italic">
                        Execute a step to see data appearing here.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
      
      {/* Auth Modal */}
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={handleCloseAuthModal} 
        onSubmit={handleTokenSubmit}
        service={authService || 'jira'} 
      />
      
      <Toaster />
    </div>
  );
}