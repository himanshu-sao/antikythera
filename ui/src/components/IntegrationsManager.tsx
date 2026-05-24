import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';

interface Integration {
  name: string;
  type: 'native' | 'mcp';
  config: any;
  created_at: string;
}

export function IntegrationsManager() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newInt, setNewInt] = useState({ name: '', type: 'native', config: '' });
  const [showSecretModal, setShowSecretModal] = useState(false);
  const [secretProfile, setSecretProfile] = useState('');
  const [secretData, setSecretData] = useState('');

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const fetchIntegrations = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/integrations/`);
      if (!res.ok) throw new Error('Failed to fetch integrations');
      const data = await res.json();
      setIntegrations(data);
    } catch (e: any) {
      toast.error(e.message);
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
      if (!res.ok) throw new Error('Failed to add integration');
      setShowAddModal(false);
      setNewInt({ name: '', type: 'native', config: '' });
      fetchIntegrations();
      toast.success("Integration added");
    } catch (e: any) {
      toast.error("Invalid config JSON or API error");
    }
  };

  const handleDelete = async (name: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/integrations/${name}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      fetchIntegrations();
      toast.success("Deleted");
    } catch (e: any) {
      toast.error(e.message);
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
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-[#231f19]">Integrations Hub</h1>
          <p className="text-[#6f6a63]">Connect external services via Native Adapters or MCP Servers</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setShowSecretModal(true)}
            className="px-4 py-2 bg-white border border-[#d8d3ca] rounded-full text-sm text-[#6f6a63] hover:bg-gray-50 transition-all"
          >
            Manage Secrets
          </button>
          <button 
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-[#0b6b72] text-white rounded-full text-sm font-medium hover:bg-[#0a5c62] transition-all shadow-sm"
          >
            + Add Connection
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {integrations.map(int => (
          <div key={int.name} className="bg-white border border-[#d8d3ca] rounded-2xl p-5 shadow-sm hover:shadow-md transition-all group">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${int.type === 'mcp' ? 'bg-indigo-100 text-indigo-600' : 'bg-teal-100 text-teal-600'}`}>
                  {int.type === 'mcp' ? '🔌' : '🛠️'}
                </div>
                <div>
                  <h3 className="font-bold text-[#231f19]">{int.name}</h3>
                  <span className="text-[10px] uppercase font-bold text-[#6f6a63] tracking-wider">{int.type}</span>
                </div>
              </div>
              <button 
                onClick={() => handleDelete(int.name)}
                className="p-2 text-gray-400 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
              >
                ✕
              </button>
            </div>
            <div className="bg-[#fbfaf7] rounded-lg p-3 mb-4">
              <div className="text-xs font-mono text-[#6f6a63] break-all">
                {JSON.stringify(int.config)}
              </div>
            </div>
            <div className="flex justify-between items-center text-[11px] text-gray-400">
              <span>Created: {int.created_at.split('T')[0]}</span>
              <button className="text-[#0b6b72] font-bold hover:underline">Test Connection →</button>
            </div>
          </div>
        ))}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h2 className="text-xl font-bold mb-4 text-[#231f19]">Add Integration</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Connection Name</label>
                <input type="text" className="w-full p-2 border rounded-lg" value={newInt.name} onChange={e => setNewInt({...newInt, name: e.target.value})} placeholder="e.g. GitHub Production" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Connector Type</label>
                <select className="w-full p-2 border rounded-lg" value={newInt.type} onChange={e => setNewInt({...newInt, type: e.target.value})}>
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

      {showSecretModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h2 className="text-xl font-bold mb-4 text-[#231f19]">Secret Vault</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Profile ID</label>
                <input type="text" className="w-full p-2 border rounded-lg" value={secretProfile} onChange={e => setSecretProfile(e.target.value)} placeholder="e.g. github_prod" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Secrets (JSON)</label>
                <textarea 
                  className="w-full p-2 border rounded-lg font-mono text-xs h-32" 
                  value={secretData} 
                  onChange={e => setSecretData(e.target.value)} 
                  placeholder='{"api_key": "ghp_...", "token": "..."}'
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
