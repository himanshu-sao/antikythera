import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';

// Mirrors the Template/Step shape used by WorkflowBuilder.tsx and produced by
// POST /api/builder/generate. Kept local so this panel stays self-contained;
// if a third consumer appears, lift these into types.ts.
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

const MIN_PROMPT_LENGTH = 10; // matches backend GenerationRequest.prompt min_length=10

export function BlueprintArchitect() {
  const [prompt, setPrompt] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [template, setTemplate] = useState<Template | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [validation, setValidation] = useState<{ status: string; message: string } | null>(null);

  const generate = async () => {
    if (prompt.trim().length < MIN_PROMPT_LENGTH) {
      toast.error('Please describe the workflow in at least 10 characters');
      return;
    }
    setIsGenerating(true);
    setValidation(null);
    try {
      const res = await fetch(`${apiUrl}/api/builder/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, template_name: templateName || undefined }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || 'AI generation failed');
      }
      const data: Template = await res.json();
      setTemplate(data);
      toast.success('Blueprint generated');
    } catch (e: any) {
      toast.error(e.message || 'AI generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  const validate = async () => {
    if (!template) return;
    setIsValidating(true);
    try {
      const res = await fetch(`${apiUrl}/api/builder/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_data: template }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setValidation({ status: 'valid', message: data.message || 'Template structure is correct' });
      } else {
        setValidation({ status: 'invalid', message: data.detail || 'Validation failed' });
      }
    } catch (e: any) {
      setValidation({ status: 'invalid', message: e.message || 'Validation request failed' });
    } finally {
      setIsValidating(false);
    }
  };

  // Adapters that can execute arbitrary commands / shell — block these from
  // being silently persisted via an AI-generated template. The execution
  // engine's registry has INTERNAL, GITHUB, JIRA, BOB_SHELL; the builder
  // uses lowercase tokens (shell, ai, internal, github, jira, bob_shell).
  // 'shell' is not in the engine registry (would error at run time), but we
  // still block it here. 'bob_shell' IS in the registry and runs commands.
  const EXECUTION_CAPABLE_ADAPTERS = new Set(['shell', 'bob_shell']);

  // Derive a stable template_id from the name (POST /api/workflows/templates
  // requires one). Falls back to a slug when the name is empty.
  const save = async () => {
    if (!template) return;

    // Client gate: reject templates that contain execution-capable adapters.
    // The backend /api/workflows/templates currently has no adapter allowlist;
    // this defends the Save sink regardless.
    const dangerousSteps = template.steps.filter(step =>
      EXECUTION_CAPABLE_ADAPTERS.has(step.adapter?.toLowerCase())
    );
    if (dangerousSteps.length > 0) {
      toast.error(
        `Template contains execution-capable adapter(s): ${dangerousSteps.map(s => s.adapter).join(', ')}. ` +
        `Remove or change these steps before saving.`
      );
      return;
    }

    setIsSaving(true);
    try {
      const templateId =
        template.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') ||
        'blueprint';
      const res = await fetch(`${apiUrl}/api/workflows/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: templateId, ...template }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || 'Failed to save template');
      }
      toast.success('Template saved to library');
    } catch (e: any) {
      toast.error(e.message || 'Failed to save template');
    } finally {
      setIsSaving(false);
    }
  };

  const canGenerate = prompt.trim().length >= MIN_PROMPT_LENGTH && !isGenerating;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold text-[#231f19] mb-2">Blueprint Architect</h1>
        <p className="text-[#6f6a63]">
          Describe an automation in plain English, generate a workflow template, validate it, and save it to the library.
        </p>
      </div>

      <div className="bg-white border border-[#d8d3ca] rounded-2xl p-6 shadow-sm mb-10">
        <textarea
          className="w-full p-3 border rounded-xl text-lg focus:ring-2 focus:ring-[#0b6b72] outline-none transition-all mb-3"
          placeholder="e.g. Create a GitHub PR release workflow that runs build and tests on merge"
          rows={3}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          aria-label="Workflow description"
        />
        <div className="flex gap-3">
          <input
            type="text"
            className="flex-1 p-3 border rounded-xl text-sm focus:ring-2 focus:ring-[#0b6b72] outline-none transition-all"
            placeholder="Template name (optional)"
            value={templateName}
            onChange={e => setTemplateName(e.target.value)}
            aria-label="Template name"
          />
          <button
            onClick={generate}
            disabled={!canGenerate}
            className="px-6 py-3 bg-[#0b6b72] text-white rounded-xl font-bold hover:bg-[#0a5c62] transition-all disabled:opacity-50"
          >
            {isGenerating ? 'Generating...' : 'Generate Blueprint'}
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
                    onChange={e => setTemplate({ ...template, name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Description</label>
                  <textarea
                    className="w-full p-2 border rounded-lg h-24"
                    value={template.description}
                    onChange={e => setTemplate({ ...template, description: e.target.value })}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={validate}
                    disabled={isValidating}
                    className="flex-1 py-3 bg-[#0b6b72] text-white rounded-xl font-bold hover:bg-[#0a5c62] transition-all disabled:opacity-50"
                  >
                    {isValidating ? 'Validating...' : 'Validate'}
                  </button>
                  <button
                    onClick={save}
                    disabled={isSaving}
                    className="flex-1 py-3 bg-[#231f19] text-white rounded-xl font-bold hover:bg-black transition-all disabled:opacity-50"
                  >
                    {isSaving ? 'Saving...' : 'Save to Library'}
                  </button>
                </div>
                {validation && (
                  <div
                    className={`p-3 rounded-lg text-sm font-medium ${
                      validation.status === 'valid' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
                    }`}
                    role="status"
                  >
                    {validation.message}
                  </div>
                )}
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
                      <div className="w-0.5 h-4 bg-[#d8d3ca] dashed" />
                    </div>
                    <div className="flex items-center gap-4 p-4 bg-white border border-[#d8d3ca] rounded-xl">
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

export default BlueprintArchitect;
