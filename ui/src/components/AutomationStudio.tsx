// Automation Studio — turn-based, live-results-led compiler (Phase 4).
//
// Replaces the dead "NL → one PathStep" recorder (dec #3/#25). The human plays
// and selects against live data turn by turn; each reaction materializes a
// StudioNode. The graph is saved as a durable headless template (dec #5) and
// replayed on demand (dec #7/#15).
//
// See docs/plans/mighty-greeting-cookie.md §0 (Twistlock example) and §8 Step 3.
//
// Slice 1 scope: Query → Fan-out → AI-transform → Conditional-action → Save/Run.
// No AuthModal/token-paste (dec #14); no Skill Brainstormer loop (dec #18).

import React, { useState, useEffect } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { TextHighlighter } from './TextHighlighter';
import {
  type StudioGraph,
  type StudioNode,
  type CapabilityTier,
  DEFAULT_CAPABILITY,
} from '../types/studio';
import {
  getIntegrationStatus,
  previewNode,
  saveGraph,
  runGraph,
  type IntegrationStatus,
  type PreviewNodeResult,
} from '../api/studioClient';

// -----------------------------------------------------------------------------
// Constants
// -----------------------------------------------------------------------------

// A studio graph is authored in memory; the backend assigns graph_id on save.
const EMPTY_GRAPH: StudioGraph = {
  graph_id: '',
  name: '',
  description: '',
  version: '1.0.0',
  created_at: '',
  updated_at: '',
  nodes: [],
  edges: [],
  required_capability: DEFAULT_CAPABILITY,
  cron_schedule: undefined,
  cron_enabled: false,
  undefined_queue_cap: 100,
  max_run_logs: 50,
};

// Which turn the author is on. Each turn drafts exactly one StudioNode (except
// collapse/pick, which is a scope narrowing — deferred to a later slice).
type TurnType = 'query' | 'fan_out' | 'ai_transform' | 'conditional_action';

const TURN_LABELS: Record<TurnType, { title: string; hint: string }> = {
  query: { title: '1. Query', hint: 'Fetch live data (list/vector) from an adapter.' },
  fan_out: { title: '2. Fan-out', hint: 'Loop — one branch per item in the query result.' },
  ai_transform: { title: '3. AI-transform', hint: 'Run a Python snippet or saved Skill over each item.' },
  conditional_action: { title: '4. Conditional-action', hint: 'Route/act when a condition matches.' },
};

