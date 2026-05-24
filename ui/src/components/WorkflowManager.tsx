import React, { useState, useEffect } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { apiUrl } from '../config';

interface Template {
  id: string;
  name: string;
  version: string;
  trigger: { type: string };
  steps: any[];
}

interface WorkflowRun {
  id: string;
  template_id: string;
  template_version: string;
  status: string;
  current_step_id: string;
  started_at: string;
  inputs: any;
}

interface TimelineEvent {
  timestamp: string;
  event_type: string;
  details: any;
  actor: string;
}

interface RunDetailData {
  run: WorkflowRun;
  template: Template;
  timeline: TimelineEvent[];
  bindings: any[];
}

export function WorkflowManager() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [isLoading, setLoading] = useState(false);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/workflows/templates`);
      if (!res.ok) throw new Error('Failed to fetch templates');
      const data = await res.json();
      setTemplates(data);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const triggerTemplate = async (templateId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/workflows/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: templateId, inputs: {} }),
      });
      if (!res.ok) throw new Error('Failed to trigger workflow');
      const data = await res.json();
      toast.success(`Workflow started! Run ID: ${data.run_id}`);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  if (isLoading) return <div className="p-4 text-center text-gray-500">Loading templates...</div>;

  return (
    <div className="flex h-full w-full overflow-hidden bg-[#f6f4ef]">
      {/* Sidebar: Templates List */}
      <div className="w-72 border-r bg-[#fcfbf8] overflow-y-auto border-[#d8d3ca] flex flex-col">
        <div className="p-4 border-b flex justify-between items-center bg-[#f1eee8] border-[#d8d3ca] sticky top-0 z-10">
          <div className="flex flex-col">
            <h3 className="font-bold text-[#231f19] text-sm uppercase tracking-wider">Templates</h3>
            <p className="text-[10px] text-[#6f6a63]">Automation recipes</p>
          </div>
          <button 
            onClick={() => toast.success("Template Creator coming soon!")} 
            className="p-1.5 hover:bg-[#d8d3ca] rounded-lg text-xs bg-[#0b6b72] text-white transition-colors font-medium shadow-sm"
          >
            + New
          </button>
        </div>
        <div className="p-2 space-y-2 overflow-y-auto">
          {templates.map(t => (
            <div 
              key={t.id} 
              onClick={() => setSelectedTemplate(t)}
              className={`p-3 cursor-pointer rounded-xl border transition-all ${
                selectedTemplate?.id === t.id 
                ? 'bg-[#f9fdfd] border-[#0b6b72] shadow-sm ring-1 ring-[#0b6b72]/20' 
                : 'bg-white border-transparent hover:border-[#d8d3ca] hover:bg-[#fcfbf8]'
              }`}
            >
              <div className="font-bold text-sm text-[#231f19]">{t.name}</div>
              <div className="text-[11px] text-[#6f6a63] leading-tight mt-1">v{t.version} • {t.trigger.type}</div>
            </div>
          ))}
          {templates.length === 0 && <div className="p-4 text-xs text-[#6f6a63] italic text-center">No templates found.</div>}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-8 bg-[#f6f4ef]">
        {!selectedTemplate ? (
          <div className="h-full flex flex-col items-center justify-center text-[#6f6a63] text-center">
            <div className="w-16 h-16 bg-[#ebe7df] rounded-full flex items-center justify-center mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#6f6a63]"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            </div>
            <p className="text-lg font-medium text-[#231f19]">No Template Selected</p>
            <p className="text-sm opacity-70">Select a workflow from the sidebar to view and trigger its blueprint</p>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-8">
            <div className="flex justify-between items-start">
              <div className="flex flex-col gap-1">
                <h2 className="text-3xl font-bold text-[#231f19] tracking-tight">{selectedTemplate.name}</h2>
                <div className="flex items-center gap-2 text-sm text-[#6f6a63]">
                  <span className="font-mono bg-[#ebe7df] px-1.5 py-0.5 rounded text-[11px]">ID: {selectedTemplate.id}</span>
                  <span>•</span>
                  <span>Version {selectedTemplate.version}</span>
                </div>
              </div>
              <button 
                onClick={() => triggerTemplate(selectedTemplate.id)}
                className="px-5 py-2.5 bg-[#0b6b72] text-white rounded-xl text-sm font-bold hover:bg-[#0a5c62] transition-all shadow-lg hover:shadow-[#0b6b72]/20 flex items-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Trigger Workflow
              </button>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-[#d8d3ca] overflow-hidden">
              <div className="p-6 border-b border-[#d8d3ca] bg-[#fcfbf8] flex justify-between items-center">
                <h3 className="text-lg font-bold text-[#231f19]">Blueprint Execution Path</h3>
                <div className="px-3 py-1 bg-[#d5e7e6] text-[#0b6b72] rounded-full text-[11px] font-bold uppercase tracking-wider">
                  Trigger: {selectedTemplate.trigger.type}
                </div>
              </div>
              <div className="p-8">
                <div className="space-y-0">
                  {selectedTemplate.steps.map((step, idx) => (
                    <div key={step.step_id} className="flex gap-6">
                      <div className="flex flex-col items-center">
                        <div className="w-8 h-8 rounded-full bg-[#231f19] text-white flex items-center justify-center text-xs font-bold shadow-sm">
                          {idx + 1}
                        </div>
                        {idx < selectedTemplate.steps.length - 1 && (
                          <div className="w-0.5 h-10 bg-[#d8d3ca] relative">
                            <div className="absolute top-0 left-[-3px] w-2 h-2 rounded-full bg-[#d8d3ca]"></div>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 pb-8">
                        <div className="p-4 rounded-xl border border-[#d8d3ca] bg-[#fcfbf8] hover:border-[#0b6b72] hover:bg-[#f9fdfd] transition-all group relative">
                          <div className="flex justify-between items-start mb-2">
                            <span className="font-bold text-sm text-[#231f19]">{step.name}</span>
                            <span className="text-[10px] px-2 py-0.5 bg-[#ebe7df] text-[#6f6a63] rounded-full uppercase font-bold tracking-tighter">
                              {step.category}
                            </span>
                          </div>
                          <div className="text-xs text-[#6f6a63] leading-relaxed">
                            {step.config?.description || `Action managed by ${step.config?.adapter || 'INTERNAL'} adapter`}
                          </div>
                          <div className="mt-3 pt-3 border-t border-gray-100 flex justify-between items-center text-[10px] text-gray-400 font-mono">
                            <span>Adapter: {step.config?.adapter || 'INTERNAL'}</span>
                            <span className="text-[#0b6b72] opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer font-bold">
                              Debug Step →
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
