'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Bot, CheckCircle, Save, Search, Target, Wrench, X, XCircle } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useAgentsStore, type AgentCommand, type AgentIntent } from '@/stores/agents';
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

  const { agents, fetchAgents, updateAgent, toggleAgent, fetchAgentCommands } = useAgentsStore();
  const { refreshProviders } = useIntegrationsStore();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [serviceAgent, setServiceAgent] = useState<ServiceAgent | null>(null);
  const [registeredTools, setRegisteredTools] = useState<AgentCommand[]>([]);
  const [registeredSubAgents, setRegisteredSubAgents] = useState<AgentCommand[]>([]);
  const [registeredIntents, setRegisteredIntents] = useState<AgentIntent[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);
  const [toolsQuery, setToolsQuery] = useState('');
  const [agentsQuery, setAgentsQuery] = useState('');
  const [intentsQuery, setIntentsQuery] = useState('');

  // The agent we're viewing acts as the "supervisor" for dedupe purposes:
  // when the recursive walk surfaces the same tool/sub-agent on both this
  // agent and a deeper sub-agent, we keep the entry that lives on this agent.
  const supervisorClassName = serviceAgent?.class_name ?? null;

  const dedupeByCommand = <T extends AgentCommand>(items: T[]): T[] => {
    const byCommand = new Map<string, T>();
    for (const item of items) {
      const existing = byCommand.get(item.command);
      if (!existing) {
        byCommand.set(item.command, item);
        continue;
      }
      const existingIsSupervisor =
        supervisorClassName !== null && existing.owner_class_name === supervisorClassName;
      const candidateIsSupervisor =
        supervisorClassName !== null && item.owner_class_name === supervisorClassName;
      if (!existingIsSupervisor && candidateIsSupervisor) {
        byCommand.set(item.command, item);
      }
    }
    return Array.from(byCommand.values());
  };

  const sortedTools = useMemo(
    () =>
      dedupeByCommand(registeredTools).sort((a, b) => a.name.localeCompare(b.name)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [registeredTools, supervisorClassName]
  );
  const sortedSubAgents = useMemo(
    () =>
      dedupeByCommand(registeredSubAgents).sort((a, b) => a.name.localeCompare(b.name)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [registeredSubAgents, supervisorClassName]
  );

  const matchesQuery = (entry: AgentCommand, query: string) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      entry.name.toLowerCase().includes(q) ||
      entry.command.toLowerCase().includes(q) ||
      (entry.description || '').toLowerCase().includes(q) ||
      (entry.owner_name || '').toLowerCase().includes(q)
    );
  };

  const filteredTools = useMemo(
    () => sortedTools.filter((t) => matchesQuery(t, toolsQuery)),
    [sortedTools, toolsQuery]
  );
  const filteredSubAgents = useMemo(
    () => sortedSubAgents.filter((s) => matchesQuery(s, agentsQuery)),
    [sortedSubAgents, agentsQuery]
  );

  // Intents: dedupe by (intent_value, intent_target), preferring entries from
  // the agent being viewed when the recursive walker surfaces the same intent
  // on a deeper sub-agent.
  const sortedIntents = useMemo(() => {
    const byKey = new Map<string, AgentIntent>();
    for (const intent of registeredIntents) {
      const key = `${intent.intent_value}::${intent.intent_target}`;
      const existing = byKey.get(key);
      if (!existing) {
        byKey.set(key, intent);
        continue;
      }
      const existingIsSupervisor =
        supervisorClassName !== null && existing.owner_class_name === supervisorClassName;
      const candidateIsSupervisor =
        supervisorClassName !== null && intent.owner_class_name === supervisorClassName;
      if (!existingIsSupervisor && candidateIsSupervisor) {
        byKey.set(key, intent);
      }
    }
    // Sort by type bucket (agent → tool → raw → anything else), then by value
    // within each bucket so the table groups related intents together.
    const typeOrder: Record<string, number> = { agent: 0, tool: 1, raw: 2 };
    return Array.from(byKey.values()).sort((a, b) => {
      const aRank = typeOrder[a.intent_type?.toLowerCase()] ?? 99;
      const bRank = typeOrder[b.intent_type?.toLowerCase()] ?? 99;
      if (aRank !== bRank) return aRank - bRank;
      return a.intent_value.localeCompare(b.intent_value);
    });
  }, [registeredIntents, supervisorClassName]);

  const filteredIntents = useMemo(() => {
    const q = intentsQuery.trim().toLowerCase();
    if (!q) return sortedIntents;
    return sortedIntents.filter((intent) =>
      intent.intent_value.toLowerCase().includes(q) ||
      intent.intent_type.toLowerCase().includes(q) ||
      intent.intent_target.toLowerCase().includes(q) ||
      intent.intent_scope.toLowerCase().includes(q) ||
      (intent.owner_name || '').toLowerCase().includes(q)
    );
  }, [sortedIntents, intentsQuery]);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [provider, setProvider] = useState('');
  const [modelId, setModelId] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [enabled, setEnabled] = useState(false);

  const storeAgent = useMemo(() => agents.find((agent) => agent.id === agentId), [agents, agentId]);

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

  useEffect(() => {
    if (!agentId) return;
    let cancelled = false;
    setCommandsLoading(true);
    fetchAgentCommands(agentId, { recursive: true })
      .then((result) => {
        if (cancelled || !result) return;
        setRegisteredTools(result.tools || []);
        setRegisteredSubAgents(result.sub_agents || []);
        setRegisteredIntents(result.intents || []);
        // The commands endpoint instantiates the agent, which lets us read the
        // live model_id / provider straight from the BaseChatModel.  Prefer it
        // over what the DB had (which may be stale or never populated).
        if (typeof result.model_id === 'string' && result.model_id) {
          setModelId(result.model_id);
        }
        if (typeof result.provider === 'string' && result.provider) {
          setProvider(result.provider);
        }
      })
      .finally(() => {
        if (!cancelled) setCommandsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, fetchAgentCommands]);

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
        {/* Tools — includes tools from sub-agents (recursive) */}
        <div className="rounded-lg border bg-muted/20 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wrench size={14} className="text-blue-600 dark:text-blue-300" />
              <p className="text-sm font-medium">Tools</p>
            </div>
            <span className="text-xs text-muted-foreground">
              {commandsLoading
                ? 'Loading…'
                : toolsQuery.trim()
                  ? `${filteredTools.length} / ${sortedTools.length} registered`
                  : `${sortedTools.length} registered`}
            </span>
          </div>
          {sortedTools.length > 0 && (
            <div className="mb-3 relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search tools..."
                value={toolsQuery}
                onChange={(e) => setToolsQuery(e.target.value)}
                className="w-full rounded-md border bg-background pl-8 pr-8 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
              />
              {toolsQuery && (
                <button
                  type="button"
                  onClick={() => setToolsQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          )}
          {sortedTools.length === 0 ? (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <XCircle size={14} />
              {commandsLoading ? 'Loading tools…' : 'No tools registered on this agent instance'}
            </p>
          ) : filteredTools.length === 0 ? (
            <p className="rounded bg-background px-3 py-2 text-xs text-muted-foreground">
              No tools match &ldquo;{toolsQuery}&rdquo;
            </p>
          ) : (
            <div className="space-y-2">
              {filteredTools.map((tool) => {
                const ownedBySubAgent = Boolean(
                  tool.owner_name && tool.owner_name !== serviceAgent.name
                );
                const params = tool.parameters || [];
                const returnDirect = Boolean(tool.return_direct);
                return (
                  <div key={`${tool.owner_class_name || ''}:${tool.name}`} className="rounded bg-background px-3 py-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded bg-blue-500/15 text-blue-600 dark:text-blue-300">
                        <Wrench size={12} />
                      </span>
                      <span className="font-medium">{tool.name}</span>
                      {ownedBySubAgent ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          <Bot size={10} />
                          {tool.owner_name}
                        </span>
                      ) : null}
                      {returnDirect ? (
                        <span
                          className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300"
                          title="The tool's output is returned directly to the user (short-circuits the agent)."
                        >
                          return_direct
                        </span>
                      ) : null}
                      <code className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">
                        /{tool.command}
                      </code>
                    </div>
                    {tool.description ? (
                      <p className="mt-1 text-muted-foreground line-clamp-3">{tool.description}</p>
                    ) : null}
                    {params.length > 0 && (
                      <div className="mt-2 rounded border bg-muted/30">
                        <div className="border-b px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                          Parameters
                        </div>
                        <table className="w-full text-[11px]">
                          <thead>
                            <tr className="border-b bg-muted/40 text-left">
                              <th className="px-2 py-1 font-medium w-32">Name</th>
                              <th className="px-2 py-1 font-medium w-24">Type</th>
                              <th className="px-2 py-1 font-medium w-20">Required</th>
                              <th className="px-2 py-1 font-medium w-28">Default</th>
                              <th className="px-2 py-1 font-medium">Description</th>
                            </tr>
                          </thead>
                          <tbody>
                            {params.map((param) => (
                              <tr key={param.name} className="border-b last:border-b-0">
                                <td className="px-2 py-1 align-top font-mono">{param.name}</td>
                                <td className="px-2 py-1 align-top font-mono text-muted-foreground">{param.type}</td>
                                <td className="px-2 py-1 align-top">
                                  {param.required ? (
                                    <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-[10px] font-medium text-red-700 dark:text-red-300">
                                      required
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">optional</span>
                                  )}
                                </td>
                                <td className="px-2 py-1 align-top font-mono text-muted-foreground">
                                  {param.required
                                    ? '—'
                                    : param.default === undefined || param.default === null
                                      ? 'None'
                                      : JSON.stringify(param.default)}
                                </td>
                                <td className="px-2 py-1 align-top text-muted-foreground">
                                  {param.description || '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Agents — sub-agents reachable from this agent (recursive) */}
        <div className="rounded-lg border bg-muted/20 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot size={14} className="text-purple-600 dark:text-purple-300" />
              <p className="text-sm font-medium">Agents</p>
            </div>
            <span className="text-xs text-muted-foreground">
              {commandsLoading
                ? 'Loading…'
                : agentsQuery.trim()
                  ? `${filteredSubAgents.length} / ${sortedSubAgents.length} registered`
                  : `${sortedSubAgents.length} registered`}
            </span>
          </div>
          {sortedSubAgents.length > 0 && (
            <div className="mb-3 relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search agents..."
                value={agentsQuery}
                onChange={(e) => setAgentsQuery(e.target.value)}
                className="w-full rounded-md border bg-background pl-8 pr-8 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
              />
              {agentsQuery && (
                <button
                  type="button"
                  onClick={() => setAgentsQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          )}
          {sortedSubAgents.length === 0 ? (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <XCircle size={14} />
              {commandsLoading ? 'Loading agents…' : 'No agents registered on this agent instance'}
            </p>
          ) : filteredSubAgents.length === 0 ? (
            <p className="rounded bg-background px-3 py-2 text-xs text-muted-foreground">
              No agents match &ldquo;{agentsQuery}&rdquo;
            </p>
          ) : (
            <div className="space-y-2">
              {filteredSubAgents.map((subagent) => {
                const ownedByDeeperAgent = Boolean(
                  subagent.owner_name && subagent.owner_name !== serviceAgent.name
                );
                return (
                  <div key={`${subagent.owner_class_name || ''}:${subagent.name}`} className="rounded bg-background px-3 py-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded bg-purple-500/15 text-purple-600 dark:text-purple-300">
                        <Bot size={12} />
                      </span>
                      <span className="font-medium">{subagent.name}</span>
                      {ownedByDeeperAgent ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          <Bot size={10} />
                          {subagent.owner_name}
                        </span>
                      ) : null}
                      <code className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">
                        /{subagent.command}
                      </code>
                    </div>
                    {subagent.description ? (
                      <p className="mt-1 text-muted-foreground line-clamp-3">{subagent.description}</p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Intents — extracted from the live IntentAgent instance (recursive) */}
        <div className="rounded-lg border bg-muted/20 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Target size={14} className="text-amber-600 dark:text-amber-300" />
              <p className="text-sm font-medium">Intents</p>
            </div>
            <span className="text-xs text-muted-foreground">
              {commandsLoading
                ? 'Loading…'
                : intentsQuery.trim()
                  ? `${filteredIntents.length} / ${sortedIntents.length} registered`
                  : `${sortedIntents.length} registered`}
            </span>
          </div>
          {sortedIntents.length > 0 && (
            <div className="mb-3 relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search intents..."
                value={intentsQuery}
                onChange={(e) => setIntentsQuery(e.target.value)}
                className="w-full rounded-md border bg-background pl-8 pr-8 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
              />
              {intentsQuery && (
                <button
                  type="button"
                  onClick={() => setIntentsQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          )}
          {sortedIntents.length === 0 ? (
            <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <XCircle size={14} />
              {commandsLoading ? 'Loading intents…' : 'No intents registered on this agent instance'}
            </p>
          ) : filteredIntents.length === 0 ? (
            <p className="rounded bg-background px-3 py-2 text-xs text-muted-foreground">
              No intents match &ldquo;{intentsQuery}&rdquo;
            </p>
          ) : (
            <div className="rounded-md border bg-background overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-muted/40 text-left">
                    <th className="px-2 py-1.5 font-medium w-24">Type</th>
                    <th className="px-2 py-1.5 font-medium">Value</th>
                    <th className="px-2 py-1.5 font-medium">Target</th>
                    <th className="px-2 py-1.5 font-medium w-20">Scope</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredIntents.map((intent, idx) => {
                    const ownedByDeeperAgent = Boolean(
                      intent.owner_name && intent.owner_name !== serviceAgent.name
                    );
                    const typeColor =
                      intent.intent_type === 'agent'
                        ? 'bg-purple-500/15 text-purple-700 dark:text-purple-300'
                        : intent.intent_type === 'tool'
                          ? 'bg-blue-500/15 text-blue-700 dark:text-blue-300'
                          : 'bg-amber-500/15 text-amber-700 dark:text-amber-300';
                    return (
                      <tr
                        key={`${intent.owner_class_name || ''}:${intent.intent_value}:${intent.intent_target}:${idx}`}
                        className="border-b last:border-b-0"
                      >
                        <td className="px-2 py-1.5 align-top">
                          <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium uppercase', typeColor)}>
                            {intent.intent_type || '-'}
                          </span>
                        </td>
                        <td className="px-2 py-1.5 align-top">
                          <div className="flex items-center gap-1.5">
                            <span className="break-words">{intent.intent_value || '-'}</span>
                            {ownedByDeeperAgent ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                <Bot size={10} />
                                {intent.owner_name}
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-2 py-1.5 align-top break-words font-mono text-[11px]">
                          {intent.intent_target || '-'}
                        </td>
                        <td className="px-2 py-1.5 align-top text-muted-foreground">
                          {intent.intent_scope || '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
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
              <p>{provider || serviceAgent.provider || 'None'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Model</p>
              <p>{modelId || serviceAgent.model_id || 'None'}</p>
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
