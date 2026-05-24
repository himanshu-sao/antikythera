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
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
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

  const fetchRunDetails = async (runId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/workflows/runs/${runId}`);
      if (!res.ok) throw new Error('Failed to fetch run details');
      return await res.json();
    } catch (e: any) {
      toast.error(e.message);
      return null;
    }
  };

  if (isLoading) return <div className="p-4 text-center text-gray-500">Loading templates...</div>;

  return (
    <div className="flex h-full w-full overflow-hidden bg-gray-50">
      {/* Sidebar: Templates List */}
      <div className="w-64 border-r bg-white overflow-y-auto">
        <div className="p-4 border-b flex justify-between items-center bg-gray-50">
          <h3 className="font-bold text-gray-700">Templates</h3>
          <button 
            onClick={() => toast.success("Template Creator coming soon!")} 
            className="p-1 hover:bg-gray-200 rounded text-xs bg-indigo-600 text-white px-2"
          >
            + New
          </button>
        </div>
        <div className="divide-y">
          {templates.map(t => (
            <div 
              key={t.id} 
              onClick={() => setSelectedTemplate(t)}
              className={`p-3 cursor-pointer hover:bg-indigo-50 transition-colors ${selectedTemplate?.id === t.id ? 'bg-indigo-100 border-l-4 border-indigo-600' : ''}`}
            >
              <div className="font-medium text-sm text-gray-900">{t.name}</div>
              <div className="text-xs text-gray-500">v{t.version} • {t.trigger.type}</div>
            </div>
          ))}
          {templates.length === 0 && <div className="p-4 text-xs text-gray-400 italic">No templates found.</div>}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedTemplate ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <p className="text-lg">Select a workflow template to view its details</p>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{selectedTemplate.name}</h2>
                <p className="text-sm text-gray-500">ID: {selectedTemplate.id} • Version: {selectedTemplate.version}</p>
              </div>
              <div className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-semibold">
                Trigger: {selectedTemplate.trigger.type}
              </div>
            </div>

            {/* Steps Visualization */}
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <h3 className="text-lg font-semibold mb-4 text-gray-800">Workflow Steps</h3>
              <div className="space-y-4">
                {selectedTemplate.steps.map((step, idx) => (
                  <div key={step.step_id} className="flex gap-4 items-start">
                    <div className="flex flex-col items-center">
                      <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">
                        {idx + 1}
                      </div>
                      {idx < selectedTemplate.steps.length - 1 && (
                        <div className="w-0.5 h-8 bg-gray-200"></div>
                      )}
                    </div>
                    <div className="flex-1 p-3 rounded-lg border bg-gray-50 hover:bg-gray-100 transition-colors">
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-medium text-sm text-gray-900">{step.name}</span>
                        <span className="text-[10px] px-2 py-0.5 bg-gray-200 text-gray-600 rounded uppercase font-bold">
                          {step.category}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 font-mono">
                        Adapter: {step.config?.adapter || 'INTERNAL'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
