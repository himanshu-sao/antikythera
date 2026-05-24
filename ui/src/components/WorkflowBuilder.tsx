import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';

interface Step {
  id: number;
  type: 'action' | 'decision' | 'approval';
  adapter: string;
  action: string;
  config: any;
  board_stage: string;
}

interface Template {
  name: string;
  description: string;
  trigger: {
    type: string;
    provider: string;
    config: any;
  };
  steps: Step[];
}

export function WorkflowBuilder() {
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [template, setTemplate] = useState<Template | null>(null);

  const generateFromAI = async () => {
    if (prompt.length < 10) {
      toast.error("Please provide a more detailed description");
      return;
    }
    setIsGenerating(true);
    try {
      const res = await fetch(`${apiUrl}/api/builder/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) throw new Error('AI Generation failed');
      const data = await res.json();
      setTemplate(data);
      toast.success("Template generated successfully!");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const saveTemplate = async () => {
    if (!template) return;
    try {
      const res = await fetch(`${apiUrl}/api/workflows/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(template),
      });
      if (!res.ok) throw new Error('Failed to save template');
      toast.success("Template saved to library!");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold text-[#231f19] mb-2">Workflow Architect</h1>
        <p className="text-[#6f6a63]">Describe your automation in plain English, and let AI build the blueprint.</p>
      </div>

      <div className="bg-white border border-[#d8d3ca] rounded-2xl p-6 shadow-sm mb-10">
        <div className="flex gap-3">
          <input 
            type="text" 
            className="flex-1 p-3 border rounded-xl text-lg focus:ring-2 focus:ring-[#0b6b72] outline-none transition-all"
            placeholder="e.g. I want a workflow that watches GitHub PR merges and triggers a dev build..."
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />
          <button 
            onClick={generateFromAI}
            disabled={isGenerating}
            className="px-6 py-3 bg-[#0b6b72] text-white rounded-xl font-bold hover:bg-[#0a5c62] transition-all disabled:opacity-50"
          >
            {isGenerating ? 'Architecting...' : 'Generate Blueprint'}
          </button>
        </div>
      </div>

      {template && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-white border border-[#d8d3ca] rounded-2xl p-6 shadow-sm">
              <h3 className="font-bold text-lg mb-4 text-[#231f19]">Blueprint Details</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Template Name</label>
                  <input 
                    className="w-full p-2 border rounded-lg" 
                    value={template.name} 
                    onChange={e => setTemplate({...template, name: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Description</label>
                  <textarea 
                    className="w-full p-2 border rounded-lg h-24" 
                    value={template.description} 
                    onChange={e => setTemplate({...template, description: e.target.value})}
                  />
                </div>
                <div className="pt-4">
                  <button 
                    onClick={saveTemplate}
                    className="w-full py-3 bg-[#231f19] text-white rounded-xl font-bold hover:bg-black transition-all"
                  >
                    Save to Library
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="bg-white border border-[#d8d3ca] rounded-2xl p-6 shadow-sm">
              <h3 className="font-bold text-lg mb-6 text-[#231f19]">Execution Path</h3>
              <div className="space-y-4">
                <div className="flex items-center gap-4 p-4 bg-[#fbfaf7] border border-[#d8d3ca] rounded-xl">
                  <div className="w-10 h-10 rounded-full bg-[#231f19] text-white flex items-center justify-center font-bold">T</div>
                  <div className="flex-1">
                    <div className="font-bold text-sm">Trigger: {template.trigger.provider}</div>
                    <div className="text-xs text-gray-500">{template.trigger.type} - {JSON.stringify(template.trigger.config)}</div>
                  </div>
                </div>
                
                {template.steps.map((step, idx) => (
                  <React.Fragment key={step.id}>
                    <div className="flex justify-center py-1">
                      <div className="w-0.5 h-4 bg-[#d8d3ca] dashed"></div>
                    </div>
                    <div className="flex items-center gap-4 p-4 bg-white border border-[#d8d3ca] rounded-xl hover:border-[#0b6b72] transition-all group">
                      <div className="w-10 h-10 rounded-full bg-white border-2 border-[#231f19] text-[#231f19] flex items-center justify-center font-bold">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <div className="font-bold text-sm">{step.action}</div>
                          <span className="text-[10px] px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full font-bold uppercase tracking-tighter">
                            {step.type}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500">Adapter: {step.adapter} | Stage: {step.board_stage}</div>
                      </div>
                      <button className="p-2 text-gray-300 hover:text-[#0b6b72] opacity-0 group-hover:opacity-100 transition-all">
                        ⚙️
                      </button>
                    </div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
