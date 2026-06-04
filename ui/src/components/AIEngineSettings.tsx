import React, { useState, useEffect } from 'react';

interface ModelConfig {
  model_id: string;
  name: string;
  provider: string;
  is_default: boolean;
  api_key_set: boolean;
  endpoint: string | null;
  context_window: number;
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

const AIEngineSettings: React.FC = () => {
  const [config, setConfig] = useState<AIConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'models' | 'providers' | 'settings'>('models');
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [newApiKey, setNewApiKey] = useState<string>('');
  const [showApiKeyInput, setShowApiKeyInput] = useState(false);

  // Fetch config
  useEffect(() => {
    fetch('/api/ai-engine/config')
      .then((res) => res.json())
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const testConnection = async (modelId: string) => {
    setTestResult(null);
    try {
      const res = await fetch('/api/ai-engine/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId })
      });
      const data = await res.json();
      if (res.ok) {
        setTestResult({ success: true, message: data.message });
      } else {
        setTestResult({ success: false, message: data.detail.message || 'Connection failed' });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message });
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
        // Refresh config
        const configRes = await fetch('/api/ai-engine/config');
        const data = await configRes.json();
        setConfig(data);
      }
    } catch (err: any) {
      alert('Failed to set default model: ' + err.message);
    }
  };