const TURN_ORDER: TurnType[] = ['query', 'fan_out', 'ai_transform', 'conditional_action'];

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export function AutomationStudio() {
  // ==== Graph under construction (dec #5) ==== //
  const [graph, setGraph] = useState<StudioGraph>(EMPTY_GRAPH);

  // ==== Live sandbox: output_ref -> value (preview-node updates this) ==== //
  const [executionState, setExecutionState] = useState<Record<string, unknown>>({});

  // ==== Turn tracking ==== //
  const [turnIndex, setTurnIndex] = useState<number>(0); // index into TURN_ORDER
  const activeTurn: TurnType = TURN_ORDER[turnIndex] ?? 'query';

  // ==== Per-turn draft + live preview (dec #15 — live-results-led) ==== //
  const [draftNode, setDraftNode] = useState<Partial<StudioNode> | null>(null);
  const [previewResult, setPreviewResult] = useState<PreviewNodeResult | null>(null);

  // ==== Saved graph state ==== //
  const [graphId, setGraphId] = useState<string | null>(null);
  const [graphName, setGraphName] = useState<string>('');
  const [runStatus, setRunStatus] = useState<string | null>(null);

  // ==== UI state ==== //
  const [isLoading, setIsLoading] = useState(false);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);

  // ==== Bootstrap: integration status (dec #14 — status only, no token) ==== //
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await getIntegrationStatus();
        if (!cancelled) setIntegrations(list);
      } catch (e) {
        if (!cancelled) console.error('Failed to load integration status', e);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ...turn forms, accept/save/run, and panel wiring land in later commits.

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-[#f6f4ef] text-[#231f19]">
      {/* Page Header */}
      <div className="p-6 bg-white border-b border-[#d8d3ca]">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">Automation Studio</h1>
            <p className="text-sm text-gray-500">
              Play & select against live data. Your reactions become the workflow.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={graphName}
              onChange={(e) => setGraphName(e.target.value)}
              placeholder="Graph name"
              className="px-3 py-1.5 text-sm border border-[#d8d3ca] rounded focus:outline-none focus:ring-2 focus:ring-[#0b6b72] bg-white"
            />
            <button
              disabled={graph.nodes.length === 0 || isLoading}
              className="px-4 py-1.5 text-sm font-bold bg-[#0b6b72] text-white rounded hover:bg-[#0a5c62] disabled:opacity-50"
            >
              Save
            </button>
            <button
              disabled={!graphId || isLoading}
              className="px-4 py-1.5 text-sm font-bold border border-[#0b6b72] text-[#0b6b72] rounded hover:bg-[#0b6b72] hover:text-white disabled:opacity-50"
            >
              Run
            </button>
          </div>
        </div>
        {integrations.length > 0 && (
          <div className="flex gap-3 mt-3 text-xs flex-wrap">
            {integrations.map((it) => (
              <span
                key={it.name}
                className={`px-2 py-0.5 rounded-full border ${it.connected ? 'border-green-300 text-green-700 bg-green-50' : 'border-gray-300 text-gray-500 bg-gray-50'}`}
              >
                {it.name} {it.connected ? '✅' : '❌'}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Main Content — 3 panes */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Turn Panel */}
        <div className="w-80 flex flex-col bg-[#fcfbf8] border-r border-[#d8d3ca] overflow-y-auto p-6">
          {/* Turn forms land here in Commit 2. */}
          <div className="flex-1 flex items-center justify-center text-center">
            <div>
              <p className="text-sm font-semibold text-gray-700">{TURN_LABELS[activeTurn].title}</p>
              <p className="text-xs text-gray-500 mt-1">{TURN_LABELS[activeTurn].hint}</p>
              <p className="text-[10px] text-gray-400 mt-6 italic">Turn forms arrive in the next commit.</p>
            </div>
          </div>
        </div>

        {/* Center: Live Sandbox */}
        <div className="flex-1 p-8 overflow-y-auto bg-[#f6f4ef]">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-base font-semibold">Live Sandbox</h3>
            {previewResult && (
              <div className={`flex items-center text-xs ${previewResult.status === 'success' ? 'text-green-600' : 'text-amber-600'}`}>
                <span className={`w-2 h-2 rounded-full mr-1 ${previewResult.status === 'success' ? 'bg-green-600' : 'bg-amber-600'}`} />
                {previewResult.status}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-6">
            {/* Cards: live preview of the current turn */}
            <div className="bg-white rounded-2xl shadow-sm border border-[#d8d3ca] overflow-hidden">
              <div className="px-6 py-3 border-b border-[#d8d3ca] bg-gray-50">
                <span className="text-xs font-bold uppercase text-gray-500">Live Preview</span>
              </div>
              <div className="p-6">
                {previewResult ? (
                  <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(previewResult.result, null, 2)}
                  </pre>
                ) : (
                  <p className="py-12 text-center text-xs text-gray-400 italic">
                    Draft a turn and preview-execute it to see live data here.
                  </p>
                )}
              </div>
            </div>

            {/* Active Variables: accumulated executionState */}
            <div className="bg-white rounded-2xl shadow-sm border border-[#d8d3ca] overflow-hidden">
              <div className="px-6 py-3 border-b border-[#d8d3ca] bg-gray-50 flex justify-between items-center">
                <span className="text-xs font-bold uppercase text-gray-500">Active Variables</span>
                <span className="text-[10px] text-gray-400">{Object.keys(executionState).length} refs</span>
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
                    {Object.entries(executionState).map(([key, val]) => (
                      <tr key={key} className="border-b border-gray-50 group">
                        <td className="py-3 font-mono text-xs text-[#0b6b72] font-bold align-top w-1/3">{key}</td>
                        <td className="py-3 text-xs text-gray-600 max-w-md">
                          {typeof val === 'object' ? (
                            <TextHighlighter text={JSON.stringify(val, null, 2)} onExtract={() => {}} />
                          ) : (
                            <TextHighlighter text={String(val)} onExtract={() => {}} />
                          )}
                        </td>
                      </tr>
                    ))}
                    {Object.keys(executionState).length === 0 && (
                      <tr>
                        <td colSpan={2} className="py-12 text-center text-xs text-gray-400 italic">
                          Execute a turn to see data appearing here.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Graph Outline */}
        <div className="w-72 border-l border-[#d8d3ca] bg-[#fcfbf8] p-6 overflow-y-auto">
          <h4 className="text-xs font-bold uppercase text-gray-400 mb-3">Graph Outline</h4>
          <div className="space-y-2">
            {graph.nodes.length === 0 && <p className="text-[10px] italic text-gray-400">No nodes yet.</p>}
            {graph.nodes.map((node, idx) => (
              <div key={node.node_id} className="flex items-center gap-2 text-[11px] bg-white p-2 rounded border border-gray-200">
                <span className="font-bold text-gray-400">{idx + 1}.</span>
                <span className="font-medium text-gray-700">{node.name}</span>
                <span className="ml-auto text-[9px] text-[#0b6b72] font-mono">{node.archetype}</span>
              </div>
            ))}
          </div>

          {runStatus && (
            <div className="mt-6 pt-4 border-t border-[#d8d3ca]">
              <h4 className="text-xs font-bold uppercase text-gray-400 mb-2">Last Run</h4>
              <p className="text-[11px] text-gray-600">{runStatus}</p>
            </div>
          )}
        </div>
      </div>

      <Toaster />
    </div>
  );
}
