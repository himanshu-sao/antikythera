import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { 
  Settings, 
  Cpu, 
  CheckCircle, 
  XCircle, 
  Loader, 
  Plus, 
  Trash2, 
  RefreshCw,
  Key,
  Zap,
  Server,
  Globe,
  Database
} from 'lucide-react';

interface ModelConfig {
  model_id: string;
  name: string;
  provider: string;
  is_default: boolean;
  api_key_set: boolean;
  endpoint: string | null;
  context_window: number;
  temperature: number;
  max_tokens: number;
}

interface AIConfig {
  default_provider: string;
  default_model_id: string;
  models: ModelConfig[];
  connection_settings: {
    timeout_seconds: number;
    max_retries: number;
    enable_fallback: boolean;
    enable_caching: boolean;
  };
}

interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  requires_api_key: boolean;
  features: string[];
  icon: React.ReactNode;
  color: string;
}

const AIEngineSettings: React.FC = () => {
  const [config, setConfig] = useState<AIConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  type Tab = 'overview' | 'models' | 'providers' | 'settings' | 'connections' | 'logs';
const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string; testing: boolean }>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [modelSearch, setModelSearch] = useState('');
  const [modelProviderFilter, setModelProviderFilter] = useState('all');
  const [showApiKeyModal, setShowApiKeyModal] = useState<string | null>(null);
  const [isAddingModel, setIsAddingModel] = useState(false);

  // Provider metadata
  const providers: ProviderInfo[] = [
    {
      id: 'ollama',
      name: 'Ollama',
      description: 'Local LLM server - No API key required',
      requires_api_key: false,
      features: ['local', 'text', 'completion', 'cost-free'],
      icon: <Server className="w-5 h-5" />,
      color: 'bg-green-500'
    },
    {
      id: 'nvidia_nim',
      name: 'NVIDIA NIM',
      description: 'High-performance inference microservices',
      requires_api_key: true,
      features: ['cloud', 'text', 'completion', 'chat', 'fast'],
      icon: <Zap className="w-5 h-5" />,
      color: 'bg-yellow-500'
    },
    {
      id: 'google_gemma',
      name: 'Google Gemma',
      description: 'Google\'s lightweight open models',
      requires_api_key: true,
      features: ['cloud', 'text', 'completion', 'chat'],
      icon: <Globe className="w-5 h-5" />,
      color: 'bg-teal-500'
    },
    {
      id: 'ibm_bob',
      name: 'IBM Bob',
      description: "IBM's enterprise AI platform",
      requires_api_key: true,
      features: ['cloud', 'text', 'completion', 'enterprise'],
      icon: <Database className="w-5 h-5" />,
      color: 'bg-purple-500'
    },
    {
      id: 'lm_studio',
      name: 'LM Studio',
      description: 'Local LLM studio interface – no API key required',
      requires_api_key: false,
      features: ['local', 'text', 'completion', 'chat'],
      icon: <Cpu className="w-5 h-5" />, // using Cpu icon as placeholder
      color: 'bg-indigo-500'
    }
  ];

  // Fetch config
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/ai-engine/config');
      const data = await res.json();
      setConfig(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async (modelId: string) => {
    setTestResults(prev => ({ ...prev, [modelId]: { ...prev[modelId], testing: true } }));
    
    try {
      const res = await fetch('/api/ai-engine/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId })
      });
      const data = await res.json();
      
      setTestResults(prev => ({
        ...prev,
        [modelId]: {
          success: res.ok,
          message: res.ok ? data.message : data.detail?.message || 'Connection failed',
          testing: false
        }
      }));
    } catch (err: any) {
      setTestResults(prev => ({
        ...prev,
        [modelId]: {
          success: false,
          message: err.message,
          testing: false
        }
      }));
    }
  };

  const setDefaultModel = async (modelId: string) => {
    try {
      const res = await fetch('/api/ai-engine/set-default', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId })
      });
      
      if (res.ok) {
        await fetchConfig();
        // Show success
        alert(`Default model set to ${modelId}`);
      } else {
        const data = await res.json();
        alert(`Failed: ${data.detail}`);
      }
    } catch (err: any) {
      alert('Failed to set default model: ' + err.message);
    }
  };

  const saveApiKey = async (modelId: string) => {
    const apiKey = apiKeys[modelId];
    if (!apiKey) {
      alert('Please enter an API key');
      return;
    }

    try {
      const res = await fetch('/api/ai-engine/set-api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId, api_key: apiKey })
      });

      if (res.ok) {
        setShowApiKeyModal(null);
        setApiKeys(prev => {
          const newKeys = { ...prev };
          delete newKeys[modelId];
          return newKeys;
        });
        await fetchConfig();
        alert('API key saved successfully');
      } else {
        const data = await res.json();
        alert(`Failed: ${data.detail}`);
      }
    } catch (err: any) {
      alert('Failed to save API key: ' + err.message);
    }
  };

  const getProviderInfo = (providerId: string) => {
    return providers.find(p => p.id === providerId) || providers[0];
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="w-8 h-8 animate-spin text-teal-500" />
        <span className="ml-3 text-gray-600">Loading AI Engine configuration...</span>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center text-red-700">
          <XCircle className="w-5 h-5 mr-2" />
          <span>Error loading configuration: {error}</span>
        </div>
        <button 
          onClick={fetchConfig}
          className="mt-3 px-4 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200 transition"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!config) {
    return <div className="p-4 text-gray-600">No configuration found</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">AI Engine Configuration</h2>
          <p className="text-gray-600 mt-1">Manage AI models, providers, and connection settings</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchConfig}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => setIsAddingModel(true)}
            className="flex items-center gap-2 px-4 py-2 bg-teal-500 text-white rounded hover:bg-teal-600 transition"
          >
            <Plus className="w-4 h-4" />
            Add Model
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {(['overview', 'models', 'providers', 'connections', 'logs'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-6 py-3 font-medium transition-colors border-b-2 ${
              activeTab === tab
                ? 'border-teal-500 text-teal-600'
                : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>


      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                                        <div className="bg-white border rounded-lg p-4">
                                          <div className="text-gray-600 text-sm">Total Models</div>
                                          <div className="text-2xl font-bold mt-1">{config.models.length}</div>
                                        </div>
                                        <div className="bg-white border rounded-lg p-4">
                                          <div className="text-gray-600 text-sm">Configured Providers</div>
                                          <div className="text-2xl font-bold mt-1">
                                            {new Set(config.models.map(m => m.provider)).size}
                                          </div>
                                        </div>
                                        <div className="bg-white border rounded-lg p-4">
                                          <div className="text-gray-600 text-sm">API Keys Set</div>
                                          <div className="text-2xl font-bold mt-1 text-green-600">
                                            {config.models.filter(m => m.api_key_set || m.provider === 'ollama').length}/{config.models.length}
                                          </div>
                                        </div>
                                        <div className="bg-white border rounded-lg p-4">
                                          <div className="text-gray-600 text-sm">Active Models</div>
                                          <div className="text-2xl font-bold mt-1 text-teal-600">
                                            {config.models.filter(m => m.is_default || m.api_key_set || m.provider === 'ollama').length}
                                          </div>
                                        </div>
                                        <div className="bg-white border rounded-lg p-4">
                                          <div className="text-gray-600 text-sm">Default Model</div>
                                          <div className="flex items-center text-xl font-bold mt-1 text-teal-600 truncate">
                                            {config.default_model_id}
                                            <button
                                              onClick={() => {
                                                navigator.clipboard.writeText(config.default_model_id);
                                                toast.success('Copied default model ID');
                                              }}
                                              className="ml-2 text-gray-400 hover:text-gray-600"
                                            >
                                              📋
                                            </button>
                                          </div>
                                        </div>
                                      </div>



        </div>
      )}

      {activeTab === 'models' && (
        <div>
          <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border rounded-lg p-4 flex items-center justify-between">
              <div><div className="text-sm text-gray-500">Total Models</div><div className="text-2xl font-bold text-gray-800">{config.models.length}</div></div>
              <div className="p-2 bg-teal-100 rounded"><Cpu className="w-5 h-5 text-teal-600" /></div>
            </div>
            <div className="bg-white border rounded-lg p-4 flex items-center justify-between">
              <div><div className="text-sm text-gray-500">Configured Keys</div><div className="text-2xl font-bold text-green-600">{config.models.filter(m => m.api_key_set || m.provider === 'ollama').length}</div></div>
              <div className="p-2 bg-green-100 rounded"><Key className="w-5 h-5 text-green-600" /></div>
            </div>
            <div className="bg-white border rounded-lg p-4 flex items-center justify-between">
              <div><div className="text-sm text-gray-500">Default Provider</div><div className="text-lg font-bold text-gray-800 capitalize">{config.default_provider.replace('_', ' ')}</div></div>
              <div className="p-2 bg-purple-100 rounded"><Zap className="w-5 h-5 text-purple-600" /></div>
            </div>
            <div className="bg-white border rounded-lg p-4 flex items-center justify-between">
              <div><div className="text-sm text-gray-500">Default Model</div><div className="text-lg font-bold text-teal-600">{config.default_model_id}</div></div>
              <div className="p-2 bg-yellow-100 rounded"><Server className="w-5 h-5 text-yellow-600" /></div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {config.models.map((model) => {
              const providerInfo = getProviderInfo(model.provider);
              const testResult = testResults[model.model_id];
              return (
                <div key={model.model_id} className={`border rounded-xl p-5 transition-all hover:shadow-lg ${model.is_default ? 'border-teal-400 bg-teal-50 shadow-md ring-2 ring-teal-100' : 'border-gray-200 bg-white hover:border-teal-300'}`}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`p-2.5 rounded-lg ${providerInfo.color} shadow-sm`}><div className="text-white">{providerInfo.icon}</div></div>
                    <div>
                      <h4 className="font-bold text-gray-800">{model.name}</h4>
                      <div className="text-xs text-gray-500">{providerInfo.name}</div>
                      {model.is_default && <span className="inline-block bg-teal-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full mt-1">DEFAULT</span>}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
                    <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Context</div><div className="font-semibold">{model.context_window}</div></div>
                    <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Max Tokens</div><div className="font-semibold">{model.max_tokens}</div></div>
                    <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Temperature</div><div className="font-semibold">{model.temperature}</div></div>
                    <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Status</div><div className={`font-semibold ${testResult?.success ? 'text-green-600' : testResult ? 'text-red-600' : model.api_key_set || model.provider === 'ollama' ? 'text-teal-600' : 'text-amber-600'}`}>{testResult?.success ? 'Active' : testResult ? 'Failed' : model.api_key_set || model.provider === 'ollama' ? 'Ready' : 'Needs Key'}</div></div>
                  </div>


                  <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-200">
                    {/* Test Connection Button - Always visible, cycles through states */}
                    <button
                      onClick={() => testConnection(model.model_id)}
                      disabled={testResult?.testing}
                      className={`px-3 py-1.5 rounded text-sm font-medium flex items-center gap-1.5 transition ${
                        testResult?.testing 
                          ? 'bg-gray-200 text-gray-500 cursor-wait' 
                          : testResult?.success 
                          ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                          : testResult && !testResult.success
                          ? 'bg-red-100 text-red-700 hover:bg-red-200'
                          : 'bg-teal-100 text-teal-700 hover:bg-teal-200'
                      }`}
                    >
                      {testResult?.testing ? (
                        <>
                          <Loader className="w-3.5 h-3.5 animate-spin" />
                          Testing...
                        </>
                      ) : testResult?.success ? (
                        <>
                          <CheckCircle className="w-3.5 h-3.5" />
                          Connected (Test Again)
                        </>
                      ) : testResult && !testResult.success ? (
                        <>
                          <XCircle className="w-3.5 h-3.5" />
                          Failed (Retry)
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-3.5 h-3.5" />
                          Test Connection
                        </>
                      )}
                    </button>
                    
                    {!model.api_key_set && model.provider !== 'ollama' && (
                      <button
                        onClick={() => setShowApiKeyModal(model.model_id)}
                        className="px-3 py-1.5 bg-amber-100 text-amber-700 rounded text-sm font-medium flex items-center gap-1.5 hover:bg-amber-200 transition"
                      >
                        <Key className="w-3.5 h-3.5" />
                        Set Key
                      </button>
                    )}
                    
                    {!model.is_default && (
                      <button
                        onClick={() => setDefaultModel(model.model_id)}
                        className="px-3 py-1.5 bg-teal-100 text-teal-700 rounded text-sm font-medium flex items-center gap-1.5 hover:bg-teal-200 transition"
                      >
                        <Settings className="w-3.5 h-3.5" />
                        Set Default
                      </button>
                    )}
                  </div>
                  
                  {/* Test Result Message - Always show after test */}
                  {testResult && !testResult.testing && (
                    <div className={`mt-3 p-3 rounded-lg text-sm border ${
                      testResult.success 
                        ? 'bg-green-50 border-green-200 text-green-800' 
                        : 'bg-red-50 border-red-200 text-red-800'
                    }`}>
                      <div className="flex items-start gap-2">
                        {testResult.success ? (
                          <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        )}
                        <div>
                          <div className="font-semibold mb-0.5">
                            {testResult.success ? '✓ Connection Successful' : '✗ Connection Failed'}
                          </div>
                          <div className="text-xs opacity-90">{testResult.message}</div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {config.models.length === 0 && <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed"><Cpu className="w-12 h-12 mx-auto text-gray-400 mb-3" /><h3 className="text-lg font-semibold text-gray-700">No models configured</h3><button onClick={() => setIsAddingModel(true)} className="mt-4 px-4 py-2 bg-teal-500 text-white rounded">Add Model</button></div>}
        </div>
      )}

      {/* Connections Tab */}
      {activeTab === 'connections' && (
                   <>
                     <div className="flex flex-col md:flex-row gap-4">
                       {/* Left panel – Provider Health */}
                       <div className="md:w-1/3">
                         <h3 className="font-semibold mb-2 text-gray-800">Provider Health</h3>
                         {providers.map((provider) => {
                           const modelsForProvider = config.models.filter(m => m.provider === provider.id);
                           const anyTesting = modelsForProvider.some(m => testResults[m.model_id]?.testing);
                           const anyFailed = modelsForProvider.some(m => testResults[m.model_id]?.success === false);
                           const allSuccess = modelsForProvider.length > 0 && modelsForProvider.every(m => testResults[m.model_id]?.success);
                           let statusColor = 'bg-gray-200 text-gray-600';
                           if (anyTesting) {
                             statusColor = 'bg-yellow-100 text-yellow-800';
                           } else if (anyFailed) {
                             statusColor = 'bg-red-100 text-red-800';
                           } else if (allSuccess) {
                             statusColor = 'bg-green-100 text-green-800';
                           }
                           return (
                             <div key={provider.id} className={`border rounded-lg p-4 ${statusColor} hover:shadow-md transition`}> 
                               <div className="flex items-start gap-3 mb-3">
                                 <div className={`p-2 rounded-lg ${provider.color}`}>
                                   {provider.icon}
                                 </div>
                                 <div className="flex-1">
                                   <h3 className="font-bold">{provider.name}</h3>
                                   <p className="text-sm text-gray-600 mt-1">{provider.description}</p>
                                 </div>
                               </div>
                               <div className="text-sm text-gray-600">
                                 <strong>{modelsForProvider.length}</strong> {modelsForProvider.length === 1 ? 'model' : 'models'} configured
                               </div>
                               <div className="mt-2 text-sm font-medium">
                                 Provider health: {anyTesting ? 'Testing...' : anyFailed ? 'Error' : allSuccess ? 'Healthy' : 'Unknown'}
                               </div>
                             </div>
                           );
                         })}
                       </div>
                       {/* Right panel – Model Inventory */}
                       <div className="md:w-2/3">
                         <h3 className="font-semibold mb-2 text-gray-800">Model Inventory</h3>
                         <div className="flex gap-2 mb-4">
                           <input
                             type="text"
                             placeholder="Search models..."
                             value={modelSearch}
                             onChange={(e) => setModelSearch(e.target.value)}
                             className="flex-1 border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500"
                           />
                           <select
                             value={modelProviderFilter}
                             onChange={(e) => setModelProviderFilter(e.target.value)}
                             className="border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500"
                           >
                             <option value="all">All Providers</option>
                             {providers.map(p => (
                               <option key={p.id} value={p.id}>{p.name}</option>
                             ))}
                           </select>
                         </div>
                         <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                           {config.models
                             .filter(m => (modelProviderFilter === 'all' || m.provider === modelProviderFilter))
                             .filter(m => m.name.toLowerCase().includes(modelSearch.toLowerCase()))
                             .map((model) => {
                               const providerInfo = getProviderInfo(model.provider);
                               const testResult = testResults[model.model_id];
                               return (
                                 <div key={model.model_id} className={`border rounded-xl p-5 transition-all hover:shadow-lg ${model.is_default ? 'border-teal-400 bg-teal-50 shadow-md ring-2 ring-teal-100' : 'border-gray-200 bg-white hover:border-teal-300'}`}>
                                   <div className="flex items-center gap-3 mb-4">
                                     <div className={`p-2.5 rounded-lg ${providerInfo.color} shadow-sm`}><div className="text-white">{providerInfo.icon}</div></div>
                                     <div>
                                       <h4 className="font-bold text-gray-800">{model.name}</h4>
                                       <div className="text-xs text-gray-500">{providerInfo.name}</div>
                                       {model.is_default && <span className="inline-block bg-teal-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full mt-1">DEFAULT</span>}
                                     </div>
                                   </div>
                                   <div className="grid grid-cols-2 gap-3 text-xs">
                                     <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Context</div><div className="font-semibold">{model.context_window}</div></div>
                                     <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Max Tokens</div><div className="font-semibold">{model.max_tokens}</div></div>
                                     <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Temperature</div><div className="font-semibold">{model.temperature}</div></div>
                                     <div className="bg-gray-50 p-2 rounded"><div className="text-gray-500">Status</div><div className={`font-semibold ${testResult?.success ? 'text-green-600' : testResult ? 'text-red-600' : model.api_key_set || model.provider === 'ollama' ? 'text-teal-600' : 'text-amber-600'}`}>{testResult?.success ? 'Active' : testResult ? 'Failed' : model.api_key_set || model.provider === 'ollama' ? 'Ready' : 'Needs Key'}</div></div>
                                   </div>
                                   <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-200">
                                     <button
                                       onClick={() => testConnection(model.model_id)}
                                       disabled={testResult?.testing}
                                       className={`px-3 py-1.5 rounded text-sm font-medium flex items-center gap-1.5 transition ${
                                         testResult?.testing 
                                         ? 'bg-gray-200 text-gray-500 cursor-wait' 
                                         : testResult?.success 
                                         ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                                         : testResult && !testResult.success
                                         ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                         : 'bg-teal-100 text-teal-700 hover:bg-teal-200'
                                       }`}
                                     >
                                       {testResult?.testing ? (
                                         <>
                                           <Loader className="w-3.5 h-3.5 animate-spin" />
                                           Testing...
                                         </>
                                       ) : testResult?.success ? (
                                         <>
                                           <CheckCircle className="w-3.5 h-3.5" />
                                           Connected (Test Again)
                                         </>
                                       ) : testResult && !testResult.success ? (
                                         <>
                                           <XCircle className="w-3.5 h-3.5" />
                                           Failed (Retry)
                                         </>
                                       ) : (
                                         <>
                                           <RefreshCw className="w-3.5 h-3.5" />
                                           Test Connection
                                         </>
                                       )}
                                     </button>
                                     {!model.api_key_set && model.provider !== 'ollama' && (
                                       <button
                                         onClick={() => setShowApiKeyModal(model.model_id)}
                                         className="px-3 py-1.5 bg-amber-100 text-amber-700 rounded text-sm font-medium flex items-center gap-1.5 hover:bg-amber-200 transition"
                                       >
                                         <Key className="w-3.5 h-3.5" />
                                         Set Key
                                       </button>
                                     )}
                                     {!model.is_default && (
                                       <button
                                         onClick={() => setDefaultModel(model.model_id)}
                                         className="px-3 py-1.5 bg-teal-100 text-teal-700 rounded text-sm font-medium flex items-center gap-1.5 hover:bg-teal-200 transition"
                                       >
                                         <Settings className="w-3.5 h-3.5" />
                                         Set Default
                                       </button>
                                     )}
                                     {/* Kebab menu placeholder */}
                                     <button className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-sm font-medium flex items-center gap-1.5 hover:bg-gray-200 transition">⋮</button>
                                   </div>
                                 </div>
                               );
                             })}
                         </div>
                       </div>
                     </div>
                     {/* Settings moved into Connections */}
                     <div className="bg-white border rounded-lg p-6 max-w-2xl mt-6">
                       <h3 className="text-lg font-bold mb-4">Connection Settings</h3>
                       <div className="space-y-4">
                         <div>
                           <label className="block text-sm font-medium text-gray-700 mb-1">Request Timeout (seconds)</label>
                           <input type="number" defaultValue={config.connection_settings.timeout_seconds} min="5" max="300" className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500" />
                         </div>
                         <div>
                           <label className="block text-sm font-medium text-gray-700 mb-1">Maximum Retries</label>
                           <input type="number" defaultValue={config.connection_settings.max_retries} min="0" max="10" className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500" />
                         </div>
                         <div className="flex items-center gap-3">
                           <input type="checkbox" id="fallback" defaultChecked={config.connection_settings.enable_fallback} className="w-4 h-4 text-teal-600" />
                           <label htmlFor="fallback" className="text-sm">Enable fallback to other providers on failure</label>
                         </div>
                         <div className="flex items-center gap-3">
                           <input type="checkbox" id="caching" defaultChecked={config.connection_settings.enable_caching} className="w-4 h-4 text-teal-600" />
                           <label htmlFor="caching" className="text-sm">Enable response caching (improves performance)</label>
                         </div>
                       </div>
                       <div className="mt-6 pt-6 border-t">
                         <button className="px-6 py-2 bg-teal-500 text-white rounded hover:bg-teal-600 transition">Save Settings</button>
                         <p className="text-xs text-gray-500 mt-2">Changes will apply to all future AI operations</p>
                       </div>
                     </div>
                   </>
                 )}
{/* Providers Tab */}
      {activeTab === 'providers' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {providers.map((provider) => {
            const modelCount = config.models.filter(m => m.provider === provider.id).length;
            const hasApiKey = config.models.some(m => m.provider === provider.id && m.api_key_set);
            
            return (
              <div key={provider.id} className="border rounded-lg p-4 hover:shadow-md transition">
                <div className="flex items-start gap-3 mb-3">
                  <div className={`p-2 rounded-lg ${provider.color}`}>
                    {provider.icon}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold">{provider.name}</h3>
                    <p className="text-sm text-gray-600 mt-1">{provider.description}</p>
                  </div>
                  {provider.requires_api_key && (
                    <div className={`px-2 py-1 rounded text-xs ${
                      hasApiKey ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {hasApiKey ? 'Configured' : 'Key Required'}
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 mb-4">
                  {provider.features.map((feature) => (
                    <span
                      key={feature}
                      className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded capitalize"
                    >
                      {feature}
                    </span>
                  ))}
                </div>

                <div className="text-sm text-gray-600">
                  <strong>{modelCount}</strong> {modelCount === 1 ? 'model' : 'models'} configured
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Settings Tab */}
      
      {/* Logs Tab */}
      {activeTab === 'logs' && (
          <div className="p-4">
            <h3 className="text-lg font-bold mb-2">Logs</h3>
            <p className="text-sm text-gray-600">Coming soon</p>
          </div>
        )}
      {showApiKeyModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-bold mb-4">
              Set API Key for {config?.models.find(m => m.model_id === showApiKeyModal)?.name}
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              Enter your API key for {getProviderInfo(config?.models.find(m => m.model_id === showApiKeyModal)?.provider || '').name}
            </p>
            
            <input
              type="password"
              placeholder="••••••••••••••••"
              className="w-full border rounded px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-teal-500"
              value={apiKeys[showApiKeyModal] || ''}
              onChange={(e) => setApiKeys({ ...apiKeys, [showApiKeyModal]: e.target.value })}
            />

            <div className="flex gap-3">
              <button
                onClick={() => setShowApiKeyModal(null)}
                className="flex-1 px-4 py-2 border rounded hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => saveApiKey(showApiKeyModal)}
                className="flex-1 px-4 py-2 bg-teal-500 text-white rounded hover:bg-teal-600 transition"
              >
                Save Key
              </button>
            </div>

            <div className="mt-4 text-xs text-gray-500">
              <p className="font-medium mb-1">Environment Variable:</p>
              <code className="bg-gray-100 px-2 py-1 rounded">
                {showApiKeyModal === 'llama3.1' ? 'OLLAMA_API_KEY' : 
                 showApiKeyModal.includes('nvidia') ? 'NVIDIA_API_KEY' :
                 showApiKeyModal.includes('google') ? 'GOOGLE_API_KEY' :
                 'IBM_BOB_API_KEY'}
              </code>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIEngineSettings;