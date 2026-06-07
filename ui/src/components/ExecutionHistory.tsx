import React, { useState, useEffect } from 'react';
import { apiUrl } from '../config';
import toast from 'react-hot-toast';

interface ExecutionLog {
  run_id?: string;
  pipeline_id?: string;
  step_id: string;
  parent_run_id?: string;
  started_at: string;
  ended_at?: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped';
  execution_reason?: string;
  extracted_fields: Record<string, any>;
  result_data?: Record<string, any>;
  error_detail?: string;
  duration_ms?: number;
}

interface PipelineRun {
  run_id: string;
  pipeline_id: string;
  started_at: string;
  ended_at?: string;
  status: string;
  error?: string;
  duration_ms?: number;
  logs: ExecutionLog[];
}

interface ExecutionHistoryProps {
  pipelineId: string;
  pipelineName: string;
}

export function ExecutionHistory({ pipelineId, pipelineName }: ExecutionHistoryProps) {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [expandedChildId, setExpandedChildId] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns();
  }, [pipelineId]);

  const fetchRuns = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/pipelines/${pipelineId}/runs?limit=10`);
      if (!res.ok) throw new Error('Failed to fetch run history');
      const data = await res.json();
      setRuns(data);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerRun = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/pipelines/${pipelineId}/run`, { method: 'POST' });
      if (res.ok) {
        toast.success('Pipeline triggered');
        setTimeout(fetchRuns, 1000);
      } else {
        toast.error('Failed to trigger pipeline');
      }
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      success: 'bg-green-100 text-green-700 border-green-200',
      failed: 'bg-red-100 text-red-700 border-red-200',
      running: 'bg-blue-100 text-blue-700 border-blue-200',
      skipped: 'bg-gray-100 text-gray-600 border-gray-200',
      pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${colors[status] || 'bg-gray-100 text-gray-600 border-gray-200'}`}>
        {status.replace(/_/g, ' ')}
      </span>
    );
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
  };

  const formatTime = (iso?: string) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
  };

  // Group logs by parent_run_id to show child executions
  const groupLogsByParent = (logs: ExecutionLog[]) => {
    const grouped: Record<string, ExecutionLog[]> = {};
    logs.forEach(log => {
      if (log.parent_run_id) {
        if (!grouped[log.parent_run_id]) {
          grouped[log.parent_run_id] = [];
        }
        grouped[log.parent_run_id].push(log);
      }
    });
    return grouped;
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-[#d8d3ca] shadow-sm p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-20 bg-gray-100 rounded"></div>
          <div className="h-20 bg-gray-100 rounded"></div>
          <div className="h-20 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-[#d8d3ca] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#d8d3ca] bg-gray-50 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold uppercase text-gray-500">Execution History</span>
          <span className="text-[10px] font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
            Last {runs.length} runs
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchRuns}
            className="px-3 py-1.5 text-xs border border-[#d8d3ca] rounded-lg hover:bg-gray-100 transition-colors flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <button
            onClick={triggerRun}
            className="px-3 py-1.5 text-xs bg-[#0b6b72] text-white rounded-lg hover:bg-[#0a5c62] transition-colors flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Run Now
          </button>
        </div>
      </div>

      {/* Run List */}
      <div className="divide-y divide-[#d8d3ca]/50">
        {runs.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <p className="text-gray-400 text-sm font-medium">No runs yet</p>
            <p className="text-gray-300 text-xs mt-1">Trigger a run to see execution history here.</p>
            <button
              onClick={triggerRun}
              className="mt-4 px-4 py-2 bg-[#0b6b72] text-white rounded-lg text-xs font-medium hover:bg-[#0a5c62] transition-colors"
            >
              Trigger First Run
            </button>
          </div>
        ) : (
          runs.map((run) => {
            const isExpanded = expandedRunId === run.run_id;
            
            // Get logs for this run
            const runLogs = run.logs || [];
            
            // Group child executions by parent_run_id
            const childrenByParent = groupLogsByParent(runLogs);
            
            // Find parent logs (logs that have children)
            const parentLogIds = Object.keys(childrenByParent);

            return (
              <div key={run.run_id} className="hover:bg-gray-50 transition-colors">
                {/* Run Summary Row */}
                <div
                  className="px-6 py-4 flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedRunId(isExpanded ? null : run.run_id)}
                >
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                      run.status === 'SUCCESS' || run.status === 'success' ? 'bg-green-500' :
                      run.status === 'FAILED' || run.status === 'failed' ? 'bg-red-500' :
                      run.status === 'RUNNING' || run.status === 'running' ? 'bg-blue-500 animate-pulse' :
                      'bg-yellow-500'
                    }`} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-gray-500">{run.run_id}</span>
                        {getStatusBadge(run.status)}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-[11px] text-gray-400">
                        <span>{formatTime(run.started_at)}</span>
                        <span>·</span>
                        <span>{formatDuration(run.duration_ms)}</span>
                        {run.error && (
                          <>
                            <span>·</span>
                            <span className="text-red-400 truncate max-w-[200px]">
                              ⚠ {run.error}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <svg
                    className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>

                {/* Expanded Run Detail */}
                {isExpanded && (
                  <div className="px-6 pb-4 pl-14">
                    <div className="bg-gray-50 rounded-xl border border-[#d8d3ca] p-4 space-y-4">
                      {/* Run Metadata Grid */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                        <div>
                          <span className="text-gray-400 block">Run ID</span>
                          <span className="font-mono font-medium">{run.run_id}</span>
                        </div>
                        <div>
                          <span className="text-gray-400 block">Pipeline</span>
                          <span className="font-medium">{pipelineName}</span>
                        </div>
                        <div>
                          <span className="text-gray-400 block">Started</span>
                          <span className="font-medium">{formatTime(run.started_at)}</span>
                        </div>
                        <div>
                          <span className="text-gray-400 block">Duration</span>
                          <span className="font-medium">{formatDuration(run.duration_ms)}</span>
                        </div>
                        {run.ended_at && (
                          <div>
                            <span className="text-gray-400 block">Ended</span>
                            <span className="font-medium">{formatTime(run.ended_at)}</span>
                          </div>
                        )}
                        {run.error && (
                          <div className="col-span-2">
                            <span className="text-gray-400 block">Error</span>
                            <span className="text-red-600 font-medium">{run.error}</span>
                          </div>
                        )}
                      </div>

                      {/* Child Executions Section */}
                      {Object.entries(childrenByParent).map(([parentId, children]) => (
                        <div key={parentId} className="border-l-2 border-[#0b6b72] pl-4">
                          <button
                            onClick={() => setExpandedChildId(expandedChildId === parentId ? null : parentId)}
                            className="flex items-center justify-between w-full mb-2"
                          >
                            <div className="flex items-center gap-2">
                              <svg className={`w-4 h-4 text-gray-400 transition-transform ${expandedChildId === parentId ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                              </svg>
                              <span className="text-xs font-bold text-gray-700">
                                {children.length} Child Execution{children.length !== 1 ? 's' : ''}
                              </span>
                              <span className="text-[10px] text-gray-400 font-mono">
                                Parent: {parentId}
                              </span>
                            </div>
                            <div className="flex gap-2">
                              <span className="text-[10px] px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                                {children.filter(c => c.status === 'success').length} Success
                              </span>
                              <span className="text-[10px] px-2 py-0.5 bg-red-100 text-red-700 rounded-full">
                                {children.filter(c => c.status === 'failed').length} Failed
                              </span>
                            </div>
                          </button>

                          {/* Child Cards */}
                          {expandedChildId === parentId && (
                            <div className="space-y-3 mt-3">
                              {children.map((child, idx) => (
                                <div 
                                  key={child.step_id} 
                                  className="bg-white border border-[#d8d3ca] rounded-lg overflow-hidden"
                                >
                                  {/* Child Header */}
                                  <div 
                                    className="px-4 py-2 bg-gray-50 border-b border-[#d8d3ca] flex items-center justify-between cursor-pointer"
                                    onClick={() => setExpandedChildId(expandedChildId === `${parentId}-${idx}` ? null : `${parentId}-${idx}`)}
                                  >
                                    <div className="flex items-center gap-3">
                                      <div className={`w-2 h-2 rounded-full ${
                                        child.status === 'success' ? 'bg-green-500' :
                                        child.status === 'failed' ? 'bg-red-500' :
                                        child.status === 'skipped' ? 'bg-gray-400' :
                                        'bg-yellow-500'
                                      }`} />
                                      <span className="text-xs font-mono text-gray-600">{child.step_id}</span>
                                      {getStatusBadge(child.status)}
                                    </div>
                                    <svg
                                      className={`w-3 h-3 text-gray-400 transition-transform ${expandedChildId === `${parentId}-${idx}` ? 'rotate-180' : ''}`}
                                      fill="none" stroke="currentColor" viewBox="0 0 24 24"
                                    >
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                  </div>

                                  {/* Child Details */}
                                  {expandedChildId === `${parentId}-${idx}` && (
                                    <div className="p-4 space-y-3">
                                      {/* Execution Reason */}
                                      {child.execution_reason && (
                                        <div className="text-xs text-gray-600 bg-gray-50 p-2 rounded">
                                          <span className="font-bold">Reason:</span> {child.execution_reason}
                                        </div>
                                      )}

                                      {/* Extracted Fields Table */}
                                      {child.extracted_fields && Object.keys(child.extracted_fields).length > 0 && (
                                        <div>
                                          <div className="text-[11px] font-bold text-gray-500 uppercase mb-2">
                                            Extracted Fields
                                          </div>
                                          <div className="bg-white border border-[#d8d3ca] rounded-lg overflow-hidden">
                                            <table className="min-w-full divide-y divide-[#d8d3ca]">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  <th className="px-3 py-2 text-left text-[10px] font-bold text-gray-500 uppercase">Field</th>
                                                  <th className="px-3 py-2 text-left text-[10px] font-bold text-gray-500 uppercase">Value</th>
                                                </tr>
                                              </thead>
                                              <tbody className="bg-white divide-y divide-[#d8d3ca]/50">
                                                {Object.entries(child.extracted_fields).map(([field, value]) => (
                                                  <tr key={field}>
                                                    <td className="px-3 py-2 text-xs font-mono text-gray-600">{field}</td>
                                                    <td className="px-3 py-2 text-xs text-gray-800 break-words max-w-[300px]">
                                                      {typeof value === 'string' ? value : JSON.stringify(value)}
                                                    </td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        </div>
                                      )}

                                      {/* Result Data */}
                                      {child.result_data && (
                                        <div>
                                          <div className="text-[11px] font-bold text-gray-500 uppercase mb-2">
                                            Result Data
                                          </div>
                                          <pre className="text-[10px] bg-[#1a1a2e] text-green-300 p-3 rounded-lg overflow-x-auto max-h-32">
                                            {JSON.stringify(child.result_data, null, 2)}
                                          </pre>
                                        </div>
                                      )}

                                      {/* Error Details */}
                                      {child.error_detail && (
                                        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                                          <div className="text-xs font-bold text-red-700 mb-1">Error</div>
                                          <pre className="text-xs text-red-600 whitespace-pre-wrap">{child.error_detail}</pre>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}

                      {/* Individual Logs (non-child) */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[11px] font-bold text-gray-500 uppercase">Execution Log</span>
                          <span className="text-[10px] text-gray-400">{runLogs.length} entries</span>
                        </div>
                        <div className="bg-[#1a1a2e] rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-[11px] leading-relaxed">
                          {runLogs.length === 0 ? (
                            <div className="text-gray-500 italic">No logs recorded for this run.</div>
                          ) : (
                            runLogs
                              .filter(log => !log.parent_run_id) // Filter out child logs (they're shown above)
                              .map((log, idx) => (
                                <div key={idx} className={`flex gap-2 ${
                                  log.status === 'failed' ? 'text-red-400' :
                                  log.status === 'success' ? 'text-green-300' :
                                  log.status === 'skipped' ? 'text-gray-400' :
                                  'text-gray-400'
                                }`}>
                                  <span className="text-gray-600 flex-shrink-0">
                                    {new Date(log.started_at).toLocaleTimeString()}
                                  </span>
                                  <span className="text-gray-500 flex-shrink-0">[{log.status.toUpperCase()}]</span>
                                  <span>{log.step_id}</span>
                                  {log.execution_reason && (
                                    <span className="text-gray-500">- {log.execution_reason}</span>
                                  )}
                                </div>
                              ))
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Summary Footer */}
      {runs.length > 0 && (
        <div className="px-6 py-3 border-t border-[#d8d3ca] bg-gray-50 flex items-center gap-4 text-[11px] text-gray-500">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            <span>{runs.filter(r => r.status === 'SUCCESS' || r.status === 'success').length} succeeded</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            <span>{runs.filter(r => r.status === 'FAILED' || r.status === 'failed').length} failed</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            <span>{runs.filter(r => r.status === 'RUNNING' || r.status === 'running').length} running</span>
          </div>
          <div className="ml-auto text-gray-300">
            Success rate: {runs.length > 0 ? Math.round((runs.filter(r => r.status === 'SUCCESS' || r.status === 'success').length / runs.length) * 100) : 0}%
          </div>
        </div>
      )}
    </div>
  );
}