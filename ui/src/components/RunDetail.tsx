import React, { useState, useEffect } from 'react';
import { apiUrl } from '../config';

interface TimelineEvent {
  timestamp: string;
  event_type: string;
  details: any;
  actor: string;
}

interface RunDetailData {
  run: {
    id: string;
    status: string;
    started_at: string;
    current_step_id: string;
  };
  template: {
    name: string;
    version: string;
  };
  timeline: TimelineEvent[];
  bindings: any[];
}

export default function RunDetail({ runId, onClose }: { runId: string, onClose: () => void }) {
  const [data, setData] = useState<RunDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetails = async () => {
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
    fetchDetails();
  }, [runId]);

  if (loading) return <div className="p-6 text-center text-gray-500">Loading run execution...</div>;
  if (!data) return <div className="p-6 text-center text-red-500">Run not found.</div>;

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{data.run.id}</h2>
          <p className="text-sm text-gray-500">Template: {data.template.name} (v{data.template.version})</p>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-bold ${
          data.run.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 
          data.run.status === 'FAILED' ? 'bg-red-100 text-red-700' : 
          data.run.status === 'BLOCKED' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'
        }`}>
          {data.run.status}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pr-2">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Execution Timeline</h3>
        <div className="space-y-4 relative before:absolute before:left-4 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
          {data.timeline.map((event, idx) => (
            <div key={idx} className="relative pl-10 pb-4">
              <div className={`absolute left-2 top-1 w-4 h-4 rounded-full border-2 bg-white z-10 ${
                event.event_type === 'ERROR' ? 'border-red-500 text-red-500' : 'border-indigo-500'
              }`} />
              <div className="bg-white p-3 rounded-lg border shadow-sm">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs font-bold text-gray-900">{event.event_type}</span>
                  <span className="text-[10px] text-gray-400">{new Date(event.timestamp).toLocaleTimeString()}</span>
                </div>
                <div className="text-xs text-gray-600">
                  {JSON.stringify(event.details)}
                </div>
                <div className="text-[10px] text-gray-400 mt-1 italic">Actor: {event.actor}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 pt-4 border-t">
        <button onClick={onClose} className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-sm font-medium transition-colors">
          Close Details
        </button>
      </div>
    </div>
  );
}
