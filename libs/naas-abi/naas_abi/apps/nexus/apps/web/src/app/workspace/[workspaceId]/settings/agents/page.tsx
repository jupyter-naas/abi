'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Bot, User, Cpu, Plus, Pencil, Trash2, Brain, Sparkles, Zap, Target, Search, X, CheckCircle, XCircle, Circle, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { useIntegrationsStore } from '@/stores/integrations';
import { useAgentsStore, RESERVED_AGENT_TYPES, type Agent } from '@/stores/agents';
import { useServersStore } from '@/stores/servers';
import { useConfirm } from '@/components/ui/dialogs';
import { useParams, useRouter } from 'next/navigation';

// Statically declared so Tailwind's content scanner picks up all class names.
// Indexed by deterministic hash of the type label.
const TYPE_PALETTE: Array<{ bg: string; text: string; hover: string }> = [
  { bg: 'bg-sky-100 dark:bg-sky-950', text: 'text-sky-700 dark:text-sky-300', hover: 'hover:bg-sky-100 hover:text-sky-700 dark:hover:bg-sky-950 dark:hover:text-sky-300' },
  { bg: 'bg-emerald-100 dark:bg-emerald-950', text: 'text-emerald-700 dark:text-emerald-300', hover: 'hover:bg-emerald-100 hover:text-emerald-700 dark:hover:bg-emerald-950 dark:hover:text-emerald-300' },
  { bg: 'bg-amber-100 dark:bg-amber-950', text: 'text-amber-700 dark:text-amber-300', hover: 'hover:bg-amber-100 hover:text-amber-700 dark:hover:bg-amber-950 dark:hover:text-amber-300' },
  { bg: 'bg-rose-100 dark:bg-rose-950', text: 'text-rose-700 dark:text-rose-300', hover: 'hover:bg-rose-100 hover:text-rose-700 dark:hover:bg-rose-950 dark:hover:text-rose-300' },
  { bg: 'bg-violet-100 dark:bg-violet-950', text: 'text-violet-700 dark:text-violet-300', hover: 'hover:bg-violet-100 hover:text-violet-700 dark:hover:bg-violet-950 dark:hover:text-violet-300' },
  { bg: 'bg-teal-100 dark:bg-teal-950', text: 'text-teal-700 dark:text-teal-300', hover: 'hover:bg-teal-100 hover:text-teal-700 dark:hover:bg-teal-950 dark:hover:text-teal-300' },
  { bg: 'bg-orange-100 dark:bg-orange-950', text: 'text-orange-700 dark:text-orange-300', hover: 'hover:bg-orange-100 hover:text-orange-700 dark:hover:bg-orange-950 dark:hover:text-orange-300' },
  { bg: 'bg-pink-100 dark:bg-pink-950', text: 'text-pink-700 dark:text-pink-300', hover: 'hover:bg-pink-100 hover:text-pink-700 dark:hover:bg-pink-950 dark:hover:text-pink-300' },
];

const RESERVED_TYPE_COLORS: Record<string, { bg: string; text: string; hover: string }> = {
  Default: {
    bg: 'bg-blue-100 dark:bg-blue-950',
    text: 'text-blue-700 dark:text-blue-300',
    hover: 'hover:bg-blue-100 hover:text-blue-700 dark:hover:bg-blue-950 dark:hover:text-blue-300',
  },
  Custom: {
    bg: 'bg-purple-100 dark:bg-purple-950',
    text: 'text-purple-700 dark:text-purple-300',
    hover: 'hover:bg-purple-100 hover:text-purple-700 dark:hover:bg-purple-950 dark:hover:text-purple-300',
  },
};

function getTypeColor(label: string): { bg: string; text: string; hover: string } {
  const reserved = RESERVED_TYPE_COLORS[label];
  if (reserved) return reserved;
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) | 0;
  return TYPE_PALETTE[Math.abs(hash) % TYPE_PALETTE.length];
}

