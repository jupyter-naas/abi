'use client';

import { useState, useEffect } from 'react';
import { Bot, User, Cpu, Plus, Pencil, Trash2, Brain, Sparkles, Zap, Target, Search, X, CheckCircle, XCircle, Server } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getLogoUrl } from '@/lib/logo-url';
import { useIntegrationsStore } from '@/stores/integrations';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useModelsStore, modelDisplayName } from '@/stores/models';
import { useServersStore } from '@/stores/servers';
import { useParams, useRouter } from 'next/navigation';

const iconMap = {
  bot: Bot,
  user: User,
  cpu: Cpu,
  brain: Brain,
  sparkles: Sparkles,
  zap: Zap,
  target: Target,
  search: Search,
};

const iconOptions: Agent['icon'][] = ['user', 'bot', 'cpu', 'brain', 'sparkles', 'zap', 'target', 'search'];

function AgentAvatar({ agent, size = 18 }: { agent: Agent; size?: number }) {
  if (agent.logoUrl) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={getLogoUrl(agent.logoUrl)} alt={agent.name} className="h-full w-full object-cover" />;
  }
  const Icon = iconMap[agent.icon] || Sparkles;
  return <Icon size={size} />;
}

export default function AgentsPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const [mounted, setMounted] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [newAgent, setNewAgent] = useState({
    name: '',
    description: '',
    icon: 'sparkles' as Agent['icon'],
    systemPrompt: 'You are a helpful AI assistant.',
    providerId: null as string | null,
  });

  const { providers } = useIntegrationsStore();
  const {
    agents,
    addAgent,
    deleteAgent,
    toggleAgent,
    fetchAgents,
  } = useAgentsStore();
  const { fetchServers } = useServersStore();
  const { models, fetchModels } = useModelsStore();

  // Fetch agents from database
  useEffect(() => {
    const loadAgents = async () => {
      try {
        if (!workspaceId) return;
        await fetchAgents(workspaceId);
        await fetchServers(workspaceId);
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      }
    };

    loadAgents();
  }, [fetchAgents, fetchServers, workspaceId]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const enabledProviders = mounted ? providers.filter((p) => p.enabled) : [];
  const displayAgents = mounted ? agents : [];
  
  // Filter and sort agents alphabetically by name
  const filteredAgents = searchQuery.trim()
    ? displayAgents
        .filter(
          (agent) =>
            agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            agent.description.toLowerCase().includes(searchQuery.toLowerCase())
        )
        .sort((a, b) => a.name.localeCompare(b.name))
    : displayAgents.slice().sort((a, b) => a.name.localeCompare(b.name));

  const handleAddAgent = () => {
    if (!newAgent.name.trim()) return;
    void addAgent({
      name: newAgent.name.trim(),
      description: newAgent.description.trim(),
      icon: newAgent.icon,
      systemPrompt: newAgent.systemPrompt,
      providerId: newAgent.providerId,
      provider: null,
      modelId: null,
      logoUrl: null,
      enabled: true,
      tools: ['search_knowledge', 'search_files', 'read_ontology'],
      capabilities: { memory: true, reasoning: false, vision: false },
      intentMappings: [],
    });
    setNewAgent({
      name: '',
      description: '',
      icon: 'sparkles',
      systemPrompt: 'You are a helpful AI assistant.',
      providerId: null,
    });
    setShowAddForm(false);
  };

  const handleOpenAgentEditor = (agentId: string) => {
    if (!workspaceId) return;
    router.push(`/workspace/${workspaceId}/settings/agents/${agentId}`);
  };

  const handleDeleteAgent = (id: string) => {
    if (confirm('Are you sure you want to delete this agent?')) {
      deleteAgent(id);
    }
  };

  const getAssignedProvider = (providerId: string | null) => {
    if (!providerId) return null;
    return enabledProviders.find((p) => p.id === providerId);
  };

  const getModelIds = (agent: Agent): string[] => {
    const declared = (agent.modelIds || []).map((id) => id.trim()).filter(Boolean);
    if (declared.length > 0) return Array.from(new Set(declared));

    let rawId: string | null = null;
    if (agent.provider === 'abi') {
      rawId = agent.modelId || agent.resolvedModelId || null;
    } else if (agent.provider) {
      const provider = enabledProviders.find((p) => p.type === agent.provider && p.enabled);
      rawId = agent.modelId || provider?.model || agent.resolvedModelId || null;
    } else if (agent.providerId) {
      rawId =
        getAssignedProvider(agent.providerId)?.model ||
        agent.modelId ||
        agent.resolvedModelId ||
        null;
    } else {
      rawId = agent.modelId || agent.resolvedModelId || null;
    }
    return rawId ? [rawId] : [];
  };

  if (!mounted) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading agents...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Agents</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {filteredAgents.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage AI agents and their configurations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Agent
          </button>
        </div>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <h3 className="mb-4 font-medium">Add New Agent</h3>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Name *</label>
                <input
                  type="text"
                  value={newAgent.name}
                  onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                  placeholder="Agent name"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Icon</label>
                <div className="flex gap-2">
                  {iconOptions.map((icon) => {
                    const IconComp = iconMap[icon];
                    return (
                      <button
                        key={icon}
                        onClick={() => setNewAgent({ ...newAgent, icon })}
                        className={cn(
                          'rounded border p-2',
                          newAgent.icon === icon
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'hover:bg-muted'
                        )}
                      >
                        <IconComp size={16} />
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input
                type="text"
                value={newAgent.description}
                onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                placeholder="Brief description"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">System Prompt</label>
              <textarea
                value={newAgent.systemPrompt}
                onChange={(e) => setNewAgent({ ...newAgent, systemPrompt: e.target.value })}
                placeholder="You are a helpful AI assistant..."
                rows={3}
                className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setNewAgent({
                    name: '',
                    description: '',
                    icon: 'sparkles',
                    systemPrompt: 'You are a helpful AI assistant.',
                    providerId: null,
                  });
                }}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleAddAgent}
                disabled={!newAgent.name.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Add Agent
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Agents List */}
      {displayAgents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <Bot size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No agents configured</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Create AI agents to get started
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Agent
          </button>
        </div>
      ) : (
        <div>
          {/* Search */}
          {displayAgents.length > 0 && (
            <div className="mb-4 relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search agents..."
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
                  <th className="p-3 font-medium">Agent</th>
                  <th className="p-3 font-medium">Models</th>
                  <th className="p-3 font-medium w-24">Enabled</th>
                  <th className="p-3 font-medium w-32">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAgents.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      {searchQuery ? `No agents match "${searchQuery}"` : 'No agents available'}
                    </td>
                  </tr>
                ) : (
                  filteredAgents.map((agent) => {
                    return (
                      <tr
                        key={agent.id}
                        onClick={() => handleOpenAgentEditor(agent.id)}
                        className="cursor-pointer border-b transition-colors hover:bg-muted/30"
                      >
                        <td className="p-3 align-top">
                          <div className="flex items-center gap-3 min-h-[3.25rem]">
                            <div className={cn(
                              'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg overflow-hidden',
                              agent.logoUrl ? 'bg-transparent' : 'bg-muted'
                            )}>
                              <AgentAvatar agent={agent} />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-medium">{agent.name}</p>
                              {agent.class_name ? (
                                <p className="text-[10px] text-muted-foreground italic pb-0.5">
                                  {agent.class_name.split('/')[0]}
                                </p>
                              ) : null}
                              <p
                                className="text-xs text-muted-foreground line-clamp-2 min-h-[2rem]"
                                title={agent.description || undefined}
                              >
                                {agent.description || '\u00A0'}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="p-3">
                          {(() => {
                            const modelIds = getModelIds(agent);
                            if (modelIds.length === 0) {
                              return (
                                <div className="flex items-center gap-2">
                                  <XCircle size={14} className="text-muted-foreground" />
                                  <span className="text-sm text-muted-foreground">
                                    {agent.provider === 'abi' ? 'Not exposed' : 'Not assigned'}
                                  </span>
                                </div>
                              );
                            }
                            return (
                              <div className="flex flex-col gap-1">
                                {modelIds.map((id) => {
                                  const label = modelDisplayName(models, id) ?? id;
                                  return (
                                    <div key={id} className="flex items-center gap-2">
                                      {agent.provider === 'abi' ? (
                                        <Server size={14} className="shrink-0 text-muted-foreground" />
                                      ) : (
                                        <CheckCircle size={14} className="shrink-0 text-green-500" />
                                      )}
                                      <span
                                        className={cn(
                                          'text-sm',
                                          agent.provider === 'abi' && 'text-muted-foreground italic'
                                        )}
                                        title={id}
                                      >
                                        {label}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            );
                          })()}
                        </td>
                        <td className="p-3">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleAgent(agent.id);
                            }}
                            className={cn(
                              'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                              agent.enabled ? 'bg-primary' : 'bg-muted'
                            )}
                            title={agent.enabled ? 'Disable agent' : 'Enable agent'}
                          >
                            <span
                              className={cn(
                                'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
                                agent.enabled ? 'translate-x-5' : 'translate-x-0.5'
                              )}
                            />
                          </button>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenAgentEditor(agent.id);
                              }}
                              className="rounded p-1.5 text-muted-foreground hover:bg-muted"
                              title="Edit"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteAgent(agent.id);
                              }}
                              className="rounded p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
