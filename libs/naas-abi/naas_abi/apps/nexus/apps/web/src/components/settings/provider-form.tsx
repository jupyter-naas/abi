'use client';

import { useState, useEffect } from 'react';
import { Check, X, RefreshCw, Key } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getOllamaUrl } from '@/lib/config';
import {
  useIntegrationsStore,
  type ProviderConfig,
  type ProviderType,
} from '@/stores/integrations';
import { useSecretsStore } from '@/stores/secrets';

interface ProviderFormProps {
  provider?: ProviderConfig;
  onSave: () => void;
  onCancel: () => void;
}

const providerTypes: { value: ProviderType; label: string; needsEndpoint: boolean; needsApiKey: boolean; needsAccountId: boolean }[] = [
  { value: 'openrouter', label: 'OpenRouter (400+ models)', needsEndpoint: false, needsApiKey: true, needsAccountId: false },
  { value: 'anthropic', label: 'Anthropic (Claude)', needsEndpoint: false, needsApiKey: true, needsAccountId: false },
  { value: 'openai', label: 'OpenAI', needsEndpoint: false, needsApiKey: true, needsAccountId: false },
  { value: 'cloudflare', label: 'Cloudflare Workers AI', needsEndpoint: false, needsApiKey: true, needsAccountId: true },
  { value: 'ollama', label: 'Ollama (Local)', needsEndpoint: true, needsApiKey: false, needsAccountId: false },
  { value: 'custom', label: 'Custom (OpenAI-compatible)', needsEndpoint: true, needsApiKey: true, needsAccountId: false },
];

const defaultModels: Record<ProviderType, string[]> = {
  openrouter: ['anthropic/claude-opus-4.6', 'anthropic/claude-sonnet-4.6', 'openai/gpt-5.2-codex', 'moonshotai/kimi-k2.5', 'qwen/qwen3-coder-next'],
  anthropic: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3-5-haiku-20241022'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o1-mini'],
  cloudflare: [
    '@cf/meta/llama-3.1-8b-instruct',
    '@cf/meta/llama-3.1-70b-instruct',
    '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
    '@cf/meta/llama-3.2-3b-instruct',
    '@cf/qwen/qwen3-30b-a3b-fp8',
    '@cf/qwen/qwq-32b',
    '@cf/google/gemma-3-12b-it',
    '@cf/mistral/mistral-small-3.1-24b-instruct',
    '@cf/deepseek/deepseek-r1-distill-qwen-32b',
  ],
  ollama: [], // Will be fetched dynamically
  custom: [],
};