function AgentTypeSelect({
  agent,
  currentType,
  customTypes,
  onPickDefault,
  onPickType,
  onCreateType,
}: {
  agent: Agent;
  currentType: string;
  customTypes: string[];
  onPickDefault: (agent: Agent) => void | Promise<void>;
  onPickType: (agent: Agent, type: string) => void;
  onCreateType: (name: string) => string | null;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left });
      }
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setPopoverPos(null);
    }
  }, [open]);

  // Recompute position on scroll/resize while open so the popover follows the trigger.
  useEffect(() => {
    if (!open) return;
    const reposition = () => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left });
      }
    };
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open]);

  const allTypes = useMemo(
    () => [...RESERVED_AGENT_TYPES, ...customTypes],
    [customTypes]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allTypes;
    return allTypes.filter((t) => t.toLowerCase().includes(q));
  }, [allTypes, query]);

  const trimmed = query.trim();
  const canCreate =
    trimmed.length > 0 &&
    !allTypes.some((t) => t.toLowerCase() === trimmed.toLowerCase());

  const color = getTypeColor(currentType);
  const disabled = !agent.enabled;

  const handlePick = (type: string) => {
    setOpen(false);
    if (type === currentType) return;
    if (type === 'Default') {
      void onPickDefault(agent);
      return;
    }
    if (agent.isDefault) {
      // Demotion blocked — promote another agent instead.
      return;
    }
    onPickType(agent, type);
  };

  const handleCreate = () => {
    if (!canCreate) return;
    const created = onCreateType(trimmed);
    if (!created) return;
    setOpen(false);
    if (agent.isDefault) return; // Won't demote
    onPickType(agent, created);
  };

  return (
    <div className="inline-block">
      <button
        ref={triggerRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (disabled) return;
          setOpen((v) => !v);
        }}
        disabled={disabled}
        title={disabled ? 'Enable agent to change type' : 'Change type'}
        className={cn(
          'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors',
          color.bg,
          color.text,
          !disabled && 'cursor-pointer hover:opacity-80',
          disabled && 'opacity-60 cursor-not-allowed'
        )}
      >
        {currentType}
      </button>

      {open && popoverPos && typeof document !== 'undefined' && createPortal(
        <>
          <div
            className="fixed inset-0 z-[9998]"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
            }}
          />
          <div
            style={{ top: popoverPos.top, left: popoverPos.left }}
            className="fixed z-[9999] w-56 rounded-md border border-border bg-popover p-1 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (canCreate) {
                    handleCreate();
                  } else if (filtered.length > 0) {
                    handlePick(filtered[0]);
                  }
                } else if (e.key === 'Escape') {
                  setOpen(false);
                }
              }}
              placeholder="Search or create type..."
              className="mb-1 w-full rounded border-0 bg-muted px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-primary/30"
            />
            <div className="max-h-60 overflow-y-auto">
              {filtered.map((type) => {
                const c = getTypeColor(type);
                const isSelected = type === currentType;
                const wouldDemote =
                  agent.isDefault && type !== 'Default';
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => handlePick(type)}
                    disabled={wouldDemote}
                    title={
                      wouldDemote
                        ? 'To change the default, promote another agent to "Default" first'
                        : undefined
                    }
                    className={cn(
                      'flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-xs',
                      !wouldDemote && 'hover:bg-accent cursor-pointer',
                      wouldDemote && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    <span
                      className={cn(
                        'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
                        c.bg,
                        c.text
                      )}
                    >
                      {type}
                    </span>
                    {isSelected && <Check size={12} className="text-muted-foreground" />}
                  </button>
                );
              })}
              {filtered.length === 0 && !canCreate && (
                <p className="px-2 py-1.5 text-xs text-muted-foreground">No matching type</p>
              )}
              {canCreate && (
                <button
                  type="button"
                  onClick={handleCreate}
                  className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                >
                  <Plus size={12} className="text-muted-foreground" />
                  <span>
                    Create{' '}
                    <span className="font-medium text-foreground">&ldquo;{trimmed}&rdquo;</span>
                  </span>
                </button>
              )}
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}

const getApiBase = () => getApiUrl();

