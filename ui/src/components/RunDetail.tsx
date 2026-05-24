import React, { useState, useEffect } from 'react';
import { apiUrl } from '../config';

interface TimelineEvent {
  timestamp: string;
  event_type: string;
  details: any;
  actor: string;
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

interface Template {
  id: string;
  name: string;
  version: string;
  trigger: { type: string };
  steps: any[];
}

interface RunDetailData {
  run: WorkflowRun;
  template: Template;
  timeline: TimelineEvent[];
  bindings: any[];
}

export default function RunDetail({ runId, onClose }: { runId: string, onClose: () => void }) {
  const [data, setData] = useState<RunDetailData | null>(null);
  const [isLoading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRun = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/workflows/runs/${runId}`);
        if (!res.ok) throw new Error('Failed to fetch run details');
        setData(await res.json());
      } catch (e: any) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchRun();
  }, [runId]);

  if (isLoading) return <div className="p-4 text-center text-gray-500">Loading run details...</div>;
  if (!data) return <div className="p-4 text-center text-red-500">Run not found.</div>;

  const statusColors: Record<string, string> = {
    COMPLETED: 'bg-[#dbead8] text-[#2f6b2a]',
    FAILED: 'bg-red-100 text-red-800',
    WAITING: 'bg-[#f8ead8] text-[#a45a12]',
    NEEDS_APPROVAL: 'bg-[#f8ead8] text-[#a45a12]',
    BLOCKED: 'bg-red-100 text-red-800',
    ACTIVE: 'bg-blue-100 text-blue-800',
  };

  return (
    <div className="flex flex-col h-full w-full bg-[#fcfbf8] text-[#231f19]">
      <div className="flex justify-between items-center p-4 border-b border-[#d8d3ca] bg-[#f1eee8]">
        <div>
          <h2 className="text-xl font-bold">{data.template.name}</h2>
          <p className="text-xs text-[#6f6a63]">Run ID: {data.run.id} • v{data.template.version}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${statusColors[data.run.status] || 'bg-gray-100 text-gray-600'}`}>
            {data.run.status}
          </span>
          <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded-full transition-colors">✕</button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Run Metadata */}
          <div className="space-y-4">
            <div className="bg-white p-4 rounded-xl border border-[#d8d3ca] shadow-sm">
              <h3 className="text-sm font-bold text-[#6f6a63] uppercase mb-3">Execution Details</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-xs text-gray-400">Started At</div>
                  <div className="font-medium">{new Date(data.run.started_at).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">Current Step</div>
                  <div className="font-medium">{data.run.current_step_id}</div>
                </div>
              </div>
            </div>
            <div className="bg-white p-4 rounded-xl border border-[#d8d3ca] shadow-sm">
              <h3 className="text-sm font-bold text-[#6f6a63] uppercase mb-3">Bound Items</h3>
              <div className="flex flex-wrap gap-2">
                {data.bindings.map(b => (
                  <span key={b.item_id} className="px-2 py-1 bg-[#ebe7df] text-[#6f6a63] rounded text-xs font-mono border border-[#d8d3ca]">
                    {b.item_id}
                  </span>
                ))}
                {data.bindings.length === 0 && <div className="text-xs italic text-gray-400">No bound items found.</div>}
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-[#6f6a63] uppercase">Execution Timeline</h3>
            <div className="relative pl-6 space-y-6 border-l-2 border-dashed border-[#d8d3ca]">
              {data.timeline.map((event, idx) => (
                <div key={idx} className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-[#231f19] border-2 border-white shadow-sm"></div>
                  <div className="bg-white p-3 rounded-lg border border-[#d8d3ca] shadow-sm hover:border-[#0b6b72] transition-colors">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-bold text-[#0b6b72] uppercase">{event.event_type}</span>
                      <span className="text-[10px] text-gray-400">{new Date(event.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-sm text-[#231f19]">{event.details}</div>
                    <div className="text-[10px] text-gray-400 mt-1 italic">Actor: {event.actor}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}