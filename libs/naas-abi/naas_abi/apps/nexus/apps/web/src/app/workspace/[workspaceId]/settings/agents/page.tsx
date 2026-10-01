'use client';

import { useState, useEffect } from 'react';
import { Bot, User, Cpu, Plus, Pencil, Trash2, Brain, Sparkles, Zap, Target, Search, CheckCircle, XCircle, Server } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getLogoUrl } from '@/lib/logo-url';
import { useIntegrationsStore } from '@/stores/integrations';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useModelsStore, modelDisplayName } from '@/stores/models';
import { useServersStore } from '@/stores/servers';
import { useParams, useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Textarea } from '@/components/ui/input';
import {
  SettingsEmpty,
  SettingsField,
  SettingsLoading,
  SettingsPageHeader,
  SettingsSearch,
  SettingsSection,
  settingsTable,
} from '@/components/settings/settings-ui';

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
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();

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

  const handleDeleteAgent = async (id: string) => {
    const ok = await confirmDelete({
      title: 'Delete agent?',
      description: 'Are you sure you want to delete this agent?',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (ok) deleteAgent(id);
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
    return <SettingsLoading label="Loading agents…" />;
  }

  const resetNewAgent = () => {
    setShowAddForm(false);
    setNewAgent({
      name: '',
      description: '',
      icon: 'sparkles',
      systemPrompt: 'You are a helpful AI assistant.',
      providerId: null,
    });
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title={
          <span className="flex items-center gap-2">
            Agents
            <Badge>{filteredAgents.length}</Badge>
          </span>
        }
        description="Manage AI agents and their configurations"
        actions={
          <Button onClick={() => setShowAddForm(true)}>
            <Plus size={16} />
            Add Agent
          </Button>
        }
      />

      {showAddForm && (
        <SettingsSection title="Add New Agent">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <SettingsField label="Name *">
                <Input
                  type="text"
                  value={newAgent.name}
                  onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                  placeholder="Agent name"
                />
              </SettingsField>
              <SettingsField label="Icon">
                <div className="flex gap-2">
                  {iconOptions.map((icon) => {
                    const IconComp = iconMap[icon];
                    return (
                      <Button
                        key={icon}
                        variant="secondary"
                        size="icon"
                        onClick={() => setNewAgent({ ...newAgent, icon })}
                        className={cn(
                          'h-9 w-9',
                          newAgent.icon === icon && 'border-primary bg-primary/10 text-primary hover:bg-primary/10'
                        )}
                      >
                        <IconComp size={16} />
                      </Button>
                    );
                  })}
                </div>
              </SettingsField>
            </div>
            <SettingsField label="Description">
              <Input
                type="text"
                value={newAgent.description}
                onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                placeholder="Brief description"
              />
            </SettingsField>
            <SettingsField label="System Prompt">
              <Textarea
                value={newAgent.systemPrompt}
                onChange={(e) => setNewAgent({ ...newAgent, systemPrompt: e.target.value })}
                placeholder="You are a helpful AI assistant..."
                rows={3}
                className="resize-none"
              />
            </SettingsField>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={resetNewAgent}>
                Cancel
              </Button>
              <Button onClick={handleAddAgent} disabled={!newAgent.name.trim()}>
                Add Agent
              </Button>
            </div>
          </div>
        </SettingsSection>
      )}

      {displayAgents.length === 0 ? (
        <SettingsEmpty
          icon={<Bot size={40} className="opacity-40" />}
          title="No agents configured"
          description="Create AI agents to get started"
          action={
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Add Agent
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          <SettingsSearch value={searchQuery} onChange={setSearchQuery} placeholder="Search agents..." />

          <div className={settingsTable.wrapper}>
            <table className={settingsTable.table}>
              <thead>
                <tr className={settingsTable.headRow}>
                  <th className={settingsTable.th}>Agent</th>
                  <th className={settingsTable.th}>Models</th>
                  <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
                  <th className={cn(settingsTable.th, 'w-24')}>Actions</th>
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
                  filteredAgents.map((agent) => (
                    <tr
                      key={agent.id}
                      onClick={() => handleOpenAgentEditor(agent.id)}
                      className={cn(settingsTable.row, 'cursor-pointer')}
                    >
                      <td className={cn(settingsTable.td, 'align-top')}>
                        <div className="flex min-h-[3.25rem] items-center gap-3">
                          <div
                            className={cn(
                              'flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden',
                              agent.logoUrl ? 'bg-transparent' : 'bg-muted'
                            )}
                          >
                            <AgentAvatar agent={agent} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-medium">{agent.name}</p>
                            {agent.class_name ? (
                              <p className="pb-0.5 text-micro italic text-muted-foreground">
                                {agent.class_name.split('/')[0]}
                              </p>
                            ) : null}
                            <p
                              className="line-clamp-2 min-h-[2rem] text-xs text-muted-foreground"
                              title={agent.description || undefined}
                            >
                              {agent.description || '\u00A0'}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className={settingsTable.td}>
                        {(() => {
                          const modelIds = getModelIds(agent);
                          if (modelIds.length === 0) {
                            return (
                              <div className="flex items-center gap-2 text-muted-foreground">
                                <XCircle size={14} />
                                <span>{agent.provider === 'abi' ? 'Not exposed' : 'Not assigned'}</span>
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
                                      <CheckCircle size={14} className="shrink-0 text-primary" />
                                    )}
                                    <span
                                      className={cn(agent.provider === 'abi' && 'italic text-muted-foreground')}
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
                      <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={agent.enabled}
                          onCheckedChange={() => toggleAgent(agent.id)}
                          aria-label={agent.enabled ? 'Disable agent' : 'Enable agent'}
                          title={agent.enabled ? 'Disable agent' : 'Enable agent'}
                        />
                      </td>
                      <td className={settingsTable.td}>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenAgentEditor(agent.id);
                            }}
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </Button>
                          <Button
                            variant="destructive-ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteAgent(agent.id);
                            }}
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </Button>
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
      {confirmDialog}
    </div>
  );
}
