import React, { useState, useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';
import { Search } from 'lucide-react';

interface Integration {
  name: string;
  type: 'native' | 'mcp';
  config: any;
  created_at: string;
  status?: 'connected' | 'error' | 'warning' | 'disconnected';
  last_sync?: string;
  description?: string;
}

interface TestResult {
  status: 'success' | 'error';
  message: string;
  data?: any;
}

interface Tool {
  name: string;
  description?: string;
  inputSchema?: any;
}

interface ExecutionResult {
  result: any;
  logs?: string;
}

interface ToolItemProps {
  tool: Tool;
  integrationName: string;
  onRun: (name: string) => Promise<ExecutionResult>;
}

export function IntegrationsManager() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newInt, setNewInt] = useState({ name: '', type: 'native', config: '' });
  const [showSecretModal, setShowSecretModal] = useState(false);
  const [secretProfile, setSecretProfile] = useState('');
  const [secretData, setSecretData] = useState('');
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  
  const [editingInt, setEditingInt] = useState<Integration | null>(null);
  const [editConfig, setEditConfig] = useState('');
  const [isTestingEdit, setIsTestingEdit] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [showTestLogs, setShowTestLogs] = useState(false);
  
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [isFetchingTools, setIsFetchingTools] = useState(false);
  
  // Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'native' | 'mcp'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'connected' | 'error' | 'warning' | 'disconnected'>('all');
  
  // Detail modal state (centered)
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  // Focus management refs
  const addCardRef = useRef<HTMLDivElement>(null);
  const addNameRef = useRef<HTMLInputElement>(null);
  const editConfigRef = useRef<HTMLTextAreaElement>(null);
  const secretProfileRef = useRef<HTMLInputElement>(null);
  const drawerCloseBtnRef = useRef<HTMLButtonElement>(null);

  // Effect: focus Add modal input when opened, return focus to button when closed
  useEffect(() => {
    if (showAddModal) {
      addNameRef.current?.focus();
    } else {
      addCardRef.current?.focus();
    }
  }, [showAddModal]);

  // Effect: focus Edit modal textarea when opened
  useEffect(() => {
    if (editingInt) {
      editConfigRef.current?.focus();
    }
  }, [editingInt]);

  // Effect: focus Secret modal first input when opened
  useEffect(() => {
    if (showSecretModal) {
      secretProfileRef.current?.focus();
    }
  }, [showSecretModal]);

  // Effect: focus drawer close button when drawer opens
  useEffect(() => {
    if (showDetailModal) {
      drawerCloseBtnRef.current?.focus();
    }
  }, [showDetailModal]);

  useEffect(() => {
    fetchIntegrations();
  }, []);

  // Computed filtered integrations
  const filteredIntegrations = integrations.filter(int => {
    const matchesSearch = !searchQuery || int.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === 'all' || int.type === typeFilter;
    const matchesStatus = statusFilter === 'all' || int.status === statusFilter;
    return matchesSearch && matchesType && matchesStatus;
  });

  const fetchIntegrations = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/integrations/`);
      if (!res.ok) throw new Error('Failed to fetch integrations');
      const data = await res.json();
      // Handle both legacy array response and new { integrations: [] } shape used in tests
      setIntegrations(Array.isArray(data) ? data : data.integrations || []);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const fetchTools = async (name: string) => {
    setIsFetchingTools(true);
    try {
      const res = await fetch(`${apiUrl}/api/integrations/${name}/tools`);
      if (!res.ok) throw new Error('Failed to fetch tools');
      const data = await res.json();
      
      const tools = 
        data.data?.result?.result?.tools || 
        data.data?.result?.tools || 
        data.data?.tools || 
        [];
        
      setAvailableTools(tools);
      if (tools.length === 0) {
        toast.error("No tools found for this integration.");
      }
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsFetchingTools(false);
    }
  };

  const handleAdd = async () => {
    try {
      const config = JSON.parse(newInt.config);
      const res = await fetch(`${apiUrl}/api/integrations/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newInt, config }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to add integration');
      }
      setShowAddModal(false);
      setNewInt({ name: '', type: 'native', config: '' });
      fetchIntegrations();
      toast.success("Integration added");
    } catch (e: any) {
      toast.error(e.message || "Invalid config JSON or API error");
    }
  };

  const handleToggle = async (intg: Integration) => {
    const currentEnabled = intg.config?.enabled ?? true;
    const newEnabled = !currentEnabled;
    const updatedConfig = { ...intg.config, enabled: newEnabled };
    try {
      const res = await fetch(`${apiUrl}/api/integrations/${intg.name}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: updatedConfig }),
      });
      if (!res.ok) throw new Error('Failed to toggle');
      fetchIntegrations();
      toast.success(`Integration ${newEnabled ? 'enabled' : 'disabled'}`);
    } catch (e: any) {
      toast.error(e.message || 'Toggle failed');
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Are you sure you want to delete the integration "${name}"? This action cannot be undone.`)) {
      return;
    }
    try {
      const res = await fetch(`${apiUrl}/api/integrations/${name}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      fetchIntegrations();
      toast.success("Deleted");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const handleTest = async (name: string): Promise<any> => {
    const res = await fetch(`${apiUrl}/api/integrations/${name}/test`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      throw { message: data.detail || 'Connection failed', data };
    }
    return data;
  };

  const handleUpdate = async (name: string) => {
    try {
      const config = JSON.parse(editConfig);
      const res = await fetch(`${apiUrl}/api/integrations/${name}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to update');
      }
      setEditingInt(null);
      fetchIntegrations();
      toast.success("Integration updated");
    } catch (e: any) {
      toast.error(e.message || "Failed to update");
    }
  };

  const handleSaveSecret = async () => {
    try {
      const secrets = JSON.parse(secretData);
      const res = await fetch(`${apiUrl}/api/integrations/secrets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: secretProfile, secrets }),
      });
      if (!res.ok) throw new Error('Failed to store secrets');
      setShowSecretModal(false);
      setSecretProfile('');
      setSecretData('');
      toast.success("Secrets updated");
    } catch (e: any) {
      toast.error("Invalid JSON secrets");
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-[#231f19]">Integrations Hub</h1>
          <p className="text-[#6f6a63] mt-1">Connect external services via Native Adapters or MCP Servers</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setShowSecretModal(true)}
            className="px-4 py-2 bg-white border border-[#d8d3ca] rounded-full text-sm text-[#6f6a63] hover:bg-gray-50 transition-all"
          >
            Manage Secrets
          </button>
          <button 
            onClick={(e) => { e.stopPropagation(); setShowAddModal(true); }}
            className="px-4 py-2 bg-[#0b6b72] text-white rounded-full text-sm font-medium hover:bg-[#0a5c62] transition-all shadow-sm"
          >
            + Add Connection
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex gap-4 mb-6 items-center">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
                      type="text"
                      placeholder="Search integrations..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      aria-label="Search integrations"
                      className="w-full pl-10 pr-4 py-2 bg-white border border-[#d8d3ca] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0b6b72] focus:border-transparent"
                    />
        </div>
        <div className="flex gap-3">
          <select
                      value={typeFilter}
                      onChange={(e) => setTypeFilter(e.target.value as any)}
                      aria-label="Filter by type"
                      className="px-3 py-2 bg-white border border-[#d8d3ca] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0b6b72]"
                    >
            <option value="all">All Types</option>
            <option value="native">Native</option>
            <option value="mcp">MCP</option>
          </select>
          <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value as any)}
                      aria-label="Filter by status"
                      className="px-3 py-2 bg-white border border-[#d8d3ca] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0b6b72]"
                    >
            <option value="all">All Status</option>
            <option value="connected">Connected</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="disconnected">Disconnected</option>
          </select>
        </div>
      </div>

      {/* Integrations Grid */}
      <div className="grid gap-6" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
        {filteredIntegrations.map(int => (
          <div 
            key={int.name} 
            className="bg-white border border-[#d8d3ca] rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-[#0b6b72] transition-all cursor-pointer group"
            onClick={() => {
              setSelectedIntegration(int);
              setShowDetailModal(true);
            }}
          >
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                  int.type === 'mcp' ? 'bg-indigo-100 text-indigo-600' : 'bg-teal-100 text-teal-600'
                }`}>
                  {int.type === 'mcp' ? '🔌' : '🛠️'}
                </div>
                <div>
                  <h3 className="font-bold text-[#231f19]">{int.name}</h3>
                  <span className="text-[10px] uppercase font-bold text-[#6f6a63] tracking-wider">{int.type}</span>
                </div>
              </div>
              <div className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${
                int.status === 'connected' ? 'bg-green-100 text-green-700' :
                int.status === 'error' ? 'bg-red-100 text-red-700' :
                int.status === 'warning' ? 'bg-amber-100 text-amber-700' :
                'bg-gray-100 text-gray-600'
              }`}>
                {int.status ? int.status.charAt(0).toUpperCase() + int.status.slice(1) : 'Disconnected'}
              </div>
              {int.type === 'mcp' && (
                <div className="ml-2 flex items-center">
                  <label className="text-xs text-gray-500 mr-1">Enabled</label>
                  <input type="checkbox" checked={int.config?.enabled ?? true} onChange={(e)=>{e.stopPropagation(); handleToggle(int);}} className="h-4 w-4" />
                </div>
              )}
            </div>
            
            {int.description && (
              <p className="text-sm text-gray-500 mb-4 line-clamp-2">{int.description}</p>
            )}
            
            <div className="flex justify-between items-center text-[11px] text-gray-400 mt-4 pt-4 border-t border-gray-100">
              <span>{int.last_sync ? `Synced: ${int.last_sync.split('T')[0]}` : 'Never synced'}</span>
              <div className="relative">
                              <button
                                onClick={(e) => { e.stopPropagation(); setMenuOpen(int.name); }}
                                className="p-1 text-gray-500 hover:text-gray-700"
                                aria-label="Menu"
                              >
                                ⋮
                              </button>
                              {menuOpen === int.name && (
                                <div className="absolute right-0 mt-2 w-32 bg-white border rounded shadow-lg z-10">
                                  <button
                                    onClick={(e) => { e.stopPropagation(); setEditingInt(int); setEditConfig(JSON.stringify(int.config, null, 2)); setTestResult(null); setShowTestLogs(false); setMenuOpen(null); }}
                                    className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-100"
                                  >
                                    Edit
                                  </button>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleTest(int.name).then(() => toast.success('Connection successful')).catch(err => toast.error(err.message)); setMenuOpen(null); }}
                                    className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-100"
                                  >
                                    Test Connection
                                  </button>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); toast.success('Disconnected (mock)'); setMenuOpen(null); }}
                                    className="block w-full text-left px-3 py-2 text-sm text-yellow-600 hover:bg-yellow-50"
                                  >
                                    Disconnect
                                  </button>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleDelete(int.name); setMenuOpen(null); }}
                                    className="block w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                                  >
                                    Remove
                                  </button>
                                </div>
                              )}
                              </div>
            </div>
          </div>
        ))}
      {/* Add Connection CTA Card */}
      <div
        ref={addCardRef}
        tabIndex={0}
        className="flex items-center justify-center border border-dashed border-[#d8d3ca] rounded-2xl p-5 bg-gray-50 hover:bg-gray-100 cursor-pointer transition-all"
        onClick={() => setShowAddModal(true)}
        onKeyPress={(e) => { if (e.key === 'Enter' || e.key === ' ') setShowAddModal(true); }}
      >
        <span className="text-2xl font-bold text-[#0b6b72]">+ Add Connection</span>
      </div>
      </div>

      {/* Detail Modal (centered) */}
      {showDetailModal && selectedIntegration && (
        <>
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40" onClick={() => setShowDetailModal(false)}></div>
          <div className="fixed inset-0 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 overflow-y-auto max-h-[90vh]" role="dialog" aria-modal="true" aria-labelledby="detail-modal-title">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 id="detail-modal-title" className="text-2xl font-bold text-[#231f19]">{selectedIntegration.name}</h2>
                  <p className="text-sm text-gray-500 mt-1">{selectedIntegration.type === 'mcp' ? 'MCP Server' : 'Native Adapter'}</p>
                </div>
                <button ref={drawerCloseBtnRef} onClick={() => setShowDetailModal(false)} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-all">✕</button>
              </div>

              {/* Status Badge */}
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-bold mb-6 ${
                selectedIntegration.status === 'connected' ? 'bg-green-100 text-green-700' :
                selectedIntegration.status === 'error' ? 'bg-red-100 text-red-700' :
                selectedIntegration.status === 'warning' ? 'bg-amber-100 text-amber-700' :
                'bg-gray-100 text-gray-600'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  selectedIntegration.status === 'connected' ? 'bg-green-500' :
                  selectedIntegration.status === 'error' ? 'bg-red-500' :
                  selectedIntegration.status === 'warning' ? 'bg-amber-500' :
                  'bg-gray-500'
                }`} />
                {selectedIntegration.status || 'disconnected'}
              </div>

              {/* Details */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Description</label>
                  <p className="text-sm text-gray-700">{selectedIntegration.description || 'No description provided'}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Type</label>
                    <p className="text-sm text-gray-900 capitalize">{selectedIntegration.type}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Created</label>
                    <p className="text-sm text-gray-900">{new Date(selectedIntegration.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Last Sync</label>
                  <p className="text-sm text-gray-900">
                    {selectedIntegration.last_sync ? new Date(selectedIntegration.last_sync).toLocaleString() : 'Never synced'}
                  </p>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Configuration</label>
                  <pre className="bg-gray-50 p-3 rounded-lg text-xs font-mono text-gray-700 overflow-x-auto max-h-48 custom-scrollbar">
                    {JSON.stringify(selectedIntegration.config, null, 2)}
                  </pre>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 mt-8 pt-6 border-t border-gray-100">
                <button
                  onClick={() => {
                    setShowDetailModal(false);
                    setEditingInt(selectedIntegration);
                    setEditConfig(JSON.stringify(selectedIntegration.config, null, 2));
                    setTestResult(null);
                    setShowTestLogs(false);
                  }}
                  className="flex-1 px-4 py-2 bg-[#0b6b72] text-white rounded-lg font-medium hover:bg-[#0a5c62] transition-all"
                >
                  Edit Connection
                </button>
                <button
                  onClick={async () => {
                    try {
                      const result = await handleTest(selectedIntegration.name);
                      setTestResult({ status: 'success', message: 'Success', data: result.data });
                      toast.success('Test successful');
                    } catch (e: any) {
                      setTestResult({ status: 'error', message: e.message, data: e.data });
                      toast.error(`Test failed: ${e.message}`);
                    }
                  }}
                  className="px-4 py-2 bg-[#fbfaf7] text-[#0b6b72] border border-[#d8d3ca] rounded-lg font-medium hover:bg-[#f5f3ed]"
                >
                  Test Connection
                </button>
                <button
                  onClick={() => { setShowDetailModal(false); handleDelete(selectedIntegration.name); }}
                  className="px-4 py-2 bg-white border border-red-200 text-red-600 rounded-lg font-medium hover:bg-red-50 transition-all"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Edit Modal */}
      {editingInt && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title">
          <div className="bg-white rounded-2xl shadow-xl w-full md:w-1/2 p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 id="edit-modal-title" className="text-xl font-bold text-[#231f19]">Edit Integration: {editingInt.name}</h2>
              <button onClick={() => setEditingInt(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Config (JSON)</label>
                <textarea 
                  ref={editConfigRef}
                  className="w-full p-2 border rounded-lg font-mono text-xs h-48 resize-y overflow-auto custom-scrollbar" 
                  value={editConfig} 
                  onChange={e => setEditConfig(e.target.value)} 
                />
              </div>

              {testResult && (
                <div className={`p-3 rounded-lg text-xs font-mono ${testResult.status === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                  <p className="font-bold mb-1">{testResult.status === 'success' ? '✅ Test Passed' : '❌ Test Failed'}</p>
                  {testResult.status === 'success' && testResult.data?.result && (
                    <div className="mb-2 p-2 bg-white/50 rounded border border-green-100">
                      <p className="text-[10px] uppercase font-bold opacity-70 mb-1">Connection Result:</p>
                      <pre className="whitespace-pre overflow-auto max-h-24 custom-scrollbar">
                        {typeof testResult.data.result === 'string'
                          ? testResult.data.result
                          : JSON.stringify(testResult.data.result, null, 2)}
                      </pre>
                    </div>
                  )}
                  {testResult.data?.logs && (
                    <div className="mt-2">
                      <button 
                        onClick={() => setShowTestLogs(!showTestLogs)}
                        className="text-[10px] font-bold underline opacity-70 hover:opacity-100 mb-1"
                      >
                        {showTestLogs ? 'Hide Logs' : 'Show Logs'}
                      </button>
                      {showTestLogs && (
                        <pre className="whitespace-pre overflow-auto max-h-32 bg-black/5 p-2 rounded border border-black/5 custom-scrollbar">
                          {testResult.data.logs || "No logs available."}
                        </pre>
                      )}
                    </div>
                  )}
                  {(!testResult.data?.result && !testResult.data?.logs) && (
                    <pre className="whitespace-pre overflow-auto max-h-48 custom-scrollbar">
                      {typeof testResult.data === 'string' ? testResult.data : JSON.stringify(testResult.data, null, 2)}
                    </pre>
                  )}
                </div>
              )}

              <div className="flex flex-col gap-3">
                <button 
                  onClick={async () => {
                    setIsTestingEdit(true);
                    setTestResult(null);
                    setShowTestLogs(false);
                    try {
                      const result = await handleTest(editingInt.name);
                      setTestResult({ status: 'success', message: 'Success', data: result.data });
                      toast.success("Test successful!");
                    } catch (e: any) {
                      setTestResult({ status: 'error', message: e.message, data: e.data });
                      toast.error(`Test failed: ${e.message}`);
                    } finally {
                      setIsTestingEdit(false);
                    }
                  }}
                  disabled={isTestingEdit}
                  className={`w-full py-2 rounded-lg font-medium transition-all ${isTestingEdit ? 'bg-gray-200 text-gray-500' : 'bg-[#fbfaf7] text-[#0b6b72] border border-[#d8d3ca] hover:bg-[#f5f3ed]'}`}
                >
                  {isTestingEdit ? 'Testing Connection...' : 'Test Connection'}
                </button>
                <div className="flex justify-end gap-3">
                  <button onClick={() => setEditingInt(null)} className="px-4 py-2 text-gray-600">Cancel</button>
                  <button 
                    onClick={() => handleUpdate(editingInt.name)} 
                    className="px-4 py-2 bg-[#0b6b72] text-white rounded-lg font-medium hover:bg-[#0a5c62]"
                  >
                    Save Changes
                  </button>
                </div>
              </div>

              {editingInt.type === 'mcp' && (
                <div className="pt-4 border-t border-gray-100">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-sm font-bold text-[#231f19]">Available Tools</h3>
                    <button 
                      onClick={() => fetchTools(editingInt.name)}
                      disabled={isFetchingTools}
                      className="text-xs text-[#0b6b72] font-bold hover:underline"
                    >
                      {isFetchingTools ? 'Loading...' : 'Refresh Tools'}
                    </button>
                  </div>
                  {availableTools.length > 0 ? (
                    <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                      {availableTools.map(tool => (
                        <ToolItem 
                          key={tool.name} 
                          tool={tool} 
                          integrationName={editingInt!.name} 
                          onRun={async (name) => {
                            const res = await fetch(`${apiUrl}/api/integrations/${editingInt!.name}/call`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ name, arguments: {} }),
                            });
                            const data = await res.json();
                            if (!res.ok) throw { message: data.detail || 'Tool execution failed', data };
                            return data.data;
                          }}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400 italic">No tools loaded. Click "Refresh Tools" to fetch them.</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-labelledby="add-modal-title">
          <div className="bg-white rounded-2xl shadow-xl w-full md:w-1/2 p-6">
            <h2 id="add-modal-title" className="text-xl font-bold mb-4 text-[#231f19]">Add Integration</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Connection Name</label>
                <input type="text" ref={addNameRef} className="w-full p-2 border rounded-lg" value={newInt.name} onChange={e => setNewInt({...newInt, name: e.target.value})} placeholder="e.g. GitHub Production" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Connector Type</label>
                <select className="w-full p-2 border rounded-lg" value={newInt.type} onChange={e => setNewInt({...newInt, type: e.target.value as any})}>
                  <option value="native">Native Adapter</option>
                  <option value="mcp">MCP Server</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Config (JSON)</label>
                <textarea 
                  className="w-full p-2 border rounded-lg font-mono text-xs h-32" 
                  value={newInt.config} 
                  onChange={e => setNewInt({...newInt, config: e.target.value})} 
                  placeholder='{"adapter_module": "api.adapters.github"}'
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button onClick={() => setShowAddModal(false)} className="px-4 py-2 text-gray-600">Cancel</button>
                <button onClick={handleAdd} className="px-4 py-2 bg-[#0b6b72] text-white rounded-lg font-medium">Add Connection</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Secret Modal */}
      {showSecretModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true" aria-labelledby="secret-modal-title">
          <div className="bg-white rounded-2xl shadow-xl w-full md:w-1/2 p-6">
            <h2 id="secret-modal-title" className="text-xl font-bold mb-4 text-[#231f19]">Secret Vault</h2>
            <div className="space-y-4">
                          <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Profile ID</label>
                            <input type="text" ref={secretProfileRef} className="w-full p-2 border rounded-lg" value={secretProfile} onChange={e => setSecretProfile(e.target.value)} placeholder="e.g. github_prod" />
                            <div className="flex gap-2 mt-2">
                              <button
                                onClick={async () => {
                                  if (!secretProfile) { toast.error('Enter profile ID first'); return; }
                                  try {
                                    const res = await fetch(`${apiUrl}/api/integrations/secrets/${secretProfile}`);
                                    if (!res.ok) throw new Error('Failed to load secrets');
                                    const data = await res.json();
                                    setSecretData(JSON.stringify(data, null, 2));
                                    toast.success('Secrets loaded');
                                  } catch (e:any) {
                                    toast.error(e.message);
                                  }
                                }}
                                className="px-3 py-1 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
                              >
                                Load
                              </button>
                              <button
                                onClick={() => { setSecretData(''); setSecretProfile(''); }}
                                className="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
                              >
                                Clear
                              </button>
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Secrets (JSON)</label>
                            <textarea 
                              className="w-full p-2 border rounded-lg font-mono text-xs h-32" 
                              value={secretData} 
                              onChange={e => setSecretData(e.target.value)} 
                              placeholder='{"api_key": "***", "token": "***"}'
                            />
                          </div>
                          <div className="flex justify-end gap-3 pt-4">
                            <button onClick={() => setShowSecretModal(false)} className="px-4 py-2 text-gray-600">Cancel</button>
                            <button onClick={handleSaveSecret} className="px-4 py-2 bg-[#0b6b72] text-white rounded-lg font-medium">Save Secrets</button>
                          </div>
                        </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ToolItem({ tool, integrationName, onRun }: ToolItemProps) {
  const [isLocalRunning, setIsLocalRunning] = useState(false);
  const [localResult, setLocalResult] = useState<TestResult | null>(null);
  const [showToolLogs, setShowToolLogs] = useState(false);

  const isQuickRun = !tool.inputSchema || Object.keys(tool.inputSchema.properties || {}).length === 0;

  const handleLocalRun = async () => {
    setIsLocalRunning(true);
    setLocalResult(null);
    setShowToolLogs(false);
    try {
      const data = await onRun(tool.name);
      setLocalResult({ status: 'success', message: 'Success', data });
      toast.success(`Tool ${tool.name} executed!`);
    } catch (e: any) {
      setLocalResult({ status: 'error', message: e.message, data: e.data });
      toast.error(`Tool execution failed: ${e.message}`);
    } finally {
      setIsLocalRunning(false);
    }
  };

  return (
    <div className="p-2 bg-gray-50 rounded-lg text-xs border border-gray-100 group/tool">
      <div className="flex justify-between items-start">
        <div>
          <div className="font-bold text-[#231f19]">{tool.name}</div>
          {tool.description && <div className="text-gray-500 text-[10px] mt-0.5">{tool.description}</div>}
        </div>
        {isQuickRun && (
          <button 
            onClick={handleLocalRun}
            disabled={isLocalRunning}
            className="px-2 py-1 bg-white border border-[#d8d3ca] rounded hover:bg-gray-100 transition-colors text-[10px] font-bold text-[#0b6b72] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLocalRunning ? '...' : '▶ Run'}
          </button>
        )}
      </div>
      {localResult && (
        <div className={`mt-2 p-2 rounded text-[10px] font-mono ${localResult.status === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-700'}`}>
          <p className="font-bold mb-1">{localResult.status === 'success' ? '✅ Success' : '❌ Failed'}</p>
          {localResult.status === 'success' && localResult.data?.result && (
            <div className="mb-2 p-2 bg-white/50 rounded border border-green-100">
              <p className="text-[10px] uppercase font-bold opacity-70 mb-1">Execution Result:</p>
              <pre className="whitespace-pre overflow-auto max-h-24 custom-scrollbar">
                {typeof localResult.data.result === 'string'
                  ? localResult.data.result
                  : JSON.stringify(localResult.data.result, null, 2)}
              </pre>
            </div>
          )}
          {localResult.data?.logs && (
            <div className="mt-2">
              <button 
                onClick={() => setShowToolLogs(!showToolLogs)}
                className="text-[10px] font-bold underline opacity-70 hover:opacity-100 mb-1"
              >
                {showToolLogs ? 'Hide Logs' : 'Show Logs'}
              </button>
              {showToolLogs && (
                <pre className="whitespace-pre overflow-auto max-h-32 bg-black/5 p-2 rounded border border-black/5 custom-scrollbar">
                  {localResult.data.logs || "No logs available."}
                </pre>
              )}
            </div>
          )}
          {(!localResult.data?.result && !localResult.data?.logs) && (
            <pre className="whitespace-pre overflow-auto max-h-20 custom-scrollbar">
              {typeof localResult.data === 'string' ? localResult.data : JSON.stringify(localResult.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
