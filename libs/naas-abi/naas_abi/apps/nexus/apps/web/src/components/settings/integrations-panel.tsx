'use client';

import { useState, useEffect } from 'react';
import {
  Plus,
  Pencil,
  Trash2,
  Check,
  X,
  ExternalLink,
  Server,
  Cloud,
  Code,
  ToggleLeft,
  ToggleRight,
  FileCode,
  RefreshCw,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useIntegrationsStore,
  type ProviderConfig,
  type ProviderType,
} from '@/stores/integrations';
import { useSecretsStore } from '@/stores/secrets';
import { ProviderForm } from './provider-form';
import { YamlEditor } from './yaml-editor';

const providerIcons: Record<string, React.ReactNode> = {
  anthropic: <Cloud size={18} />,
  openai: <Cloud size={18} />,
  openrouter: <Cloud size={18} />,
  xai: <Cloud size={18} />,
  mistral: <Cloud size={18} />,
  google: <Cloud size={18} />,
  perplexity: <Cloud size={18} />,
  cloudflare: <Cloud size={18} />,
  ollama: <Server size={18} />,
  custom: <Code size={18} />,
};

const providerLabels: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  xai: 'xAI (Grok)',
  mistral: 'Mistral',
  google: 'Google',
  perplexity: 'Perplexity',
  cloudflare: 'Cloudflare',
  ollama: 'Ollama',
  custom: 'Custom',
};

import { getOllamaUrl } from '@/lib/config';

export function IntegrationsPanel() {
  const { providers, toggleProvider, deleteProvider, updateProvider, addProvider, syncOllamaProviders } = useIntegrationsStore();
  const { secrets } = useSecretsStore();
  const [mounted, setMounted] = useState(false);
  
  // Helper to check if provider has credentials configured
  const hasCredentials = (provider: ProviderConfig) => {
    if (provider.type === 'ollama') return true; // Doesn't need credentials
    if (provider.apiKeySecretKey) {
      const secret = secrets.find(s => s.key === provider.apiKeySecretKey);
      return !!secret; // Secret exists means it has a value (server-side encrypted)
    }
    return !!provider.apiKey; // Legacy fallback
  };
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'yaml'>('table');

  useEffect(() => {
    setMounted(true);
  }, []);

  const resetConfig = () => {
    if (confirm('Reset all model and agent configurations to defaults?')) {
      localStorage.removeItem('nexus-integrations');
      localStorage.removeItem('nexus-agents');
      window.location.reload();
    }
  };

  const handleEdit = (id: string) => {
    setEditingId(id);
    setShowAddForm(false);
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this model?')) {
      deleteProvider(id);
    }
  };

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Models</h2>
            <p className="text-sm text-muted-foreground">
              Loading...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Models</h2>
          <p className="text-sm text-muted-foreground">
            Configure AI models and endpoints for your agents
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex rounded-lg border bg-card p-1">
            <button
              onClick={() => setViewMode('table')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                viewMode === 'table' ? 'bg-secondary' : 'hover:bg-secondary/50'
              )}
            >
              Table
            </button>
            <button
              onClick={() => setViewMode('yaml')}
              className={cn(
                'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                viewMode === 'yaml' ? 'bg-secondary' : 'hover:bg-secondary/50'
              )}
            >
              <FileCode size={14} />
              YAML
            </button>
          </div>
          {viewMode === 'table' && (
            <>
              <button
                onClick={resetConfig}
                className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm text-muted-foreground hover:bg-secondary"
              >
                Reset
              </button>
              <button
                onClick={() => {
                  setShowAddForm(true);
                  setEditingId(null);
                }}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Plus size={16} />
                Add Model
              </button>
            </>
          )}
        </div>
      </div>

      {viewMode === 'yaml' ? (
        <YamlEditor />
      ) : (
        <>
          {/* Add form */}
          {showAddForm && (
            <div className="rounded-xl border bg-card p-4">
              <h3 className="mb-4 font-medium">Add New Model</h3>
              <ProviderForm
                onSave={() => setShowAddForm(false)}
                onCancel={() => setShowAddForm(false)}
              />
            </div>
          )}

          {/* Models table */}
          <div className="overflow-x-auto rounded-xl border bg-card">
            <table className="w-full min-w-[800px]">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="p-4 font-medium">Name</th>
                  <th className="p-4 font-medium w-24">Provider</th>
                  <th className="p-4 font-medium">Model</th>
                  <th className="p-4 font-medium">Credentials</th>
                  <th className="p-4 font-medium w-28">Status</th>
                  <th className="p-4 font-medium w-24 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((provider) => (
                  <tr key={provider.id} className="border-b last:border-0">
                    {editingId === provider.id ? (
                      <td colSpan={6} className="p-4">
                        <ProviderForm
                          provider={provider}
                          onSave={() => setEditingId(null)}
                          onCancel={() => setEditingId(null)}
                        />
                      </td>
                    ) : (
                      <>
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
                              {providerIcons[provider.type]}
                            </div>
                            <span className="font-medium">{provider.name}</span>
                          </div>
                        </td>
                        <td className="p-4 text-sm text-muted-foreground">
                          {providerLabels[provider.type]}
                        </td>
                        <td className="p-4">
                          <code className="rounded bg-secondary px-2 py-1 text-xs">
                            {provider.model}
                          </code>
                        </td>
                        <td className="p-4 text-sm">
                          {provider.type === 'ollama' ? (
                            <span className="text-muted-foreground">{provider.endpoint || getOllamaUrl()}</span>
                          ) : provider.apiKeySecretKey ? (
                            <span className="flex items-center gap-1 text-primary">
                              <CheckCircle size={12} />
                              {provider.apiKeySecretKey}
                            </span>
                          ) : provider.apiKey ? (
                            <span className="flex items-center gap-1 text-amber-500">
                              <CheckCircle size={12} />
                              Legacy key
                            </span>
                          ) : (
                            <span className="text-destructive">Not configured</span>
                          )}
                        </td>
                        <td className="p-4">
                          <button
                            onClick={() => toggleProvider(provider.id)}
                            className={cn(
                              'flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium transition-colors',
                              provider.enabled
                                ? 'bg-primary/10 text-primary'
                                : 'bg-secondary text-muted-foreground'
                            )}
                          >
                            {provider.enabled ? (
                              <>
                                <ToggleRight size={14} />
                                Enabled
                              </>
                            ) : (
                              <>
                                <ToggleLeft size={14} />
                                Disabled
                              </>
                            )}
                          </button>
                        </td>
                        <td className="p-4">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => handleEdit(provider.id)}
                              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground"
                              title="Edit"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => handleDelete(provider.id)}
                              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Hint to configure agent mappings */}
          <div className="rounded-xl border bg-card/50 p-4 text-center">
            <p className="text-sm text-muted-foreground">
              To assign models to agents, go to{' '}
              <a href="settings/agents" className="text-primary hover:underline font-medium">
                Settings → Agents
              </a>
            </p>
          </div>
        </>
      )}
    </div>
  );
}
