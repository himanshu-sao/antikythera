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

import React, { useState, useEffect, useMemo } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { TextHighlighter } from './TextHighlighter';
import {
  type StudioGraph,
  type StudioNode,
  type QueryNode,
  type FanOutNode,
  type GraphEdge,
  type CapabilityTier,
  NodeArchetype,
  StudioNodeSchema,
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

// Adapter list/vector actions offered by the Query form (dec #28). Keyed by
// adapter name (the `name` returned by getIntegrationStatus()). A Query must
// select an action that returns a vector — fetch_resource returns one, never a list.
type ActionSpec = { action: string; label: string; params: string[] };
const ADAPTER_ACTIONS: Record<string, ActionSpec[]> = {
  jira: [
    { action: 'list_tickets', label: 'list_tickets(jql, max_results)', params: ['jql', 'max_results'] },
    { action: 'list_projects', label: 'list_projects()', params: [] },
  ],
  github: [
    { action: 'list_repos', label: 'list_repos(org, type, per_page)', params: ['org', 'type', 'per_page'] },
    { action: 'list_pull_requests', label: 'list_pull_requests(owner, repo, state, per_page)', params: ['owner', 'repo', 'state', 'per_page'] },
  ],
  internal: [
    { action: 'list_items', label: 'list_items(stage)', params: ['stage'] },
  ],
};

// Map a connected-integration name to an adapter catalog key. Integration
// names are free-form; this is a forgiving matcher over the recognized prefixes.
const adapterKeyFor = (name: string): string => {
  const lower = name.toLowerCase();
  if (lower.includes('jira')) return 'jira';
  if (lower.includes('github')) return 'github';
  if (lower.includes('internal')) return 'internal';
  return '';
};

// Build a fresh node_id. Deterministic + monotonic so commits are stable in
// the graph outline (no Math.random — keeps snapshots/test output reproducible).
const nextNodeId = (archetype: string, count: number): string =>
  `${archetype}_${String(count).padStart(2, '0')}`;

// -----------------------------------------------------------------------------
// Per-turn draft state (kept separate from the committed graph)
// -----------------------------------------------------------------------------

interface QueryDraft {
  adapter: string;
  action: string;
  params: Record<string, string>;
  output_ref: string;
  name: string;
}

interface FanOutDraft {
  source: string;
  iterator_var: string;
  name: string;
}

type Draft = QueryDraft | FanOutDraft | null;

// Empty draft for each turn, so switching turns clears the form.
const emptyDraftFor = (turn: TurnType): Draft => {
  if (turn === 'query') return { adapter: '', action: '', params: {}, output_ref: '', name: '' };
  if (turn === 'fan_out') return { source: '', iterator_var: 'item', name: '' };
  return null;
};

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
  const [draft, setDraft] = useState<Draft>(emptyDraftFor('query'));
  const [previewResult, setPreviewResult] = useState<PreviewNodeResult | null>(null);
  const [previewing, setPreviewing] = useState(false);

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

  // ------------------------------------------------------------------
  // Draft → StudioNode builder for the active turn (Turns 1–2 only in T2a).
  // ------------------------------------------------------------------
  const buildDraftNode = (d: Draft): StudioNode | null => {
    const count = graph.nodes.length;
    if (activeTurn === 'query' && d && 'adapter' in d) {
      const q: QueryDraft = d;
      if (!q.adapter || !q.action || !q.output_ref) return null;
      return {
        node_id: nextNodeId('query', count),
        archetype: NodeArchetype.QUERY,
        name: q.name || `Query ${q.adapter}.${q.action}`,
        adapter: q.adapter,
        action: q.action,
        params: Object.fromEntries(
          Object.entries(q.params).filter(([, v]) => v !== '' && v !== undefined),
        ),
        output_ref: q.output_ref,
      } as QueryNode;
    }
    if (activeTurn === 'fan_out' && d && 'iterator_var' in d) {
      const f: FanOutDraft = d;
      if (!f.source || !f.iterator_var) return null;
      return {
        node_id: nextNodeId('fan_out', count),
        archetype: NodeArchetype.FAN_OUT,
        name: f.name || `Fan-out over ${f.source}`,
        loop_over: { source: f.source, iterator_var: f.iterator_var },
      } as FanOutNode;
    }
    return null;
  };

  // ------------------------------------------------------------------
  // Preview: execute the draft node against execution_state (dec #15).
  // Sets the live result + merges updated_state into executionState.
  // ------------------------------------------------------------------
  const handlePreview = async () => {
    const d: Draft = (activeTurn === 'query' || activeTurn === 'fan_out') ? draft : null;
    const node = buildDraftNode(d);
    if (!node) {
      toast.error('Fill in the required fields before previewing.');
      return;
    }
    setPreviewing(true);
    try {
      const res = await previewNode({ node, execution_state: executionState });
      setPreviewResult(res);
      if (res.updated_state) {
        setExecutionState((prev) => ({ ...prev, ...res.updated_state }));
      }
      if (res.status === 'failed' || res.status === 'undefined') {
        toast.error(res.error || `Preview returned status "${res.status}".`);
      } else if (res.status === 'success') {
        toast.success('Preview succeeded.');
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Preview failed: ${msg}`);
    } finally {
      setPreviewing(false);
    }
  };

  // ------------------------------------------------------------------
  // Commit: zod-validate the draft node, append it + an edge to the graph,
  // then advance to the next turn. Save/Run stay inert until T2b.
  // ------------------------------------------------------------------
  const handleCommit = () => {
    const d: Draft = (activeTurn === 'query' || activeTurn === 'fan_out') ? draft : null;
    const node = buildDraftNode(d);
    if (!node) {
      toast.error('Nothing to commit — fill in the form first.');
      return;
    }
    const parsed = StudioNodeSchema.safeParse(node);
    if (!parsed.success) {
      toast.error(`Invalid node: ${parsed.error.issues.map((i) => i.path.join('.') + ' ' + i.message).join('; ')}`);
      return;
    }
    const committed = parsed.data as StudioNode;
    const edge: GraphEdge | null = (() => {
      const last = graph.nodes[graph.nodes.length - 1];
      if (!last) return null;
      const source_handle = last.archetype === NodeArchetype.FAN_OUT ? 'loop' : undefined;
      return {
        edge_id: `e_${last.node_id}_${committed.node_id}`,
        source: last.node_id,
        target: committed.node_id,
        source_handle,
      };
    })();

    setGraph((g) => ({
      ...g,
      nodes: [...g.nodes, committed],
      edges: edge ? [...g.edges, edge] : g.edges,
    }));
    if (previewResult?.updated_state) {
      setExecutionState((prev) => ({ ...prev, ...previewResult.updated_state }));
    }
    setPreviewResult(null);

    const nextIdx = Math.min(turnIndex + 1, TURN_ORDER.length - 1);
    setTurnIndex(nextIdx);
    setDraft(emptyDraftFor(TURN_ORDER[nextIdx]));
    toast.success(`Committed ${committed.archetype} node.`);
  };

  // ------------------------------------------------------------------
  // Save / Run — land in T2b. Kept inert placeholders here (dec #25 scope):
  // clicking surfaces a "not yet wired" toast so the buttons aren't dead,
  // but we do NOT persist or execute until the T2b terminal turn exists.
  // The imports are referenced so the client surface stays compile-clean.
  // ------------------------------------------------------------------
  const handleSave = () => {
    void saveGraph;  // T2b
    toast('Save lands in T2b.', { icon: '🚧' });
  };

  const handleRun = () => {
    void runGraph;  // T2b
    if (!graphId) return;
    toast('Run lands in T2b.', { icon: '🚧' });
  };

  // Connected integrations offered by the Query form's adapter select.
  const adapterOptions = useMemo(
    () => integrations.filter((i) => i.connected && adapterKeyFor(i.name)),
    [integrations],
  );

  // Existing output_refs the Fan-out form can loop over.
  const sourceOptions = useMemo(
    () => Object.keys(executionState),
    [executionState],
  );


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
              onClick={handleSave}
              disabled={graph.nodes.length === 0 || isLoading}
              className="px-4 py-1.5 text-sm font-bold bg-[#0b6b72] text-white rounded hover:bg-[#0a5c62] disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={handleRun}
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
          <div className="mb-4">
            <p className="text-sm font-semibold text-gray-700">{TURN_LABELS[activeTurn].title}</p>
            <p className="text-xs text-gray-500 mt-1">{TURN_LABELS[activeTurn].hint}</p>
          </div>

          {/* ---- Turn 1: Query ---- */}
          {activeTurn === 'query' && draft && 'adapter' in draft && (() => {
            const q = draft as QueryDraft;
            const akey = q.adapter ? adapterKeyFor(q.adapter) : '';
            const actions = akey ? (ADAPTER_ACTIONS[akey] ?? []) : [];
            const chosen = actions.find((a) => a.action === q.action) ?? null;
            const setQ = (patch: Partial<QueryDraft>) =>
              setDraft({ ...(draft as QueryDraft), ...patch } as QueryDraft);
            return (
              <div className="flex-1 space-y-4">
                <label className="block">
                  <span className="text-[10px] font-bold uppercase text-gray-400">Adapter</span>
                  <select
                    aria-label="Adapter"
                    value={q.adapter}
                    onChange={(e) => {
                      const name = e.target.value;
                      const key = adapterKeyFor(name);
                      const firstAction = key ? (ADAPTER_ACTIONS[key]?.[0]?.action ?? '') : '';
                      setQ({ adapter: name, action: firstAction, params: {} });
                    }}
                    className="mt-1 w-full px-2 py-1.5 text-sm border border-[#d8d3ca] rounded bg-white"
                  >
                    <option value="">Select adapter…</option>
                    {adapterOptions.map((it) => (
                      <option key={it.name} value={it.name}>{it.name}</option>
                    ))}
                  </select>
                  {adapterOptions.length === 0 && (
                    <span className="text-[10px] text-amber-600">No connected adapters loaded.</span>
                  )}
                </label>

                <label className="block">
                  <span className="text-[10px] font-bold uppercase text-gray-400">Action (list/vector)</span>
                  <select
                    aria-label="Action"
                    value={q.action}
                    onChange={(e) => setQ({ action: e.target.value, params: {} })}
                    disabled={!akey}
                    className="mt-1 w-full px-2 py-1.5 text-sm border border-[#d8d3ca] rounded bg-white disabled:opacity-50"
                  >
                    <option value="">{akey ? 'Select action…' : 'Pick an adapter first'}</option>
                    {actions.map((a) => (
                      <option key={a.action} value={a.action}>{a.label}</option>
                    ))}
                  </select>
                </label>

                {chosen && chosen.params.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-[10px] font-bold uppercase text-gray-400">Params</span>
                    {chosen.params.map((p) => (
                      <label key={p} className="block">
                        <span className="text-[11px] font-mono text-gray-500">{p}</span>
                        <input
                          aria-label={`param ${p}`}
                          value={q.params[p] ?? ''}
                          onChange={(e) => setQ({ params: { ...q.params, [p]: e.target.value } })}
                          className="mt-0.5 w-full px-2 py-1 text-xs font-mono border border-[#d8d3ca] rounded bg-white"
                        />
                      </label>
                    ))}
                  </div>
                )}

                <label className="block">
                  <span className="text-[10px] font-bold uppercase text-gray-400">output_ref</span>
                  <input
                    aria-label="output_ref"
                    value={q.output_ref}
                    onChange={(e) => setQ({ output_ref: e.target.value })}
                    placeholder="jira_tickets"
                    className="mt-1 w-full px-2 py-1.5 text-xs font-mono border border-[#d8d3ca] rounded bg-white"
                  />
                </label>
              </div>
            );
          })()}

          {/* ---- Turn 2: Fan-out ---- */}
          {activeTurn === 'fan_out' && draft && 'iterator_var' in draft && (() => {
            const f = draft as FanOutDraft;
            const setF = (patch: Partial<FanOutDraft>) =>
              setDraft({ ...(draft as FanOutDraft), ...patch } as FanOutDraft);
            return (
              <div className="flex-1 space-y-4">
                <label className="block">
                  <span className="text-[10px] font-bold uppercase text-gray-400">Source (existing output_ref)</span>
                  <select
                    aria-label="Source"
                    value={f.source}
                    onChange={(e) => setF({ source: e.target.value })}
                    className="mt-1 w-full px-2 py-1.5 text-sm font-mono border border-[#d8d3ca] rounded bg-white"
                  >
                    <option value="">Select source…</option>
                    {sourceOptions.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  {sourceOptions.length === 0 && (
                    <span className="text-[10px] text-amber-600">Query a node first to populate outputs.</span>
                  )}
                </label>

                <label className="block">
                  <span className="text-[10px] font-bold uppercase text-gray-400">iterator_var</span>
                  <input
                    aria-label="iterator_var"
                    value={f.iterator_var}
                    onChange={(e) => setF({ iterator_var: e.target.value })}
                    placeholder="ticket"
                    className="mt-1 w-full px-2 py-1.5 text-xs font-mono border border-[#d8d3ca] rounded bg-white"
                  />
                </label>
              </div>
            );
          })()}

          {/* Turns 3–4 are T2b — surface the label but no form yet. */}
          {(activeTurn === 'ai_transform' || activeTurn === 'conditional_action') && (
            <div className="flex-1 flex items-center justify-center text-center">
              <p className="text-[11px] text-gray-400 italic">
                This turn's form lands in T2b.
              </p>
            </div>
          )}

          {/* Preview / Commit */}
          <div className="pt-4 mt-4 border-t border-[#d8d3ca] space-y-2">
            <button
              onClick={handlePreview}
              disabled={previewing}
              className="w-full px-3 py-2 text-sm font-bold border border-[#0b6b72] text-[#0b6b72] rounded hover:bg-[#0b6b72] hover:text-white disabled:opacity-50"
            >
              {previewing ? 'Previewing…' : 'Preview'}
            </button>
            <button
              onClick={handleCommit}
              className="w-full px-3 py-2 text-sm font-bold bg-[#0b6b72] text-white rounded hover:bg-[#0a5c62]"
            >
              Commit turn
            </button>
            <p className="text-[10px] text-gray-400 italic">
              Commit advances to the next turn and writes the node into the graph.
            </p>
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
              <div className="px-6 py-3 border-b border-[#d8d3ca] bg-gray-50 flex justify-between items-center">
                <span className="text-xs font-bold uppercase text-gray-500">Live Preview</span>
                {previewResult && Array.isArray(previewResult.result) && (
                  <span className="text-[10px] text-gray-400">
                    {previewResult.result.length} item{previewResult.result.length === 1 ? '' : 's'}
                  </span>
                )}
              </div>
              <div className="p-6">
                {previewResult ? (
                  Array.isArray(previewResult.result) ? (
                    <div className="grid grid-cols-2 gap-3">
                      {previewResult.result.map((item, idx) => (
                        <div
                          key={idx}
                          className="border border-[#e2ddd2] rounded-lg p-3 bg-[#fcfbf8] hover:border-[#0b6b72] cursor-pointer"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] font-bold uppercase text-gray-400">#{idx + 1}</span>
                          </div>
                          <pre className="text-[11px] font-mono text-gray-700 whitespace-pre-wrap break-words overflow-hidden max-h-40">
                            {typeof item === 'object' && item !== null
                              ? JSON.stringify(item, null, 2)
                              : String(item)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap overflow-x-auto">
                      {JSON.stringify(previewResult.result, null, 2)}
                    </pre>
                  )
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
