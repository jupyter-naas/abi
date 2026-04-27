'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Bot, CheckCircle, Save, XCircle } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';

type ServiceIntent = {
  intent_value: string;
  intent_type: string;
  intent_target: string;
  intent_scope?: string;
};

type ServiceSuggestion = {
  label: string;
  value: string;
};

type ServiceAgent = {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  enabled: boolean;
  class_name?: string | null;
  system_prompt?: string | null;
  model_id?: string | null;
  provider?: string | null;
  logo_url?: string | null;
  created_at: string;
  updated_at: string;
  suggestions?: ServiceSuggestion[] | null;
  intents?: ServiceIntent[] | null;
};

const getLogoUrl = (url: string | null | undefined): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return `${getApiUrl()}${url}`;
};

export default function AgentEditPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const agentId = params.agentId as string;

  const { agents, fetchAgents, updateAgent, toggleAgent } = useAgentsStore();
  const { refreshProviders } = useIntegrationsStore();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [serviceAgent, setServiceAgent] = useState<ServiceAgent | null>(null);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [provider, setProvider] = useState('');
  const [modelId, setModelId] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [enabled, setEnabled] = useState(false);

  const storeAgent = useMemo(() => agents.find((agent) => agent.id === agentId), [agents, agentId]);
  const tools = storeAgent?.tools ?? [];
  const subagents = useMemo(() => {
    if (!serviceAgent?.intents) return [];
    return serviceAgent.intents
      .filter((intent) => intent.intent_type?.toLowerCase() === 'agent')
      .map((intent) => intent.intent_target)
      .filter((target): target is string => Boolean(target));
  }, [serviceAgent]);

  useEffect(() => {
    const load = async () => {
      try {
        if (!workspaceId || !agentId) return;
        setLoading(true);
        setError(null);

        await Promise.all([
          fetchAgents(workspaceId, true),
          refreshProviders(),
        ]);

        const response = await authFetch(`${getApiUrl()}/api/agents/?workspace_id=${workspaceId}`);
        if (!response.ok) {
          throw new Error('Failed to load agent from service');
        }
        const serviceAgents = (await response.json()) as ServiceAgent[];
        const selectedServiceAgent = serviceAgents.find((agent) => agent.id === agentId) || null;
        if (!selectedServiceAgent) {
          setError('Agent not found in service');
          return;
        }

        setServiceAgent(selectedServiceAgent);
        setName(selectedServiceAgent.name || '');
        setDescription(selectedServiceAgent.description || '');
        setSystemPrompt(selectedServiceAgent.system_prompt || '');
        setProvider(selectedServiceAgent.provider || '');
        setModelId(selectedServiceAgent.model_id || '');
        setLogoUrl(selectedServiceAgent.logo_url || '');
        setEnabled(Boolean(selectedServiceAgent.enabled));

      } catch (err) {
        console.error(err);
        setError(err instanceof Error ? err.message : 'Failed to load agent');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [workspaceId, agentId, fetchAgents, refreshProviders]);

  const handleSave = async () => {
    if (!storeAgent) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await updateAgent(storeAgent.id, {
        name: name.trim(),
        description: description.trim(),
        systemPrompt,
        provider: provider || null,
        modelId: modelId || null,
        logoUrl: logoUrl || null,
      });
      if (storeAgent.enabled !== enabled) {
        await toggleAgent(storeAgent.id);
      }
      setSaved(true);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to save agent');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading agent...</div>;
  }

  if (error) {
    return (
      <div className="space-y-4 p-6">
        <button
          onClick={() => router.push(`/workspace/${workspaceId}/settings/agents`)}
          className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
        >
          <ArrowLeft size={16} />
          Back to agents
        </button>
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      </div>
    );
  }

  if (!storeAgent || !serviceAgent) {
    return (
      <div className="space-y-4 p-6">
        <button
          onClick={() => router.push(`/workspace/${workspaceId}/settings/agents`)}
          className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
        >
          <ArrowLeft size={16} />
          Back to agents
        </button>
        <p className="text-sm text-muted-foreground">Agent not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push(`/workspace/${workspaceId}/settings/agents`)}
            className="mb-3 inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
          >
            <ArrowLeft size={16} />
            Back to agents
          </button>
          <div className="flex items-center gap-3">
            <div className={cn(
              'flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg',
              serviceAgent.logo_url ? 'bg-transparent' : 'bg-muted'
            )}>
              {serviceAgent.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={getLogoUrl(serviceAgent.logo_url)} alt={serviceAgent.name} className="h-full w-full object-cover" />
              ) : (
                <Bot size={16} />
              )}
            </div>
            <div>
              <h2 className="text-lg font-semibold">Edit Agent</h2>
              <p className="text-sm text-muted-foreground">{serviceAgent.name}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Enabled</span>
            <button
              type="button"
              onClick={() => setEnabled((current) => !current)}
              className={cn(
                'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                enabled ? 'bg-primary' : 'bg-muted'
              )}
              title={enabled ? 'Disable agent' : 'Enable agent'}
            >
              <span
                className={cn(
                  'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
                  enabled ? 'translate-x-5' : 'translate-x-0.5'
                )}
              />
            </button>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            <Save size={16} />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {saved && (
        <div className="inline-flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-300">
          <CheckCircle size={14} />
          Agent updated
        </div>
      )}

      <div className="max-h-[75vh] space-y-4 overflow-y-auto rounded-lg border p-4 pr-2">
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">System Prompt</label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={12}
              className="min-h-[14rem] w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">Provider</label>
              <input
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Model ID</label>
              <input
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Logo URL</label>
            <input
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="mb-1 text-sm font-medium">Logo Preview</p>
          {serviceAgent.logo_url ? (
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 overflow-hidden rounded-md border bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={getLogoUrl(serviceAgent.logo_url)} alt={serviceAgent.name} className="h-full w-full object-cover" />
              </div>
              <p className="break-all text-xs text-muted-foreground">{serviceAgent.logo_url}</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No logo defined</p>
          )}
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="mb-2 text-sm font-medium">Suggestions</p>
          {serviceAgent.suggestions && serviceAgent.suggestions.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {serviceAgent.suggestions.map((suggestion) => (
                <li key={`${suggestion.label}-${suggestion.value}`} className="rounded bg-background px-2 py-1">
                  <span className="font-medium">{suggestion.label}</span>
                  <span className="text-muted-foreground"> - {suggestion.value}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No suggestions</p>
          )}
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="mb-2 text-sm font-medium">Intents</p>
          {serviceAgent.intents && serviceAgent.intents.length > 0 ? (
            <div className="space-y-2">
              {serviceAgent.intents.map((intent, index) => (
                <div key={`${intent.intent_value}-${index}`} className="rounded bg-background px-2 py-2 text-xs">
                  <p><span className="text-muted-foreground">Value:</span> {intent.intent_value || '-'}</p>
                  <p><span className="text-muted-foreground">Type:</span> {intent.intent_type || '-'}</p>
                  <p><span className="text-muted-foreground">Target:</span> {intent.intent_target || '-'}</p>
                  <p><span className="text-muted-foreground">Scope:</span> {intent.intent_scope || '-'}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <XCircle size={14} />
              No intents
            </p>
          )}
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="mb-2 text-sm font-medium">Tools</p>
          {tools.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {tools.map((toolId) => (
                <li key={toolId} className="rounded bg-background px-2 py-1 font-mono text-xs">
                  {toolId}
                </li>
              ))}
            </ul>
          ) : (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <XCircle size={14} />
              No tools configured
            </p>
          )}
        </div>
        <div className="rounded-lg border bg-muted/20 p-3">
          <p className="mb-2 text-sm font-medium">Subagents</p>
          {subagents.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {subagents.map((subagent) => (
                <li key={subagent} className="rounded bg-background px-2 py-1 font-mono text-xs">
                  {subagent}
                </li>
              ))}
            </ul>
          ) : (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <XCircle size={14} />
              No subagents configured
            </p>
          )}
        </div>
        <div className="border-t pt-4">
          <h4 className="mb-3 text-sm font-medium text-muted-foreground">Service Metadata</h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-muted-foreground">ID</p>
              <p className="break-all font-mono text-xs">{serviceAgent.id}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Workspace</p>
              <p className="break-all font-mono text-xs">{serviceAgent.workspace_id}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Class</p>
              <p className="break-all font-mono text-xs">{serviceAgent.class_name || 'None'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Status</p>
              <p>{serviceAgent.enabled ? 'Enabled' : 'Disabled'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Provider</p>
              <p>{serviceAgent.provider || 'None'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Model</p>
              <p>{serviceAgent.model_id || 'None'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Created</p>
              <p>{new Date(serviceAgent.created_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Updated</p>
              <p>{new Date(serviceAgent.updated_at).toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
