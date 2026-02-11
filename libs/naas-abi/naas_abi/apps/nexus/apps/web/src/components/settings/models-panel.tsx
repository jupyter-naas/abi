'use client';

import { useState, useEffect } from 'react';
import {
  Server,
  Cloud,
  RefreshCw,
  Check,
  X,
  Loader2,
  Plus,
  Pencil,
  Trash2,
  AlertCircle,
  CheckCircle,
  Search,
  Cpu,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { getApiUrl, getOllamaUrl } from '@/lib/config';

const API_BASE = getApiUrl();

type ModelInfo = {
  id: string;
  name: string;
  provider: string;
  context_window: number;
  supports_streaming: boolean;
  supports_vision: boolean;
  supports_function_calling: boolean;
  max_output_tokens: number | null;
  released: string;
};

type Provider = {
  id: string;
  name: string;
  type: string;
  has_api_key: boolean;
  logo_url?: string | null;
  models: ModelInfo[];
};

type Model = {
  id: string;
  name: string;
  provider: string;
  model: string;
  credentials: string;
  status: 'enabled' | 'disabled';
  configured: boolean;
  // Registry metadata
  context_window?: number;
  supports_streaming?: boolean;
  supports_vision?: boolean;
  supports_function_calling?: boolean;
  max_output_tokens?: number | null;
};

const providerIcons: Record<string, React.ReactNode> = {
  anthropic: <Cloud size={18} />,
  openai: <Cloud size={18} />,
  cloudflare: <Cloud size={18} />,
  xai: <Cloud size={18} />,
  mistral: <Cloud size={18} />,
  perplexity: <Cloud size={18} />,
  google: <Cloud size={18} />,
  openrouter: <Cloud size={18} />,
  ollama: <Server size={18} />,
};

export function ModelsPanel() {
  const [mounted, setMounted] = useState(false);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [showAddModel, setShowAddModel] = useState(false);

  // New model form
  const [newModel, setNewModel] = useState({
    provider: '',
    model: '',
  });

  useEffect(() => {
    setMounted(true);
    fetchProviders();
  }, []);

  const fetchProviders = async (fetchLive = false) => {
    try {
      const response = await authFetch(`${API_BASE}/api/providers/available`);
      if (response.ok) {
        const data = await response.json();
        setProviders(data);
        
        // Generate models from providers (using registry data)
        const generatedModels: Model[] = [];
        for (const provider of data) {
          for (const modelInfo of provider.models) {
            generatedModels.push({
              id: `${provider.id}-${modelInfo.id}`,
              name: modelInfo.name,
              provider: provider.name,
              model: modelInfo.id,
              credentials: provider.has_api_key
                ? `${provider.type.toUpperCase()}_API_KEY`
                : 'Not required',
              status: provider.has_api_key ? 'enabled' : 'disabled',
              configured: provider.has_api_key,
              // Registry metadata
              context_window: modelInfo.context_window,
              supports_streaming: modelInfo.supports_streaming,
              supports_vision: modelInfo.supports_vision,
              supports_function_calling: modelInfo.supports_function_calling,
              max_output_tokens: modelInfo.max_output_tokens,
            });
          }
        }
        setModels(generatedModels);
        // Also refresh the integrations store to avoid drift in other parts of the UI
        const { refreshProviders } = await import('@/stores/integrations');
        try { (refreshProviders as any)?.(); } catch {}
      }
    } catch (error) {
      console.error('Failed to fetch providers:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncModels = async () => {
    setSyncing(true);
    await fetchProviders();
    setSyncing(false);
  };

  const toggleModel = (modelId: string) => {
    setModels(models.map(m => 
      m.id === modelId 
        ? { ...m, status: m.status === 'enabled' ? 'disabled' : 'enabled' }
        : m
    ));
  };

  const handleAddModel = () => {
    if (!newModel.provider || !newModel.model.trim()) return;
    
    const provider = providers.find(p => p.id === newModel.provider);
    if (!provider) return;

    const newModelEntry: Model = {
      id: `${provider.id}-${newModel.model}`,
      name: `${provider.name} - ${newModel.model}`,
      provider: provider.name,
      model: newModel.model.trim(),
      credentials: provider.has_api_key
        ? `${provider.type.toUpperCase()}_API_KEY`
        : 'Not required',
      status: provider.has_api_key ? 'enabled' : 'disabled',
      configured: provider.has_api_key,
    };

    setModels([...models, newModelEntry]);
    setNewModel({ provider: '', model: '' });
    setShowAddModel(false);
  };

  // Filter models based on search query
  const filteredModels = searchQuery.trim()
    ? models.filter(
        (model) =>
          model.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          model.provider.toLowerCase().includes(searchQuery.toLowerCase()) ||
          model.model.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : models;

  if (!mounted || loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading models...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Models</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {filteredModels.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            AI models from connected providers
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncModels}
            disabled={syncing}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
          >
            {syncing ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <RefreshCw size={16} />
            )}
            Sync Models
          </button>
          <button
            onClick={() => setShowAddModel(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Model
          </button>
        </div>
      </div>

      {/* Add Model Form */}
      {showAddModel && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <h3 className="mb-4 font-medium">Add Custom Model</h3>
          <div className="grid gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Provider *</label>
              <select
                value={newModel.provider}
                onChange={(e) => setNewModel({ ...newModel, provider: e.target.value })}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">Select a provider...</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name} {provider.has_api_key ? '✓' : '(no API key)'}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Model Name *</label>
              <input
                type="text"
                value={newModel.model}
                onChange={(e) => setNewModel({ ...newModel, model: e.target.value })}
                placeholder="e.g., gpt-4o, claude-3-5-sonnet-20241022"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/30"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Enter the exact model identifier from the provider's documentation
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowAddModel(false);
                  setNewModel({ provider: '', model: '' });
                }}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleAddModel}
                disabled={!newModel.provider || !newModel.model.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Add Model
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Models List */}
      {models.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <Cloud size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No models available</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Configure API keys in Secrets to enable cloud provider models
          </p>
          <button
            onClick={handleSyncModels}
            disabled={syncing}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
          >
            {syncing ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <RefreshCw size={16} />
            )}
            Sync Models
          </button>
        </div>
      ) : (
        <div>
          {/* Search */}
          {models.length > 0 && (
            <div className="mb-4 relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search models..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border bg-background pl-10 pr-10 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          )}

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm">
                  <th className="p-3 font-medium">Model</th>
                  <th className="p-3 font-medium">Provider</th>
                  <th className="p-3 font-medium">Capabilities</th>
                  <th className="p-3 font-medium">Credentials</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 w-32"></th>
                </tr>
              </thead>
              <tbody>
                {filteredModels.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">
                      {searchQuery ? `No models match "${searchQuery}"` : 'No models available'}
                    </td>
                  </tr>
                ) : (
                  filteredModels.map((model) => (
                    <tr key={model.id} className="border-b last:border-0">
                      <td className="p-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg bg-muted">
                            {(() => {
                              const p = providers.find(p => p.name === model.provider);
                              const url = p?.logo_url as string | undefined;
                              return url ? (
                                // Use API base for relative /logos/* paths
                                <img src={url.startsWith('http') ? url : `${API_BASE}${url}`} alt={model.provider} className="h-full w-full object-cover" />
                              ) : (
                                providerIcons[model.provider.toLowerCase()] || <Cloud size={18} />
                              );
                            })()}
                          </div>
                          <div>
                            <p className="font-medium">{model.name}</p>
                            <code className="text-xs text-muted-foreground font-mono">{model.model}</code>
                          </div>
                        </div>
                      </td>
                      <td className="p-3 text-sm">{model.provider}</td>
                      <td className="p-3">
                        <div className="flex flex-wrap gap-1">
                          {model.supports_streaming && (
                            <span className="inline-flex rounded bg-blue-100 dark:bg-blue-950 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:text-blue-300">
                              Stream
                            </span>
                          )}
                          {model.supports_vision && (
                            <span className="inline-flex rounded bg-purple-100 dark:bg-purple-950 px-1.5 py-0.5 text-[10px] font-medium text-purple-700 dark:text-purple-300">
                              Vision
                            </span>
                          )}
                          {model.supports_function_calling && (
                            <span className="inline-flex rounded bg-green-100 dark:bg-green-950 px-1.5 py-0.5 text-[10px] font-medium text-green-700 dark:text-green-300">
                              Functions
                            </span>
                          )}
                          {model.context_window && model.context_window >= 100000 && (
                            <span className="inline-flex rounded bg-amber-100 dark:bg-amber-950 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                              {(model.context_window / 1000).toFixed(0)}K
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-3">
                        {model.configured ? (
                          <div className="flex items-center gap-2 text-sm">
                            <CheckCircle size={14} className="text-green-500" />
                            <span className="text-muted-foreground">{model.credentials}</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 text-sm text-red-500">
                            <XCircle size={14} />
                            <span>Not configured</span>
                          </div>
                        )}
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => toggleModel(model.id)}
                          disabled={!model.configured}
                          className={cn(
                            'flex h-6 w-11 items-center rounded-full p-0.5 transition-colors',
                            model.status === 'enabled'
                              ? 'bg-primary'
                              : 'bg-muted-foreground/30',
                            !model.configured && 'cursor-not-allowed opacity-50'
                          )}
                        >
                          <div
                            className={cn(
                              'h-5 w-5 rounded-full bg-white shadow-sm transition-transform',
                              model.status === 'enabled' && 'translate-x-5'
                            )}
                          />
                        </button>
                      </td>
                      <td className="p-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            className="rounded p-1.5 hover:bg-muted"
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            className="rounded p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
        <AlertCircle size={20} className="mt-0.5 flex-shrink-0 text-blue-600 dark:text-blue-500" />
        <div className="text-sm">
          <p className="font-medium text-blue-800 dark:text-blue-200">
            Models from centralized registry
          </p>
          <p className="text-blue-700 dark:text-blue-300">
            Add API keys in <strong>Settings → Secrets</strong> to enable providers. The registry is updated regularly with the latest models. Click "Sync Models" to refresh.
          </p>
        </div>
      </div>
    </div>
  );
}