  const saveApiKey = async (modelId: string) => {
    try {
      const res = await fetch('/api/ai-engine/set-api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId, api_key: newApiKey })
      });
      if (res.ok) {
        setShowApiKeyInput(false);
        setNewApiKey('');
        // Refresh config
        const configRes = await fetch('/api/ai-engine/config');
        const data = await configRes.json();
        setConfig(data);
      }
    } catch (err: any) {
      alert('Failed to save API key: ' + err.message);
    }
  };

  if (loading) return <div className="p-4">Loading AI Engine configuration...</div>;
  if (error) return <div className="p-4 text-red-600">Error: {error}</div>;
  if (!config) return <div className="p-4">No configuration found</div>;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h2 className="text-2xl font-bold mb-6">AI Engine Settings</h2>
      
      {/* Tabs */}
      <div className="flex border-b mb-6">
        <button
          className={`px-4 py-2 ${activeTab === 'models' ? 'border-b-2 border-blue-500 font-bold' : ''}`}
          onClick={() => setActiveTab('models')}
        >
          Models ({config.models.length})
        </button>
        <button
          className={`px-4 py-2 ${activeTab === 'providers' ? 'border-b-2 border-blue-500 font-bold' : ''}`}
          onClick={() => setActiveTab('providers')}
        >
          Providers
        </button>
        <button
          className={`px-4 py-2 ${activeTab === 'settings' ? 'border-b-2 border-blue-500 font-bold' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          Connection Settings
        </button>
      </div>

      {/* Models Tab */}
      {activeTab === 'models' && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Configured Models</h3>
          <div className="grid gap-4">
            {config.models.map((model) => (
              <div
                key={model.model_id}
                className={`border rounded-lg p-4 ${model.is_default ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-lg">{model.name}</h4>
                      {model.is_default && (
                        <span className="bg-blue-500 text-white text-xs px-2 py-1 rounded">DEFAULT</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      Provider: {model.provider.toUpperCase()}
                    </p>
                    <p className="text-sm text-gray-600">
                      Context: {model.context_window} tokens
                    </p>
                    {model.endpoint && (
                      <p className="text-sm text-gray-500 truncate mt-1">
                        {model.endpoint}
                      </p>
                    )}
                  </div>
                  
                  <div className="flex gap-2">
                    {!model.api_key_set && model.provider !== 'ollama' && (
                      <button
                        className="bg-yellow-500 text-white px-3 py-1 rounded text-sm"
                        onClick={() => {
                          setSelectedModel(model.model_id);
                          setShowApiKeyInput(true);
                        }}
                      >
                        Set API Key
                      </button>
                    )}
                    <button
                      className="bg-green-500 text-white px-3 py-1 rounded text-sm"
                      onClick={() => testConnection(model.model_id)}
                    >
                      Test Connection
                    </button>
                    {!model.is_default && (
                      <button
                        className="bg-blue-500 text-white px-3 py-1 rounded text-sm"
                        onClick={() => setDefaultModel(model.model_id)}
                      >
                        Set Default
                      </button>
                    )}
                  </div>
                </div>
                
                {/* API Key Input */}
                {showApiKeyInput && selectedModel === model.model_id && (
                  <div className="mt-3">
                    <input
                      type="password"
                      placeholder="Enter API key"
                      className="border rounded px-3 py-2 mr-2"
                      value={newApiKey}
                      onChange={(e) => setNewApiKey(e.target.value)}
                    />
                    <button
                      className="bg-green-500 text-white px-3 py-2 rounded"
                      onClick={() => saveApiKey(model.model_id)}
                    >
                      Save
                    </button>
                    <button
                      className="ml-2 text-gray-600"
                      onClick={() => {
                        setShowApiKeyInput(false);
                        setNewApiKey('');
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                )}
                
                {/* Test Result */}
                {testResult && (
                  <div className={`mt-3 p-2 rounded ${testResult.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {testResult.message}
                  </div>
                )}
              </div>
            ))}
          </div>
          
          <div className="mt-6">
            <h4 className="font-semibold mb-2">Quick Start</h4>
            <div className="bg-gray-100 p-4 rounded text-sm">
              <p className="mb-2"><strong>Ollama (Local):</strong> No API key required. Ensure Ollama is running on localhost:11434</p>
              <p className="mb-2"><strong>NVIDIA NIM:</strong> Set NVIDIA_API_KEY environment variable</p>
              <p className="mb-2"><strong>Google Gemma:</strong> Set GOOGLE_API_KEY environment variable</p>
              <p><strong>IBM Bob:</strong> Set IBM_BOB_API_KEY environment variable</p>
            </div>
          </div>
        </div>
      )}

      {/* Providers Tab */}
      {activeTab === 'providers' && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Supported AI Providers</h3>
          <div className="grid gap-4">
            {[
              { id: 'ollama', name: 'Ollama', desc: 'Local LLM server', local: true },
              { id: 'nvidia_nim', name: 'NVIDIA NIM', desc: 'NVIDIA Inference Microservices', cloud: true },
              { id: 'google_gemma', name: 'Google Gemma', desc: 'Google Gemma models', cloud: true },
              { id: 'ibm_bob', name: 'IBM Bob', desc: 'IBM Bob AI platform', cloud: true },
              { id: 'openai', name: 'OpenAI', desc: 'GPT models', cloud: true },
              { id: 'anthropic', name: 'Anthropic', desc: 'Claude models', cloud: true },
            ].map((provider) => (
              <div key={provider.id} className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-bold">{provider.name}</h4>
                  {provider.local && (
                    <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">LOCAL</span>
                  )}
                  {provider.cloud && (
                    <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">CLOUD</span>
                  )}
                </div>
                <p className="text-sm text-gray-600">{provider.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Connection Settings</h3>
          <div className="grid gap-4 max-w-md">
            <div>
              <label className="block text-sm font-medium mb-1">Timeout (seconds)</label>
              <input
                type="number"
                className="border rounded px-3 py-2 w-full"
                defaultValue={config.connection_settings.timeout_seconds}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Max Retries</label>
              <input
                type="number"
                className="border rounded px-3 py-2 w-full"
                defaultValue={config.connection_settings.max_retries}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="fallback"
                defaultChecked={config.connection_settings.enable_fallback}
                className="h-4 w-4"
              />
              <label htmlFor="fallback">Enable fallback to other providers</label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="caching"
                defaultChecked={config.connection_settings.enable_caching}
                className="h-4 w-4"
              />
              <label htmlFor="caching">Enable response caching</label>
            </div>
          </div>
          
          <button className="mt-4 bg-blue-500 text-white px-4 py-2 rounded">
            Save Settings
          </button>
        </div>
      )}
    </div>
  );
};

export default AIEngineSettings;