const getLogoUrl = (url: string | null): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return `${getApiBase()}${url}`;
};

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
    setDefaultAgent,
    fetchAgents,
    customTypes,
    agentTypeOverrides,
    addCustomType,
    setAgentTypeOverride,
  } = useAgentsStore();
  const { fetchServers } = useServersStore();
  const { confirm: confirmSwitchDefault, dialog: confirmDialog } = useConfirm();

  const getAgentTypeLabel = (agent: Agent): string => {
    if (agent.isDefault) return 'Default';
    return agentTypeOverrides[agent.id] ?? 'Custom';
  };

  const handlePromoteToDefault = async (agent: Agent) => {
    const currentDefault = agents.find((a) => a.isDefault && a.id !== agent.id);
    if (currentDefault) {
      const ok = await confirmSwitchDefault({
        title: 'Switch default agent?',
        description: `You are about to switch the default agent from "${currentDefault.name}" to "${agent.name}".\n\nNew chats will use "${agent.name}" going forward.`,
        confirmLabel: 'Switch',
        destructive: true,
      });
      if (!ok) return;
    }
    await setDefaultAgent(agent.id);
  };

  // Fetch agents from database
  useEffect(() => {
    const loadAgents = async () => {
      try {
        if (!workspaceId) return;
        // Force a fresh fetch so the Model column reflects backend-resolved
        // model_id values (which the persisted store may not yet have cached).
        await fetchAgents(workspaceId, true);
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

  const getAgentSource = (agent: Agent): string => {
    // Determine source based on provider or model_id prefix
    if (agent.provider === 'abi') return 'ABI Server';
    if (agent.provider) return agent.provider.toUpperCase();
    return 'Model Registry';
  };

  const getModelDisplay = (agent: Agent): string => {
    // Otherwise show model ID if available
    return agent.modelId || agent.providerId || 'Not assigned';
  };

  const openModel = (modelId: string) => {
    if (!workspaceId) return;
    router.push(`/workspace/${workspaceId}/settings/models/${encodeURIComponent(modelId)}`);
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
                  <th className="p-3 font-medium">Source</th>
                  <th className="p-3 font-medium">Model</th>
                  <th className="p-3 font-medium">Type</th>
                  <th className="p-3 font-medium w-24">Enabled</th>
                  <th className="p-3 font-medium w-32">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAgents.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">
                      {searchQuery ? `No agents match "${searchQuery}"` : 'No agents available'}
                    </td>
                  </tr>
                ) : (
                  filteredAgents.map((agent) => {
                    const assignedProvider = getAssignedProvider(agent.providerId);
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
                          <span className="text-sm text-muted-foreground capitalize">
                            {getAgentSource(agent)}
                          </span>
                        </td>
                        <td className="p-3" onClick={(e) => e.stopPropagation()}>
                          {agent.modelId ? (
                            <button
                              type="button"
                              onClick={() => openModel(agent.modelId as string)}
                              title={`View model ${agent.modelId}`}
                              className="flex items-center gap-2 text-left"
                            >
                              <CheckCircle size={14} className="text-green-500" />
                              <span className="text-sm font-mono text-primary underline-offset-2 hover:underline">
                                {agent.modelId}
                              </span>
                            </button>
                          ) : assignedProvider ? (
                            <div className="flex items-center gap-2">
                              <CheckCircle size={14} className="text-green-500" />
                              <span className="text-sm">{assignedProvider.model}</span>
                            </div>
                          ) : agent.providerId ? (
                            <div className="flex items-center gap-2">
                              <Circle size={14} className="text-blue-500" />
                              <span className="text-sm text-muted-foreground">{getModelDisplay(agent)}</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <XCircle size={14} className="text-muted-foreground" />
                              <span className="text-sm text-muted-foreground">Not assigned</span>
                            </div>
                          )}
                        </td>
                        <td className="p-3" onClick={(e) => e.stopPropagation()}>
                          <AgentTypeSelect
                            agent={agent}
                            currentType={getAgentTypeLabel(agent)}
                            customTypes={customTypes}
                            onPickDefault={handlePromoteToDefault}
                            onPickType={(a, type) => setAgentTypeOverride(a.id, type)}
                            onCreateType={addCustomType}
                          />
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
      {confirmDialog}
    </div>
  );
}
