'use client';

import { useState, useEffect, Fragment } from 'react';
import { Bot, User, Cpu, Plus, Pencil, Trash2, Save, Brain, Sparkles, Zap, Target, Search, X, Users, RefreshCw, CheckCircle, XCircle, Circle, ChevronDown, Server } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useIntegrationsStore } from '@/stores/integrations';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useServersStore } from '@/stores/servers';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

const API_BASE = getApiUrl();

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

export default function AgentsPage() {
  const [mounted, setMounted] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [editedPrompt, setEditedPrompt] = useState('');
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [syncingAgents, setSyncingAgents] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [showSyncDropdown, setShowSyncDropdown] = useState(false);
  const [syncNotification, setSyncNotification] = useState<{
    type: 'success' | 'error';
    message: string;
    details?: string[];
  } | null>(null);
  const [newAgent, setNewAgent] = useState({
    name: '',
    description: '',
    icon: 'sparkles' as Agent['icon'],
    systemPrompt: 'You are a helpful AI assistant.',
    providerId: null as string | null,
  });

  const { providers } = useIntegrationsStore();
  const { agents, addAgent, updateAgent, deleteAgent, toggleAgent, setAgentProvider, fetchAgents } = useAgentsStore();
  const { servers, fetchServers } = useServersStore();

  // Fetch agents from database
  useEffect(() => {
    const loadAgents = async () => {
      try {
        const pathParts = window.location.pathname.split('/');
        const workspaceId = pathParts[pathParts.indexOf('workspace') + 1];
        
        if (!workspaceId) return;

        await fetchAgents(workspaceId);
        await fetchServers(workspaceId);
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      } finally {
        setLoading(false);
      }
    };

    loadAgents();
  }, [fetchAgents, fetchServers]);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setShowSyncDropdown(false);
    if (showSyncDropdown) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showSyncDropdown]);

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

  const handleSyncAgents = async (source: 'models' | 'server', serverId?: string) => {
    try {
      setSyncingAgents(true);
      setShowSyncDropdown(false);
      
      const pathParts = window.location.pathname.split('/');
      const workspaceId = pathParts[pathParts.indexOf('workspace') + 1];
      
      if (!workspaceId) {
        alert('No workspace selected');
        return;
      }

      let url: string;
      if (source === 'server' && serverId) {
        // Use dedicated ABI sync endpoint
        url = `${API_BASE}/api/abi/workspaces/${workspaceId}/abi-servers/${serverId}/sync`;
      } else {
        // Use model registry sync
        url = `${API_BASE}/api/agents/sync?workspace_id=${workspaceId}`;
      }

      const response = await authFetch(url, {
        method: 'POST',
      });

      if (response.ok) {
        const result = await response.json();
        // Refresh agents from database
        await fetchAgents(workspaceId);
        
        if (source === 'server') {
          // ABI sync result format
          const sourceName = servers.find(s => s.id === serverId)?.name || 'Server';
          setSyncNotification({
            type: 'success',
            message: `Successfully synced agents from ${sourceName}`,
            details: [
              `Discovered: ${result.agents_discovered || 0} agents`,
              `Created: ${result.agents_created || 0} new`,
              `Updated: ${result.agents_updated || 0} existing`,
              ...(result.agents && result.agents.length > 0 ? [`Agents: ${result.agents.join(', ')}`] : [])
            ]
          });
        } else {
          // Model registry result format
          setSyncNotification({
            type: 'success',
            message: 'Successfully synced agents from Model Registry',
            details: [
              `Created: ${result.created} agents`,
              `Skipped: ${result.skipped} (already exist)`,
              `Total models: ${result.total_models || 0}`
            ]
          });
        }
        
        // Auto-dismiss after 10 seconds
        setTimeout(() => setSyncNotification(null), 10000);
      } else {
        const error = await response.json();
        setSyncNotification({
          type: 'error',
          message: 'Failed to sync agents',
          details: [error.detail || 'Unknown error']
        });
      }
    } catch (error) {
      console.error('Failed to sync agents:', error);
      setSyncNotification({
        type: 'error',
        message: 'Failed to sync agents',
        details: [String(error)]
      });
    } finally {
      setSyncingAgents(false);
    }
  };

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

  const handleSelectAgent = (agent: Agent) => {
    // Toggle: collapse if already selected, expand if different
    if (selectedAgent?.id === agent.id) {
      setSelectedAgent(null);
      setIsEditingPrompt(false);
    } else {
      setSelectedAgent(agent);
      setEditedPrompt(agent.systemPrompt);
      setIsEditingPrompt(false);
    }
  };

  const handleUpdatePrompt = () => {
    if (selectedAgent) {
      updateAgent(selectedAgent.id, { systemPrompt: editedPrompt });
      setIsEditingPrompt(false);
      setSelectedAgent({ ...selectedAgent, systemPrompt: editedPrompt });
    }
  };

  const handleDeleteAgent = (id: string) => {
    if (confirm('Are you sure you want to delete this agent?')) {
      deleteAgent(id);
      if (selectedAgent?.id === id) {
        setSelectedAgent(null);
      }
    }
  };

  const handleProviderChange = (agentId: string, providerId: string | null) => {
    setAgentProvider(agentId, providerId);
    if (selectedAgent?.id === agentId) {
      setSelectedAgent({ ...selectedAgent, providerId });
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
    if (agent.isDefault) return 'Built-in';
    return 'Model Registry';
  };

  const getModelDisplay = (agent: Agent): string => {
    // For ABI agents, models are not exposed
    if (agent.provider === 'abi') {
      return 'Not exposed';
    }
    // Otherwise show model ID if available
    return agent.modelId || agent.providerId || 'Not assigned';
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
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowSyncDropdown(!showSyncDropdown);
              }}
              disabled={syncingAgents}
              className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
            >
              {syncingAgents ? (
                <RefreshCw size={16} className="animate-spin" />
              ) : (
                <Users size={16} />
              )}
              Sync Agents
              <ChevronDown size={14} />
            </button>
            
            {showSyncDropdown && !syncingAgents && (
              <div className="absolute right-0 top-full mt-1 z-10 min-w-[220px] rounded-lg border bg-popover shadow-lg">
                <div className="p-1">
                  <button
                    onClick={() => handleSyncAgents('models')}
                    className="flex w-full items-center gap-3 rounded px-3 py-2 text-left text-sm hover:bg-muted"
                  >
                    <Users size={16} className="text-muted-foreground" />
                    <div>
                      <div className="font-medium">Model Registry</div>
                      <div className="text-xs text-muted-foreground">Sync from centralized registry</div>
                    </div>
                  </button>
                  
                  {servers.filter(s => s.type === 'abi' && s.enabled).length > 0 && (
                    <div className="my-1 border-t" />
                  )}
                  
                  {servers.filter(s => s.type === 'abi' && s.enabled).map(server => (
                    <button
                      key={server.id}
                      onClick={() => handleSyncAgents('server', server.id)}
                      className="flex w-full items-center gap-3 rounded px-3 py-2 text-left text-sm hover:bg-muted"
                    >
                      <Server size={16} className="text-muted-foreground" />
                      <div>
                        <div className="font-medium">{server.name}</div>
                        <div className="text-xs text-muted-foreground truncate">{server.endpoint}</div>
                      </div>
                    </button>
                  ))}
                  
                  {servers.filter(s => s.type === 'abi' && s.enabled).length === 0 && (
                    <>
                      <div className="my-1 border-t" />
                      <div className="px-3 py-2 text-xs text-muted-foreground">
                        No ABI servers configured
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Agent
          </button>
        </div>
      </div>

      {/* Sync Notification */}
      {syncNotification && (
        <div className={cn(
          "rounded-lg border p-4",
          syncNotification.type === 'success' 
            ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950" 
            : "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950"
        )}>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                {syncNotification.type === 'success' ? (
                  <CheckCircle size={18} className="text-green-600 dark:text-green-400" />
                ) : (
                  <XCircle size={18} className="text-red-600 dark:text-red-400" />
                )}
                <h3 className={cn(
                  "font-medium",
                  syncNotification.type === 'success' 
                    ? "text-green-900 dark:text-green-100" 
                    : "text-red-900 dark:text-red-100"
                )}>
                  {syncNotification.message}
                </h3>
              </div>
              {syncNotification.details && syncNotification.details.length > 0 && (
                <ul className={cn(
                  "mt-2 ml-7 space-y-1 text-sm",
                  syncNotification.type === 'success' 
                    ? "text-green-700 dark:text-green-300" 
                    : "text-red-700 dark:text-red-300"
                )}>
                  {syncNotification.details.map((detail, idx) => (
                    <li key={idx}>• {detail}</li>
                  ))}
                </ul>
              )}
            </div>
            <button
              onClick={() => setSyncNotification(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}

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
            Create AI agents or sync them from your models
          </p>
          <div className="flex gap-2">
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowSyncDropdown(!showSyncDropdown);
                }}
                disabled={syncingAgents}
                className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
              >
                {syncingAgents ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <Users size={16} />
                )}
                Sync Agents
                <ChevronDown size={14} />
              </button>
              
              {showSyncDropdown && !syncingAgents && (
                <div className="absolute left-0 top-full mt-1 z-10 min-w-[220px] rounded-lg border bg-popover shadow-lg">
                  <div className="p-1">
                    <button
                      onClick={() => handleSyncAgents('models')}
                      className="flex w-full items-center gap-3 rounded px-3 py-2 text-left text-sm hover:bg-muted"
                    >
                      <Users size={16} className="text-muted-foreground" />
                      <div>
                        <div className="font-medium">Model Registry</div>
                        <div className="text-xs text-muted-foreground">Sync from centralized registry</div>
                      </div>
                    </button>
                    
                    {servers.filter(s => s.type === 'abi' && s.enabled).length > 0 && (
                      <div className="my-1 border-t" />
                    )}
                    
                    {servers.filter(s => s.type === 'abi' && s.enabled).map(server => (
                      <button
                        key={server.id}
                        onClick={() => handleSyncAgents('server', server.id)}
                        className="flex w-full items-center gap-3 rounded px-3 py-2 text-left text-sm hover:bg-muted"
                      >
                        <Server size={16} className="text-muted-foreground" />
                        <div>
                          <div className="font-medium">{server.name}</div>
                          <div className="text-xs text-muted-foreground truncate">{server.endpoint}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus size={16} />
              Add Agent
            </button>
          </div>
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
                  <th className="p-3 w-32"></th>
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
                    const Icon = iconMap[agent.icon];
                    const assignedProvider = getAssignedProvider(agent.providerId);
                    const isExpanded = selectedAgent?.id === agent.id;

                    return (
                      <Fragment key={agent.id}>
                        <tr
                          onClick={() => handleSelectAgent(agent)}
                          className={cn(
                            'cursor-pointer border-b transition-colors',
                            isExpanded ? 'bg-workspace-accent/10' : 'hover:bg-muted/30'
                          )}
                        >
                          <td className="p-3">
                            <div className="flex items-center gap-3">
                              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                                <Icon size={18} />
                              </div>
                              <div>
                                <p className="font-medium">{agent.name}</p>
                                <p className="text-xs text-muted-foreground">{agent.description}</p>
                              </div>
                            </div>
                          </td>
                          <td className="p-3">
                            <span className="text-sm text-muted-foreground capitalize">
                              {getAgentSource(agent)}
                            </span>
                          </td>
                          <td className="p-3">
                            {agent.provider === 'abi' ? (
                              <div className="flex items-center gap-2">
                                <Server size={14} className="text-muted-foreground" />
                                <span className="text-sm text-muted-foreground italic">
                                  {getModelDisplay(agent)}
                                </span>
                              </div>
                            ) : assignedProvider ? (
                              <div className="flex items-center gap-2">
                                <CheckCircle size={14} className="text-green-500" />
                                <span className="text-sm">{assignedProvider.model}</span>
                              </div>
                            ) : agent.providerId || agent.modelId ? (
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
                          <td className="p-3">
                            <span className={cn(
                              "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                              agent.isDefault
                                ? "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300"
                                : "bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300"
                            )}>
                              {agent.isDefault ? 'Default' : 'Custom'}
                            </span>
                          </td>
                          <td className="p-3">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleAgent(agent.id);
                              }}
                              className={cn(
                                "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                                agent.enabled ? "bg-primary" : "bg-muted"
                              )}
                              title={agent.enabled ? "Disable agent" : "Enable agent"}
                            >
                              <span
                                className={cn(
                                  "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                                  agent.enabled ? "translate-x-5" : "translate-x-0.5"
                                )}
                              />
                            </button>
                          </td>
                          <td className="p-3">
                            {!agent.isDefault && (
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
                            )}
                          </td>
                        </tr>
                        
                        {/* Expanded details row */}
                        {isExpanded && (
                          <tr key={`${agent.id}-details`}>
                            <td colSpan={6} className="p-0 border-b bg-muted/20">
                              <div className="p-4 space-y-4">
                                {/* System Prompt */}
                                <div>
                                  <div className="mb-2 flex items-center justify-between">
                                    <label className="text-sm font-medium">System Prompt</label>
                                    {!isEditingPrompt ? (
                                      <button
                                        onClick={() => {
                                          setIsEditingPrompt(true);
                                          setEditedPrompt(agent.systemPrompt);
                                        }}
                                        className="flex items-center gap-1 rounded px-2 py-1 text-xs hover:bg-muted"
                                      >
                                        <Pencil size={12} />
                                        Edit
                                      </button>
                                    ) : (
                                      <div className="flex gap-2">
                                        <button
                                          onClick={() => {
                                            updateAgent(agent.id, { systemPrompt: editedPrompt });
                                            setIsEditingPrompt(false);
                                          }}
                                          className="flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90"
                                        >
                                          <Save size={12} />
                                          Save
                                        </button>
                                        <button
                                          onClick={() => setIsEditingPrompt(false)}
                                          className="flex items-center gap-1 rounded px-2 py-1 text-xs hover:bg-muted"
                                        >
                                          <X size={12} />
                                          Cancel
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                  {isEditingPrompt ? (
                                    <textarea
                                      value={editedPrompt}
                                      onChange={(e) => setEditedPrompt(e.target.value)}
                                      rows={6}
                                      className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                                    />
                                  ) : (
                                    <div className="rounded-lg border bg-background p-3 text-sm text-muted-foreground whitespace-pre-wrap">
                                      {agent.systemPrompt || 'No system prompt set'}
                                    </div>
                                  )}
                                </div>

                                {/* Provider Assignment */}
                                <div>
                                  <label className="mb-2 block text-sm font-medium">Assigned Provider</label>
                                  <select
                                    value={agent.providerId || ''}
                                    onChange={(e) => setAgentProvider(agent.id, e.target.value || null)}
                                    className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                                  >
                                    <option value="">No provider</option>
                                    {enabledProviders.map((p) => (
                                      <option key={p.id} value={p.id}>
                                        {p.name} - {p.model}
                                      </option>
                                    ))}
                                  </select>
                                </div>

                                {/* Agent Metadata */}
                                <div className="grid grid-cols-2 gap-4 pt-2 border-t">
                                  <div>
                                    <p className="text-xs text-muted-foreground">Created</p>
                                    <p className="text-sm">{new Date(agent.createdAt).toLocaleDateString()}</p>
                                  </div>
                                  <div>
                                    <p className="text-xs text-muted-foreground">Updated</p>
                                    <p className="text-sm">{new Date(agent.updatedAt).toLocaleDateString()}</p>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
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