export function ProviderForm({ provider, onSave, onCancel }: ProviderFormProps) {
  const { addProvider, updateProvider } = useIntegrationsStore();
  const { secrets } = useSecretsStore();
  const isEditing = !!provider;

  const [name, setName] = useState(provider?.name || '');
  const [type, setType] = useState<ProviderType>(provider?.type || 'anthropic');
  const [endpoint, setEndpoint] = useState(provider?.endpoint || getOllamaUrl());
  const [apiKeySecretKey, setApiKeySecretKey] = useState(provider?.apiKeySecretKey || '');
  const [accountIdSecretKey, setAccountIdSecretKey] = useState(provider?.accountIdSecretKey || '');
  const [model, setModel] = useState(provider?.model || '');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const typeConfig = providerTypes.find((t) => t.value === type);
  
  // Filter secrets for API keys and account IDs
  const apiKeySecrets = secrets.filter(s => 
    s.category === 'api_keys' || s.key.toUpperCase().includes('API') || s.key.toUpperCase().includes('TOKEN')
  );
  const accountIdSecrets = secrets.filter(s => 
    s.key.toUpperCase().includes('ACCOUNT') || s.key.toUpperCase().includes('ID') || s.category === 'other'
  );

  // Fetch Ollama models when type is ollama
  useEffect(() => {
    if (type === 'ollama') {
      fetchOllamaModels();
    }
  }, [type, endpoint]);

  const fetchOllamaModels = async () => {
    setLoadingModels(true);
    try {
      const response = await fetch(`${endpoint}/api/tags`);
      if (response.ok) {
        const data = await response.json();
        const models = data.models?.map((m: any) => m.name) || [];
        setOllamaModels(models);
        if (models.length > 0 && !model) {
          setModel(models[0]);
        }
      }
    } catch {
      setOllamaModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  const getModelsForType = () => {
    if (type === 'ollama') {
      return ollamaModels;
    }
    return defaultModels[type];
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const data = {
      name: name || `${typeConfig?.label} Provider`,
      type,
      enabled: provider?.enabled ?? false,
      endpoint: typeConfig?.needsEndpoint ? endpoint : undefined,
      apiKeySecretKey: typeConfig?.needsApiKey ? apiKeySecretKey : undefined,
      accountIdSecretKey: typeConfig?.needsAccountId ? accountIdSecretKey : undefined,
      // Clear legacy fields when using secrets
      apiKey: undefined,
      accountId: undefined,
      model: model || defaultModels[type][0] || '',
    };

    if (isEditing) {
      updateProvider(provider.id, data);
    } else {
      addProvider(data);
    }

    onSave();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Name */}
        <div>
          <label className="mb-1.5 block text-sm font-medium">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Claude Provider"
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {/* Type */}
        <div>
          <label className="mb-1.5 block text-sm font-medium">Provider Type</label>
          <select
            value={type}
            onChange={(e) => {
              setType(e.target.value as ProviderType);
              setModel(defaultModels[e.target.value as ProviderType][0] || '');
            }}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          >
            {providerTypes.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Endpoint (for Ollama/Custom) */}
        {typeConfig?.needsEndpoint && (
          <div>
            <label className="mb-1.5 block text-sm font-medium">Endpoint URL</label>
            <input
              type="url"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        )}

        {/* API Key Secret (for cloud-hosted models) */}
        {typeConfig?.needsApiKey && (
          <div>
            <label className="mb-1.5 block text-sm font-medium">API Key</label>
            <div className="relative">
              <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <select
                value={apiKeySecretKey}
                onChange={(e) => setApiKeySecretKey(e.target.value)}
                className="w-full rounded-lg border bg-background pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">Select a secret...</option>
                {apiKeySecrets.map((s) => (
                  <option key={s.id} value={s.key}>
                    {s.key}
                  </option>
                ))}
              </select>
            </div>
            {apiKeySecrets.length === 0 && (
              <p className="mt-1 text-xs text-amber-500">
                No API key secrets found. Add one in Settings → Secrets first.
              </p>
            )}
          </div>
        )}

        {/* Account ID Secret (for Cloudflare) */}
        {typeConfig?.needsAccountId && (
          <div>
            <label className="mb-1.5 block text-sm font-medium">Account ID</label>
            <div className="relative">
              <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <select
                value={accountIdSecretKey}
                onChange={(e) => setAccountIdSecretKey(e.target.value)}
                className="w-full rounded-lg border bg-background pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">Select a secret...</option>
                {accountIdSecrets.map((s) => (
                  <option key={s.id} value={s.key}>
                    {s.key}
                  </option>
                ))}
              </select>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Add CLOUDFLARE_ACCOUNT_ID in Settings → Secrets
            </p>
          </div>
        )}

        {/* Model */}
        <div className={cn(!typeConfig?.needsEndpoint && !typeConfig?.needsApiKey && 'sm:col-span-2')}>
          <label className="mb-1.5 block text-sm font-medium">Model</label>
          <div className="flex gap-2">
            {getModelsForType().length > 0 ? (
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              >
                {getModelsForType().map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={type === 'ollama' ? 'No models found - run ollama pull <model>' : 'model-name'}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            )}
            {type === 'ollama' && (
              <button
                type="button"
                onClick={fetchOllamaModels}
                disabled={loadingModels}
                className="flex items-center justify-center rounded-lg border bg-background px-3 hover:bg-secondary"
              >
                <RefreshCw size={14} className={loadingModels ? 'animate-spin' : ''} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary"
        >
          <X size={16} />
          Cancel
        </button>
        <button
          type="submit"
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Check size={16} />
          {isEditing ? 'Save Changes' : 'Add Provider'}
        </button>
      </div>
    </form>
  );
}
