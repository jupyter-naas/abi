'use client';

import { useState, useEffect } from 'react';
import {
  Server,
  Plus,
  Trash2,
  RefreshCw,
  Check,
  X,
  Circle,
  Wifi,
  WifiOff,
  Loader2,
  ExternalLink,
  Settings,
  Cloud,
  HardDrive,
  Pencil,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl, getOllamaUrl } from '@/lib/config';
import {
  useServersStore,
  type Server as ServerType,
  type ServerType as ServerTypeEnum,
  serverTypeLabels,
  serverTypeDescriptions,
} from '@/stores/servers';
import { useWorkspaceStore } from '@/stores/workspace';

const serverTypeOptions: { id: ServerTypeEnum; label: string; description: string }[] = [
  { id: 'ollama', label: 'Ollama', description: 'Run open-source models locally' },
  { id: 'abi', label: 'ABI Server', description: 'NEXUS inference server' },
  { id: 'vllm', label: 'vLLM', description: 'High-throughput serving' },
  { id: 'llamacpp', label: 'llama.cpp', description: 'Efficient CPU/GPU inference' },
  { id: 'custom', label: 'Custom', description: 'OpenAI-compatible server' },
];

const statusColors: Record<ServerType['status'], string> = {
  online: 'text-green-500',
  offline: 'text-red-500',
  checking: 'text-yellow-500',
  unknown: 'text-muted-foreground',
};

const statusLabels: Record<ServerType['status'], string> = {
  online: 'Online',
  offline: 'Offline',
  checking: 'Checking...',
  unknown: 'Unknown',
};

