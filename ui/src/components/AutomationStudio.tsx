import React, { useState, useEffect } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { apiUrl } from '../config';
import { PathStep } from '../types';
import { TextHighlighter } from './TextHighlighter';
import { ModalWrapper } from './modals/ManagementModals';

// ----- Types -----
interface Proposal {
  proposal_id: string;
  suggested_step: PathStep;
  reasoning: string;
}

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (token: string) => void;
  service: string; // jira | github
}

// ----- Auth Modal -----
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
          <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300">
            Cancel
          </button>
          <button type="submit" className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600">
            Submit
          </button>
        </div>
      </form>
    </ModalWrapper>
  );
};

// ----- Main Automation Studio Component -----
export function AutomationStudio() {
  // ==== State ==== //
  const [instruction, setInstruction] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>(''); // AI model selector
  const [jiraUrl, setJiraUrl] = useState('');
  const [proposal, setProposal] = useState<any | null>(null);
  const [currentPath, setCurrentPath] = useState<PathStep[]>([]);
  const [sandboxState, setSandboxState] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isBrainstorming, setIsBrainstorming] = useState(false);
  const [brainstormResult, setBrainstormResult] = useState<any | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authService, setAuthService] = useState<'jira' | 'github' | null>(null);
  const [currentStepForAuth, setCurrentStepForAuth] = useState<PathStep | null>(null);
  const [proposalIdForAuth, setProposalIdForAuth] = useState<string | null>(null);

  // ==== Initialize AI model and Jira URL (if previously saved) ==== //
  useEffect(() => {
    const init = async () => {
      // Load AI models
      try {
        const res = await fetch(`${apiUrl}/api/ai-engine/config`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.models) && data.models.length > 0) {
            setSelectedModel(data.models[0].name);
          }
        }
      } catch (e) {
        console.error('Failed to fetch AI models', e);
      }
      // Load saved Jira URL
      try {
        const res = await fetch(`${apiUrl}/api/automation/config/jira_url`);
        if (res.ok) {
          const data = await res.json();
          if (typeof data === 'string') {
            setJiraUrl(data);
          } else if (data.access_token) {
            setJiraUrl(data.access_token);
          }
        }
      } catch (e) {
        console.error('Failed to load Jira URL', e);
      }
    };
    init();
  }, []);


  // ==== Handlers ==== //
  const handlePropose = async () => {
    if (!instruction) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/automation/propose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction,
          model: selectedModel,
          current_state: sandboxState,
          path_id: 'recording_session',
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
          target_fields: ['field_1'],
          suggestion: 'Extract the primary value',
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
          version: '1.0.0',
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
          step: proposal.suggested_step,
        }),
      });
      if (!res.ok) throw new Error('Execution failed');
      const data = await res.json();

      // Auth required?
      if (data.executed_result && data.executed_result.status === 'auth_required') {
        const adapterId = proposal.suggested_step.adapter_id;
        const service = adapterId.includes('jira')
          ? 'jira'
          : adapterId.includes('github')
          ? 'github'
          : null;
        if (service) {
          setAuthService(service as 'jira' | 'github');
          setCurrentStepForAuth(proposal.suggested_step);
          setProposalIdForAuth(proposal.proposal_id);
          setIsAuthModalOpen(true);
          setProposal(null);
          return;
        }
      }

      // Success path
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
      await fetch(`${apiUrl}/api/automation/store-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: authService, token }),
      });
      setIsLoading(true);
      const res = await fetch(`${apiUrl}/api/automation/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalIdForAuth, step: currentStepForAuth }),
      });
      if (!res.ok) throw new Error('Execution failed after auth');
      const data = await res.json();
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
    if (proposal) setProposal(proposal);
  };

  // Save Jira URL to vault via store-token endpoint (service "jira_url")
  const handleSaveJiraUrl = async () => {
    if (!jiraUrl) {
      toast.error('Please enter a Jira URL before saving');
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/automation/store-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'jira_url', token: jiraUrl }),
      });
      if (!res.ok) throw new Error('Failed to store Jira URL');
      toast.success('Jira URL saved successfully');
    } catch (e: any) {
      toast.error(e.message ?? 'Error saving Jira URL');
    } finally {
      setIsLoading(false);
    }
  };

  // ==== UI Sections ==== //
  const renderStepList = () => (
    <div className="flex flex-col gap-4 p-6 bg-[#fcfbf8] border-r border-[#d8d3ca] h-full overflow-y-auto">
      {/* Step 1 – Compose Instruction */}
      <div className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-bold text-gray-500">1.</span>
          <span className="font-medium text-gray-700">Compose Instruction</span>
        </div>
        <label className="block text-xs font-medium text-gray-500 mt-2 mb-1">AI Model</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full rounded border border-[#d8d3ca] py-1 px-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b6b72]"
          >
            {selectedModel && <option value={selectedModel}>{selectedModel}</option>}
          </select>
          {/* Jira instance URL input */}
          <label className="block text-xs font-medium text-gray-500 mt-3 mb-1">Jira Instance URL</label>
          <input
            type="text"
            value={jiraUrl}
            onChange={(e) => setJiraUrl(e.target.value)}
            placeholder="https://your-domain.atlassian.net"
            className="w-full rounded border border-[#d8d3ca] py-1 px-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b6b72]"
          />
          <button
            onClick={handleSaveJiraUrl}
            disabled={isLoading}
            className="mt-1 w-full bg-[#0b6b72] text-white py-1 rounded text-xs font-bold hover:bg-[#0a5c62] disabled:opacity-50"
          >
            {isLoading ? 'Saving…' : 'Save Jira URL'}
          </button>
          <label className="block text-xs font-medium text-gray-500 mt-3 mb-1">Your instruction</label>
        <textarea
                                      value={instruction}
                                      onChange={(e) => setInstruction(e.target.value)}
                                      placeholder='e.g. Fetch all Jira tickets with JQL "(assignee=currentUser() AND status NOT IN (Done, Cancelled, Obsolete)) AND labels = Twistlock-Commercial"'
                                      className="w-full h-28 p-2 border border-[#d8d3ca] rounded resize-none focus:outline-none focus:ring-2 focus:ring-[#0b6b72] text-sm bg-white"
                                    />
                                    {/* Help: supported Jira actions */}
                                    <div className="mt-2 text-xs text-gray-600">
                                      <strong>Supported Jira actions (via this integration):</strong>
                                      <ul className="list-disc list-inside ml-4">
                                        <li>List tickets by JQL (as you type above)</li>
                                        <li>Get details of a ticket – use <code>GET /api/integrations/jira/ticket/&#123;ticketId&#125;</code></li>
                                        <li>Transition an issue – use <code>POST /api/integrations/jira/transition</code></li>
                                        <li>Assign an issue – <code>POST /api/integrations/jira/assign</code></li>
                                        <li>Add a comment – <code>POST /api/integrations/jira/comment</code></li>
                                      </ul>
                                      <em>These endpoints are handled by the JiraAdapter; see <code>api/adapters/jira.py</code> for details.</em>
                                    </div>
        <div className="flex justify-between items-center mt-1 text-xs text-gray-400">
          <span>{instruction.length} / 2000</span>
        </div>
        <div className="flex gap-2 mt-2">
          <button className="px-2 py-0.5 border border-[#0b6b72] text-[#0b6b72] rounded-full text-xs hover:bg-[#0b6b72] hover:text-white transition-colors">
            ⊕ Add context
          </button>
          <button className="px-2 py-0.5 border border-[#0b6b72] text-[#0b6b72] rounded-full text-xs hover:bg-[#0b6b72] hover:text-white transition-colors">
            {} Use variable
          </button>
          <button className="px-2 py-0.5 border border-[#0b6b72] text-[#0b6b72] rounded-full text-xs hover:bg-[#0b6b72] hover:text-white transition-colors">
            ⊟ Examples
          </button>
        </div>
        <button
          onClick={handlePropose}
          disabled={isLoading}
          className="mt-3 w-full bg-[#0b6b72] text-white py-2 rounded text-sm font-bold hover:bg-[#0a5c62] disabled:opacity-50"
        >
          {isLoading ? 'Compiling…' : 'Propose Step'}
        </button>
      </div>

      {/* Step 2 – Refine & Confirm (collapsed) */}
      <div className="p-4 border border-[#e5e7eb] rounded-lg text-gray-500">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-gray-400">2.</span>
          <span className="font-medium text-gray-600">Refine & Confirm</span>
        </div>
      </div>

      {/* Step 3 – Add to Workflow (collapsed) */}
      <div className="p-4 border border-[#e5e7eb] rounded-lg text-gray-500">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-gray-400">3.</span>
          <span className="font-medium text-gray-600">Add to Workflow</span>
        </div>
      </div>
    </div>
  );

  const renderLiveSandbox = () => (
    <div className="flex-1 p-8 overflow-y-auto bg-[#f6f4ef]">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-base font-semibold">Live Sandbox</h3>
        <div className="flex items-center text-xs text-green-600">
          <span className="w-2 h-2 bg-green-600 rounded-full mr-1"></span>
          Live
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
                <button onClick={handleSaveSkill} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 transition-all">
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
                        <TextHighlighter text={JSON.stringify(val, null, 2)} onExtract={handleExtract} />
                      ) : (
                        <TextHighlighter text={String(val)} onExtract={handleExtract} />
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
  );

  const renderPathSequence = () => (
    <div className="w-1/4 border-l border-[#d8d3ca] bg-[#fcfbf8] p-6 overflow-y-auto">
      <h4 className="text-xs font-bold uppercase text-gray-400 mb-3">Current Path Sequence</h4>
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
  );

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-[#f6f4ef] text-[#231f19]">
      {/* Page Header */}
      <div className="p-6 bg-white border-b border-[#d8d3ca]">
        <h1 className="text-2xl font-bold">Automation Studio</h1>
        <p className="text-sm text-gray-500">Record your process. The AI compiles it into logic.</p>
      </div>
      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {renderStepList()}
        {renderLiveSandbox()}
        {renderPathSequence()}
      </div>
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
