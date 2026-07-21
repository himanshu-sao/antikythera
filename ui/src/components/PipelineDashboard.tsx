import React, { useState, useEffect } from 'react';
import { apiUrl } from '../config';
import { Pipeline, Path, PathStep } from '../types/legacy-pipeline';
import { PipelineFlowchart } from './PipelineFlowchart';
import { ExecutionHistory } from './ExecutionHistory';
import { ExecutionAuditLog } from './ExecutionAuditLog';
import toast from 'react-hot-toast';


interface PipelineDashboardProps {
  pipelineId: string;
  onBack: () => void;
}

export function PipelineDashboard({ pipelineId, onBack }: PipelineDashboardProps) {
  const [pipelineData, setPipelineData] = useState<any | null>(null);
  const [runHistory, setRunHistory] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAuditLog, setShowAuditLog] = useState(false);

  useEffect(() => {
    fetchPipeline();
    fetchRunHistory();
  }, [pipelineId]);

  const fetchPipeline = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/pipelines/${pipelineId}`);
      if (!res.ok) throw new Error('Failed to fetch pipeline');
      const data = await res.json();
      setPipelineData(data);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRunHistory = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/pipelines/${pipelineId}/runs?limit=10`);
      if (res.ok) {
        const data = await res.json();
        setRunHistory(data);
      }
    } catch (e) { console.error("Failed to fetch run history", e); }
  };

  if (isLoading) return <div className="p-8 text-center">Loading Pipeline...</div>;
  if (!pipelineData) return <div className="p-8 text-center">Pipeline not found.</div>;

  const { pipeline, paths } = pipelineData;

  return (
    <div className="h-full flex flex-col bg-[#f6f4ef] text-[#231f19]">
      <div className="p-6 border-b bg-white flex justify-between items-center">
        <div>
          <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 mb-2 flex items-center gap-1">
            ← Back to Hub
          </button>
          <h2 className="text-2xl font-bold">{pipeline.name}</h2>
          <p className="text-sm text-[#6f6a63]">{pipeline.description || 'No description provided'}</p>
        </div>
        <div className="flex gap-3">
          <div className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-[10px] font-bold uppercase tracking-tighter">
            Status: {pipeline.status}
          </div>
          <div className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-[10px] font-bold uppercase tracking-tighter">
            Trigger: {pipeline.trigger.type}
          </div>
          <button
            onClick={() => {
              // Navigate to Automation Studio with this pipeline context
              toast.success('Opening WYSIWYG Builder...');
              setTimeout(() => {
                onBack(); // Return to tabs
                // In a full implementation, this would pass the pipeline_id to the Studio
                // and auto-load the paths for editing
              }, 500);
            }}
            className="px-4 py-2 bg-[#0b6b72] text-white rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-[#0a5c62] transition-all flex items-center gap-2 shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            Edit in Builder
          </button>
        </div>
      </div>

      <div className="flex-1 p-8 overflow-y-auto">
        <div className="grid grid-cols-1 gap-8">
          
          <div className="bg-white rounded-2xl border border-[#d8d3ca] shadow-sm overflow-hidden">
            <div className="px-6 py-3 border-b border-[#d8d3ca] bg-gray-50 flex justify-between items-center">
              <span className="text-xs font-bold uppercase text-gray-500">Visual Workflow</span>
            </div>
            <div className="p-6">
               <PipelineFlowchart paths={paths} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <h3 className="text-lg font-bold mb-4">Path Details</h3>
              {paths.map((path: Path, idx: number) => (
                <div key={path.path_id} className="bg-white rounded-2xl border border-[#d8d3ca] shadow-sm overflow-hidden">
                  <div className="px-4 py-2 bg-gray-50 border-b border-[#d8d3ca] flex justify-between items-center">
                    <span className="text-xs font-bold text-gray-600">Path {idx + 1}: {path.name}</span>
                    <span className="text-[10px] font-mono text-gray-400">{path.path_id}</span>
                  </div>
                  <div className="p-4 space-y-3">
                    {path.steps.map((step: PathStep, sIdx: number) => (
                      <div key={step.step_id} className="flex items-center gap-3">
                        <div className="w-6 h-6 rounded-full bg-[#231f19] text-white flex items-center justify-center text-[10px] font-bold">
                          {sIdx + 1}
                        </div>
                        <div className="flex-1 p-2 rounded-lg border border-gray-100 bg-gray-50 text-xs flex justify-between">
                          <span className="font-medium">{step.operator_id}</span>
                          <span className="text-gray-400 font-mono">{step.adapter_id}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            
            <div className="space-y-6">
              <h3 className="text-lg font-bold mb-4">Run History</h3>
              <div className="bg-white rounded-2xl border border-[#d8d3ca] p-6 shadow-sm">
                <div className="space-y-4">
                  {runHistory.length === 0 ? (
                    <div className="text-center py-8 text-gray-400 text-sm">No runs yet</div>
                  ) : (
                    <>
                      {runHistory.slice(0, 5).map((run: any) => (
                        <div key={run.run_id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                          <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${run.status === 'SUCCESS' ? 'bg-green-500' : run.status === 'FAILED' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                            <div>
                              <span className="text-xs text-gray-600 font-mono">{run.run_id}</span>
                              {run.error && <div className="text-xs text-red-500 truncate max-w-[150px]">{run.error}</div>}
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] text-gray-400 font-mono">
                              {run.duration_ms ? `${Math.round(run.duration_ms / 1000)}s` : '...'}
                            </span>
                            <div className="text-[10px] text-gray-300">
                              {new Date(run.started_at).toLocaleTimeString()}
                            </div>
                          </div>
                        </div>
                      ))}
                      {runHistory.length > 5 && (
                        <div className="pt-4 text-center">
                          <button 
                            onClick={() => {
                              setShowAuditLog(true);
                              toast.success('Opening full audit log');
                            }}
                            className="text-xs text-[#0b6b72] font-bold hover:underline"
                          >
                            View Full Audit Log
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
              <div className="bg-white rounded-2xl border border-[#d8d3ca] p-4 shadow-sm">
                <button
                  onClick={async () => {
                    try {
                      const res = await fetch(`${apiUrl}/api/pipelines/${pipelineId}/run`, { method: 'POST' });
                      if (res.ok) {
                        toast.success('Pipeline triggered');
                        fetchRunHistory();
                      } else {
                        toast.error('Failed to trigger pipeline');
                      }
                    } catch (e: any) {
                      toast.error(e.message);
                    }
                  }}
                  className="w-full py-2 bg-[#0b6b72] text-white rounded-lg text-sm font-medium hover:bg-[#0a5c62] transition-all"
                >
                  Run Now
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      {showAuditLog && (
        <ExecutionAuditLog 
          pipelineId={pipelineId} 
          onClose={() => setShowAuditLog(false)} 
        />
      )}
    </div>
  );
}