export function ServersPanel() {
  const {
    servers,
    loading,
    fetchServers,
    addServer,
    updateServer,
    deleteServer,
    toggleServer,
    checkServerHealth,
    checkAllServers,
    setCurrentWorkspace,
  } = useServersStore();

  const { currentWorkspaceId } = useWorkspaceStore();

  const [mounted, setMounted] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [checkingAll, setCheckingAll] = useState(false);

  // New server form
  const [newServer, setNewServer] = useState({
    name: '',
    type: 'ollama' as ServerTypeEnum,
    endpoint: '',
    description: '',
    apiKey: '',
    healthPath: '',
    modelsPath: '',
  });

  // Edit form state
  const [editForm, setEditForm] = useState({
    name: '',
    endpoint: '',
    description: '',
    apiKey: '',
    healthPath: '',
    modelsPath: '',
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch servers when workspace changes
  useEffect(() => {
    if (mounted && currentWorkspaceId) {
      setCurrentWorkspace(currentWorkspaceId);
      fetchServers(currentWorkspaceId);
    }
  }, [mounted, currentWorkspaceId, fetchServers, setCurrentWorkspace]);

  // Check all servers after fetching
  useEffect(() => {
    if (mounted && servers.length > 0) {
      checkAllServers();
    }
  }, [mounted, servers.length > 0 ? servers[0]?.id : null]);

  const handleAdd = async () => {
    if (!newServer.name.trim() || !newServer.endpoint.trim()) return;

    try {
      await addServer({
        name: newServer.name.trim(),
        type: newServer.type,
        endpoint: newServer.endpoint.trim().replace(/\/$/, ''), // Remove trailing slash
        description: newServer.description.trim(),
        enabled: true,
        apiKey: newServer.apiKey || undefined,
        healthPath: newServer.healthPath || undefined,
        modelsPath: newServer.modelsPath || undefined,
      });

      setNewServer({ name: '', type: 'ollama', endpoint: '', description: '', apiKey: '', healthPath: '', modelsPath: '' });
      setShowAddForm(false);
    } catch (error) {
      console.error('Failed to add server:', error);
      alert('Failed to add server. Please try again.');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this server?')) {
      try {
        await deleteServer(id);
      } catch (error) {
        console.error('Failed to delete server:', error);
        alert('Failed to delete server. Please try again.');
      }
    }
  };

  const handleEdit = (server: ServerType) => {
    setEditingId(server.id);
    setEditForm({
      name: server.name,
      endpoint: server.endpoint,
      description: server.description || '',
      apiKey: server.apiKey || '',
      healthPath: server.healthPath || '',
      modelsPath: server.modelsPath || '',
    });
  };

  const handleSaveEdit = async () => {
    if (!editingId || !editForm.name.trim() || !editForm.endpoint.trim()) return;
    
    try {
      await updateServer(editingId, {
        name: editForm.name.trim(),
        endpoint: editForm.endpoint.trim().replace(/\/$/, ''),
        description: editForm.description.trim(),
        apiKey: editForm.apiKey || undefined,
        healthPath: editForm.healthPath || undefined,
        modelsPath: editForm.modelsPath || undefined,
      });
      
      setEditingId(null);
      setEditForm({ name: '', endpoint: '', description: '', apiKey: '', healthPath: '', modelsPath: '' });
    } catch (error) {
      console.error('Failed to update server:', error);
      alert('Failed to update server. Please try again.');
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditForm({ name: '', endpoint: '', description: '', apiKey: '', healthPath: '', modelsPath: '' });
  };

  const handleCheckAll = async () => {
    setCheckingAll(true);
    await checkAllServers();
    setCheckingAll(false);
  };

  const handleCheckOne = async (id: string) => {
    await checkServerHealth(id);
  };

  // Set default endpoint based on type
  const handleTypeChange = (type: ServerTypeEnum) => {
    const defaultEndpoints: Record<ServerTypeEnum, string> = {
      ollama: getOllamaUrl(),
      abi: getApiUrl(),
      vllm: getApiUrl(),
      llamacpp: 'http://localhost:8080',
      custom: getApiUrl(),
    };

    const defaultHealthPaths: Record<ServerTypeEnum, string> = {
      ollama: '/api/tags',
      abi: '/health',
      vllm: '/health',
      llamacpp: '/health',
      custom: '/health',
    };

    const defaultModelsPaths: Record<ServerTypeEnum, string> = {
      ollama: '/api/tags',
      abi: '/api/v1/models',
      vllm: '/v1/models',
      llamacpp: '/v1/models',
      custom: '/models',
    };

    setNewServer({
      ...newServer,
      type,
      endpoint: newServer.endpoint || defaultEndpoints[type],
      healthPath: defaultHealthPaths[type],
      modelsPath: defaultModelsPaths[type],
    });
  };

  if (!mounted || loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Servers</h2>
            <p className="text-sm text-muted-foreground">Loading...</p>
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
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Servers</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {servers.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Configure inference servers for running AI models
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCheckAll}
            disabled={checkingAll || servers.length === 0}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw size={16} className={cn(checkingAll && 'animate-spin')} />
            Check All
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Server
          </button>
        </div>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <h3 className="mb-4 font-medium">Add New Server</h3>
          <div className="grid gap-4">
            {/* Server Type */}
            <div>
              <label className="mb-2 block text-sm font-medium">Server Type</label>
              <div className="grid grid-cols-5 gap-2">
                {serverTypeOptions.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => handleTypeChange(opt.id)}
                    className={cn(
                      'flex flex-col items-center gap-1 rounded-lg border p-3 text-center transition-all',
                      newServer.type === opt.id
                        ? 'border-primary bg-primary/10'
                        : 'hover:bg-muted'
                    )}
                  >
                    {opt.id === 'ollama' || opt.id === 'llamacpp' ? (
                      <HardDrive size={20} className={newServer.type === opt.id ? 'text-primary' : 'text-muted-foreground'} />
                    ) : (
                      <Cloud size={20} className={newServer.type === opt.id ? 'text-primary' : 'text-muted-foreground'} />
                    )}
                    <span className={cn('text-xs font-medium', newServer.type === opt.id ? 'text-primary' : '')}>
                      {opt.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Name *</label>
                <input
                  type="text"
                  value={newServer.name}
                  onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                  placeholder="e.g., Local Ollama"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Endpoint *</label>
                <input
                  type="text"
                  value={newServer.endpoint}
                  onChange={(e) => setNewServer({ ...newServer, endpoint: e.target.value })}
                  placeholder="http://localhost:11434"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input
                type="text"
                value={newServer.description}
                onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
                placeholder="Optional description"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">API Key (optional)</label>
              <input
                type="password"
                value={newServer.apiKey}
                onChange={(e) => setNewServer({ ...newServer, apiKey: e.target.value })}
                placeholder="For authenticated servers"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Health Check Path (optional)</label>
                <input
                  type="text"
                  value={newServer.healthPath}
                  onChange={(e) => setNewServer({ ...newServer, healthPath: e.target.value })}
                  placeholder="e.g., /health"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Models List Path (optional)</label>
                <input
                  type="text"
                  value={newServer.modelsPath}
                  onChange={(e) => setNewServer({ ...newServer, modelsPath: e.target.value })}
                  placeholder="e.g., /api/v1/models"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setNewServer({ name: '', type: 'ollama', endpoint: '', description: '', apiKey: '', healthPath: '', modelsPath: '' });
                }}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={!newServer.name.trim() || !newServer.endpoint.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Add Server
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Servers List */}
      {servers.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <Server size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No servers configured</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Add inference servers to run AI models locally or remotely
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
          >
            <Plus size={16} />
            Add Server
          </button>
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50 text-left text-sm">
                <th className="p-4 font-medium">Server</th>
                <th className="p-4 font-medium w-24">Type</th>
                <th className="p-4 font-medium">Endpoint</th>
                <th className="p-4 font-medium w-24">Status</th>
                <th className="p-4 font-medium w-24">Enabled</th>
                <th className="p-4 w-32"></th>
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => (
                <tr key={server.id} className="border-b last:border-0">
                  {editingId === server.id ? (
                    // Edit mode
                    <>
                      <td className="p-4" colSpan={6}>
                        <div className="space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="mb-1 block text-xs font-medium">Name</label>
                              <input
                                type="text"
                                value={editForm.name}
                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                placeholder="Name"
                                className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary/30"
                              />
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium">Endpoint</label>
                              <input
                                type="text"
                                value={editForm.endpoint}
                                onChange={(e) => setEditForm({ ...editForm, endpoint: e.target.value })}
                                placeholder="Endpoint"
                                className="w-full rounded border bg-background px-2 py-1.5 text-sm font-mono outline-none focus:ring-1 focus:ring-primary/30"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="mb-1 block text-xs font-medium">Description</label>
                            <input
                              type="text"
                              value={editForm.description}
                              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                              placeholder="Description (optional)"
                              className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary/30"
                            />
                          </div>
                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <label className="mb-1 block text-xs font-medium">API Key</label>
                              <input
                                type="password"
                                value={editForm.apiKey}
                                onChange={(e) => setEditForm({ ...editForm, apiKey: e.target.value })}
                                placeholder="Optional"
                                className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary/30"
                              />
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium">Health Path</label>
                              <input
                                type="text"
                                value={editForm.healthPath}
                                onChange={(e) => setEditForm({ ...editForm, healthPath: e.target.value })}
                                placeholder="e.g., /health"
                                className="w-full rounded border bg-background px-2 py-1.5 text-sm font-mono outline-none focus:ring-1 focus:ring-primary/30"
                              />
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium">Models Path</label>
                              <input
                                type="text"
                                value={editForm.modelsPath}
                                onChange={(e) => setEditForm({ ...editForm, modelsPath: e.target.value })}
                                placeholder="e.g., /api/v1/models"
                                className="w-full rounded border bg-background px-2 py-1.5 text-sm font-mono outline-none focus:ring-1 focus:ring-primary/30"
                              />
                            </div>
                          </div>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">Enabled:</span>
                              <button
                                onClick={() => toggleServer(server.id)}
                                className={cn(
                                  'flex h-6 w-11 items-center rounded-full p-0.5 transition-colors',
                                  server.enabled ? 'bg-primary' : 'bg-muted-foreground/30'
                                )}
                              >
                                <div
                                  className={cn(
                                    'h-5 w-5 rounded-full bg-white shadow-sm transition-transform',
                                    server.enabled && 'translate-x-5'
                                  )}
                                />
                              </button>
                            </div>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={handleSaveEdit}
                                disabled={!editForm.name.trim() || !editForm.endpoint.trim()}
                                className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                              >
                                Save
                              </button>
                              <button
                                onClick={handleCancelEdit}
                                className="rounded px-3 py-1.5 text-sm hover:bg-muted"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>
                    </>
                  ) : (
                    // View mode
                    <>
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                            {server.type === 'ollama' || server.type === 'llamacpp' ? (
                              <HardDrive size={18} className="text-muted-foreground" />
                            ) : (
                              <Cloud size={18} className="text-muted-foreground" />
                            )}
                          </div>
                          <div>
                            <span className="font-medium">{server.name}</span>
                            {server.description && (
                              <p className="text-xs text-muted-foreground">{server.description}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-sm text-muted-foreground">
                        {serverTypeLabels[server.type]}
                      </td>
                      <td className="p-4">
                        <code className="rounded bg-secondary px-2 py-1 text-xs font-mono">
                          {server.endpoint}
                        </code>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          {server.status === 'checking' ? (
                            <Loader2 size={14} className="animate-spin text-yellow-500" />
                          ) : server.status === 'online' ? (
                            <Wifi size={14} className="text-green-500" />
                          ) : server.status === 'offline' ? (
                            <WifiOff size={14} className="text-red-500" />
                          ) : (
                            <Circle size={14} className="text-muted-foreground" />
                          )}
                          <span className={cn('text-xs', statusColors[server.status])}>
                            {statusLabels[server.status]}
                          </span>
                        </div>
                      </td>
                      <td className="p-4">
                        <button
                          onClick={() => toggleServer(server.id)}
                          className={cn(
                            'flex h-6 w-11 items-center rounded-full p-0.5 transition-colors',
                            server.enabled ? 'bg-primary' : 'bg-muted-foreground/30'
                          )}
                        >
                          <div
                            className={cn(
                              'h-5 w-5 rounded-full bg-white shadow-sm transition-transform',
                              server.enabled && 'translate-x-5'
                            )}
                          />
                        </button>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleCheckOne(server.id)}
                            disabled={server.status === 'checking'}
                            className="rounded p-1.5 hover:bg-muted disabled:opacity-50"
                            title="Check status"
                          >
                            <RefreshCw
                              size={14}
                              className={cn(server.status === 'checking' && 'animate-spin')}
                            />
                          </button>
                          <button
                            onClick={() => handleEdit(server)}
                            className="rounded p-1.5 hover:bg-muted"
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </button>
                          <a
                            href={server.endpoint}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded p-1.5 hover:bg-muted"
                            title="Open endpoint"
                          >
                            <ExternalLink size={14} />
                          </a>
                          <button
                            onClick={() => handleDelete(server.id)}
                            className="rounded p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
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
      )}

      {/* Info */}
      <div className="rounded-lg border bg-muted/30 p-4">
        <h3 className="mb-2 font-medium">Supported Server Types</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {serverTypeOptions.map((opt) => (
            <div key={opt.id} className="flex items-start gap-2">
              <div className="mt-0.5 flex h-5 w-5 items-center justify-center rounded bg-muted">
                {opt.id === 'ollama' || opt.id === 'llamacpp' ? (
                  <HardDrive size={12} className="text-muted-foreground" />
                ) : (
                  <Cloud size={12} className="text-muted-foreground" />
                )}
              </div>
              <div>
                <p className="font-medium">{opt.label}</p>
                <p className="text-xs text-muted-foreground">{opt.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
