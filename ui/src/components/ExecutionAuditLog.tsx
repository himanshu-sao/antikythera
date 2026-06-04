import React, { useState, useEffect } from 'react';
import { apiUrl } from '../config';
import { ExecutionLog, PipelineRun } from '../types';
import toast from 'react-hot-toast';

interface ExecutionAuditLogProps {
  pipelineId: string;
  onClose: () => void;
}

interface ChildExecutionCardProps {
  child: ExecutionLog;
  index: number;
}

function ChildExecutionCard({ child, index }: ChildExecutionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusColors = {
    success: 'bg-green-100 text-green-700 border-green-300',
    failed: 'bg-red-100 text-red-700 border-red-300',
    skipped: 'bg-gray-100 text-gray-600 border-gray-300',
    pending: 'bg-yellow-100 text-yellow-700 border-yellow-300',
    running: 'bg-blue-100 text-blue-700 border-blue-300',
  };

  const statusIcons = {
    success: '✓',
    failed: '✗',
    skipped: '⟳',
    pending: '⏳',
    running: '↻',
  };

  return (
    <div className="border border-[#d8d3ca] rounded-lg overflow-hidden mb-3 bg-white">
      {/* Card Header */}
      <div
        className="px-4 py-3 bg-gray-50 border-b border-[#d8d3ca] flex items-center justify-between cursor-pointer hover:bg-gray-100 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 flex-1">
          <div className="flex items-center justify-center w-6 h-6 rounded-full bg-white border border-gray-300 text-xs font-bold text-gray-600">
            {index + 1}
          </div>
          <div className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
            statusColors[child.status] || 'bg-gray-100 text-gray-600'
          }`}>
            {statusIcons[child.status] || '?'}
          </div>
          <span className="text-xs font-mono text-gray-600">{child.step_id}</span>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
            statusColors[child.status] || 'bg-gray-100 text-gray-600 border-gray-300'
          }`}>
            {child.status}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* Card Body */}
      {isExpanded && (
        <div className="p-4 space-y-4 bg-white">
          {/* Execution Reason */}
          {child.execution_reason && (
            <div className="text-sm bg-blue-50 border border-blue-200 rounded-lg p-3">
              <span className="font-bold text-blue-800 text-xs uppercase block mb-1">
                Execution Reason
              </span>
              <p className="text-blue-900">{child.execution_reason}</p>
            </div>
          )}

          {/* Extracted Fields */}
          {child.extracted_fields && Object.keys(child.extracted_fields).length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-gray-500 uppercase">
                  Extracted Fields
                </span>
                <span className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                  {Object.keys(child.extracted_fields).length} fields
                </span>
              </div>
              <div className="bg-white border border-[#d8d3ca] rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-[#d8d3ca]">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                        Field
                      </th>
                      <th className="px-3 py-2 text-left text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-[#d8d3ca]/50">
                    {Object.entries(child.extracted_fields).map(([field, value]) => (
                      <tr key={field} className="hover:bg-gray-50 transition-colors">
                        <td className="px-3 py-2 text-xs font-mono text-gray-600 whitespace-nowrap">
                          {field}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-800">
                          {typeof value === 'string' ? (
                            <span className="line-clamp-2">{value}</span>
                          ) : (
                            <pre className="text-[10px] bg-gray-50 p-1 rounded max-w-md overflow-x-auto">
                              {JSON.stringify(value, null, 2)}
                            </pre>
                          )}
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
              <div className="text-xs font-bold text-gray-500 uppercase mb-2">
                Result Data
              </div>
              <pre className="text-[10px] bg-[#1a1a2e] text-green-300 p-3 rounded-lg overflow-x-auto max-h-40">
                {JSON.stringify(child.result_data, null, 2)}
              </pre>
            </div>
          )}

          {/* Error Details */}
          {child.error_detail && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-xs font-bold text-red-700">Error Details</span>
              </div>
              <pre className="text-xs text-red-600 whitespace-pre-wrap break-words">
                {child.error_detail}
              </pre>
            </div>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-100">
            <div>
              <span className="text-[10px] text-gray-400 block">Started</span>
              <span className="text-xs font-medium">{new Date(child.started_at).toLocaleString()}</span>
            </div>
            {child.ended_at && (
              <div>
                <span className="text-[10px] text-gray-400 block">Ended</span>
                <span className="text-xs font-medium">{new Date(child.ended_at).toLocaleString()}</span>
              </div>
            )}
            {child.duration_ms && (
              <div>
                <span className="text-[10px] text-gray-400 block">Duration</span>
                <span className="text-xs font-medium">
                  {child.duration_ms < 1000 ? `${child.duration_ms}ms` : `${(child.duration_ms / 1000).toFixed(2)}s`}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function ExecutionAuditLog({ pipelineId, onClose }: ExecutionAuditLogProps) {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);

  useEffect(() => {
    fetchRuns();
  }, [pipelineId]);

  const fetchRuns = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/pipelines/${pipelineId}/runs?limit=50`);
      if (!res.ok) throw new Error('Failed to fetch runs');
      const data = await res.json();
      setRuns(data);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Group logs by parent_run_id
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

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#d8d3ca] bg-gray-50 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-[#231f19]">Execution Audit Log</h2>
            <p className="text-xs text-gray-500 mt-1">
              Full audit trail with child executions and extracted fields
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b6b72] mx-auto"></div>
              <p className="text-gray-500 mt-4">Loading execution history...</p>
            </div>
          ) : runs.length === 0 ? (
            <div className="text-center py-12">
              <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p className="text-gray-400">No execution history yet</p>
            </div>
          ) : (
            <div className="space-y-6">
              {runs.map((run) => {
                const runLogs = run.logs || [];
                const childrenByParent = groupLogsByParent(runLogs);
                const parentLogIds = Object.keys(childrenByParent);

                return (
                  <div
                    key={run.run_id}
                    className="bg-white border border-[#d8d3ca] rounded-xl overflow-hidden"
                  >
                    {/* Run Header */}
                    <div
                      className="px-4 py-3 bg-gray-50 border-b border-[#d8d3ca] cursor-pointer hover:bg-gray-100 transition-colors"
                      onClick={() => setSelectedRun(selectedRun?.run_id === run.run_id ? null : run)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${
                            run.status === 'SUCCESS' || run.status === 'success'
                              ? 'bg-green-500'
                              : run.status === 'FAILED' || run.status === 'failed'
                              ? 'bg-red-500'
                              : 'bg-yellow-500'
                          }`} />
                          <span className="text-xs font-mono text-gray-600">{run.run_id}</span>
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            run.status === 'SUCCESS' || run.status === 'success'
                              ? 'bg-green-100 text-green-700'
                              : run.status === 'FAILED' || run.status === 'failed'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-yellow-100 text-yellow-700'
                          }`}>
                            {run.status}
                          </span>
                          {parentLogIds.length > 0 && (
                            <span className="text-[10px] px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                              {parentLogIds.length} fan-out groups
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span>{new Date(run.started_at).toLocaleString()}</span>
                          {run.duration_ms && (
                            <span className="font-mono">
                              {run.duration_ms < 1000 ? `${run.duration_ms}ms` : `${(run.duration_ms / 1000).toFixed(2)}s`}
                            </span>
                          )}
                          <svg
                            className={`w-4 h-4 transition-transform ${selectedRun?.run_id === run.run_id ? 'rotate-180' : ''}`}
                            fill="none" stroke="currentColor" viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </div>

                    {/* Run Details */}
                    {selectedRun?.run_id === run.run_id && (
                      <div className="p-4 space-y-4">
                        {/* Summary Stats */}
                        <div className="grid grid-cols-4 gap-3">
                          <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-green-700">
                              {runLogs.filter(l => l.status === 'success').length}
                            </div>
                            <div className="text-[10px] text-green-600 uppercase font-bold">Success</div>
                          </div>
                          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-red-700">
                              {runLogs.filter(l => l.status === 'failed').length}
                            </div>
                            <div className="text-[10px] text-red-600 uppercase font-bold">Failed</div>
                          </div>
                          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-gray-700">
                              {runLogs.filter(l => l.status === 'skipped').length}
                            </div>
                            <div className="text-[10px] text-gray-600 uppercase font-bold">Skipped</div>
                          </div>
                          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-blue-700">
                              {runLogs.length}
                            </div>
                            <div className="text-[10px] text-blue-600 uppercase font-bold">Total</div>
                          </div>
                        </div>

                        {/* Child Executions */}
                        {Object.entries(childrenByParent).map(([parentId, children]) => (
                          <div key={parentId} className="border-l-4 border-[#0b6b72] pl-4">
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <svg className="w-4 h-4 text-[#0b6b72]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                </svg>
                                <span className="text-sm font-bold text-gray-700">
                                  Fan-out: {children.length} child execution{children.length !== 1 ? 's' : ''}
                                </span>
                                <span className="text-[10px] font-mono text-gray-400">
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
                            </div>
                            <div className="space-y-2">
                              {children.map((child, idx) => (
                                <ChildExecutionCard key={child.step_id} child={child} index={idx} />
                              ))}
                            </div>
                          </div>
                        ))}

                        {/* Individual Logs (non-children) */}
                        {runLogs.filter(l => !l.parent_run_id).length > 0 && (
                          <div>
                            <div className="text-xs font-bold text-gray-500 uppercase mb-2">
                              Individual Steps
                            </div>
                            <div className="space-y-2">
                              {runLogs
                                .filter(l => !l.parent_run_id)
                                .map((log, idx) => (
                                  <div
                                    key={log.step_id || idx}
                                    className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg"
                                  >
                                    <div className={`w-2 h-2 rounded-full ${
                                      log.status === 'success' ? 'bg-green-500' :
                                      log.status === 'failed' ? 'bg-red-500' :
                                      log.status === 'skipped' ? 'bg-gray-400' :
                                      'bg-yellow-500'
                                    }`} />
                                    <span className="text-xs font-mono text-gray-600 flex-1">
                                      {log.step_id}
                                    </span>
                                    {log.execution_reason && (
                                      <span className="text-[10px] text-gray-500 italic">
                                        {log.execution_reason}
                                      </span>
                                    )}
                                  </div>
                                ))}
                            </div>
                          </div>
                        )}

                        {/* Error Highlight */}
                        {run.error && (
                          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                            <div className="flex items-center gap-2">
                              <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              <span className="text-xs font-bold text-red-700">Run Error</span>
                            </div>
                            <p className="text-xs text-red-600 mt-1">{run.error}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[#d8d3ca] bg-gray-50 flex items-center justify-between">
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
            onClick={onClose}
            className="px-4 py-1.5 text-xs bg-[#0b6b72] text-white rounded-lg hover:bg-[#0a5c62] transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}