'use client';

import { useState, useEffect } from 'react';
import {
  Server,
  Plus,
  Trash2,
  RefreshCw,
  Circle,
  Wifi,
  WifiOff,
  Loader2,
  ExternalLink,
  Cloud,
  HardDrive,
  Pencil,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { Input } from '@/components/ui/input';
import {
  SettingsEmpty,
  SettingsField,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
  settingsTable,
} from '@/components/settings/settings-ui';
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
  online: 'text-primary',
  offline: 'text-destructive',
  checking: 'text-amber-600 dark:text-amber-400',
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
  const [actionError, setActionError] = useState<string | null>(null);
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();

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
  const firstServerId = servers.length > 0 ? servers[0]?.id : null;
  useEffect(() => {
    if (mounted && servers.length > 0) {
      checkAllServers();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, firstServerId]);

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
      setActionError('Failed to add server. Please try again.');
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await confirmDelete({
      title: 'Delete server?',
      description: 'Are you sure you want to delete this server?',
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    try {
      await deleteServer(id);
    } catch (error) {
      console.error('Failed to delete server:', error);
      setActionError('Failed to delete server. Please try again.');
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
      setActionError('Failed to update server. Please try again.');
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

  // Only block on the first load; later refetches keep showing the cached list.
  if (!mounted || (loading && servers.length === 0)) {
    return <SettingsLoading label="Loading servers…" />;
  }

  const resetNewServer = () =>
    setNewServer({ name: '', type: 'ollama', endpoint: '', description: '', apiKey: '', healthPath: '', modelsPath: '' });

  const serverIcon = (type: ServerTypeEnum, size: number, className = 'text-muted-foreground') =>
    type === 'ollama' || type === 'llamacpp' ? (
      <HardDrive size={size} className={className} />
    ) : (
      <Cloud size={size} className={className} />
    );

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title={
          <span className="flex items-center gap-2">
            Servers
            <Badge>{servers.length}</Badge>
          </span>
        }
        description="Configure inference servers for running AI models"
        actions={
          <>
            <Button variant="secondary" onClick={handleCheckAll} disabled={checkingAll || servers.length === 0}>
              <RefreshCw size={16} className={cn(checkingAll && 'animate-spin')} />
              Check All
            </Button>
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Add Server
            </Button>
          </>
        }
      />

      {actionError && <SettingsNotice tone="error">{actionError}</SettingsNotice>}

      {showAddForm && (
        <SettingsSection title="Add New Server">
          <div className="grid gap-4">
            <SettingsField label="Server Type">
              <div className="grid grid-cols-5 gap-2">
                {serverTypeOptions.map((opt) => {
                  const active = newServer.type === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => handleTypeChange(opt.id)}
                      className={cn(
                        'flex flex-col items-center gap-1 border p-3 text-center transition-colors',
                        active ? 'border-primary bg-primary/10' : 'border-border hover:bg-muted'
                      )}
                    >
                      {serverIcon(opt.id, 20, active ? 'text-primary' : 'text-muted-foreground')}
                      <span className={cn('text-xs font-medium', active && 'text-primary')}>{opt.label}</span>
                    </button>
                  );
                })}
              </div>
            </SettingsField>

            <div className="grid grid-cols-2 gap-4">
              <SettingsField label="Name *">
                <Input
                  type="text"
                  value={newServer.name}
                  onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                  placeholder="e.g., Local Ollama"
                />
              </SettingsField>
              <SettingsField label="Endpoint *">
                <Input
                  type="text"
                  value={newServer.endpoint}
                  onChange={(e) => setNewServer({ ...newServer, endpoint: e.target.value })}
                  placeholder="http://localhost:11434"
                  className="font-mono"
                />
              </SettingsField>
            </div>

            <SettingsField label="Description">
              <Input
                type="text"
                value={newServer.description}
                onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
                placeholder="Optional description"
              />
            </SettingsField>

            <SettingsField label="API Key (optional)">
              <Input
                type="password"
                value={newServer.apiKey}
                onChange={(e) => setNewServer({ ...newServer, apiKey: e.target.value })}
                placeholder="For authenticated servers"
              />
            </SettingsField>

            <div className="grid grid-cols-2 gap-4">
              <SettingsField label="Health Check Path (optional)">
                <Input
                  type="text"
                  value={newServer.healthPath}
                  onChange={(e) => setNewServer({ ...newServer, healthPath: e.target.value })}
                  placeholder="e.g., /health"
                  className="font-mono"
                />
              </SettingsField>
              <SettingsField label="Models List Path (optional)">
                <Input
                  type="text"
                  value={newServer.modelsPath}
                  onChange={(e) => setNewServer({ ...newServer, modelsPath: e.target.value })}
                  placeholder="e.g., /api/v1/models"
                  className="font-mono"
                />
              </SettingsField>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowAddForm(false);
                  resetNewServer();
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleAdd} disabled={!newServer.name.trim() || !newServer.endpoint.trim()}>
                Add Server
              </Button>
            </div>
          </div>
        </SettingsSection>
      )}

      {servers.length === 0 ? (
        <SettingsEmpty
          icon={<Server size={40} className="opacity-40" />}
          title="No servers configured"
          description="Add inference servers to run AI models locally or remotely"
          action={
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Add Server
            </Button>
          }
        />
      ) : (
        <div className={settingsTable.wrapper}>
          <table className={settingsTable.table}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Server</th>
                <th className={cn(settingsTable.th, 'w-24')}>Type</th>
                <th className={settingsTable.th}>Endpoint</th>
                <th className={cn(settingsTable.th, 'w-28')}>Status</th>
                <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
                <th className={cn(settingsTable.th, 'w-40')}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => (
                <tr key={server.id} className={settingsTable.row}>
                  {editingId === server.id ? (
                    <td className={settingsTable.td} colSpan={6}>
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <SettingsField label="Name">
                            <Input
                              type="text"
                              value={editForm.name}
                              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                              placeholder="Name"
                            />
                          </SettingsField>
                          <SettingsField label="Endpoint">
                            <Input
                              type="text"
                              value={editForm.endpoint}
                              onChange={(e) => setEditForm({ ...editForm, endpoint: e.target.value })}
                              placeholder="Endpoint"
                              className="font-mono"
                            />
                          </SettingsField>
                        </div>
                        <SettingsField label="Description">
                          <Input
                            type="text"
                            value={editForm.description}
                            onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                            placeholder="Description (optional)"
                          />
                        </SettingsField>
                        <div className="grid grid-cols-3 gap-3">
                          <SettingsField label="API Key">
                            <Input
                              type="password"
                              value={editForm.apiKey}
                              onChange={(e) => setEditForm({ ...editForm, apiKey: e.target.value })}
                              placeholder="Optional"
                            />
                          </SettingsField>
                          <SettingsField label="Health Path">
                            <Input
                              type="text"
                              value={editForm.healthPath}
                              onChange={(e) => setEditForm({ ...editForm, healthPath: e.target.value })}
                              placeholder="e.g., /health"
                              className="font-mono"
                            />
                          </SettingsField>
                          <SettingsField label="Models Path">
                            <Input
                              type="text"
                              value={editForm.modelsPath}
                              onChange={(e) => setEditForm({ ...editForm, modelsPath: e.target.value })}
                              placeholder="e.g., /api/v1/models"
                              className="font-mono"
                            />
                          </SettingsField>
                        </div>
                        <div className="flex items-center justify-between">
                          <Checkbox
                            checked={server.enabled}
                            onCheckedChange={() => toggleServer(server.id)}
                            label="Enabled"
                          />
                          <div className="flex items-center gap-2">
                            <Button variant="secondary" onClick={handleCancelEdit}>
                              Cancel
                            </Button>
                            <Button
                              onClick={handleSaveEdit}
                              disabled={!editForm.name.trim() || !editForm.endpoint.trim()}
                            >
                              Save
                            </Button>
                          </div>
                        </div>
                      </div>
                    </td>
                  ) : (
                    <>
                      <td className={settingsTable.td}>
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center bg-muted">
                            {serverIcon(server.type, 18)}
                          </div>
                          <div>
                            <span className="font-medium">{server.name}</span>
                            {server.description && (
                              <p className="text-xs text-muted-foreground">{server.description}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className={cn(settingsTable.td, 'text-muted-foreground')}>
                        {serverTypeLabels[server.type]}
                      </td>
                      <td className={settingsTable.td}>
                        <code className="bg-muted px-2 py-1 font-mono text-xs">{server.endpoint}</code>
                      </td>
                      <td className={settingsTable.td}>
                        <div className={cn('flex items-center gap-2', statusColors[server.status])}>
                          {server.status === 'checking' ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : server.status === 'online' ? (
                            <Wifi size={14} />
                          ) : server.status === 'offline' ? (
                            <WifiOff size={14} />
                          ) : (
                            <Circle size={14} />
                          )}
                          <span className="text-xs">{statusLabels[server.status]}</span>
                        </div>
                      </td>
                      <td className={settingsTable.td}>
                        <Checkbox
                          checked={server.enabled}
                          onCheckedChange={() => toggleServer(server.id)}
                          aria-label={server.enabled ? 'Disable server' : 'Enable server'}
                          title={server.enabled ? 'Disable server' : 'Enable server'}
                        />
                      </td>
                      <td className={settingsTable.td}>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleCheckOne(server.id)}
                            disabled={server.status === 'checking'}
                            title="Check status"
                          >
                            <RefreshCw size={14} className={cn(server.status === 'checking' && 'animate-spin')} />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => handleEdit(server)} title="Edit">
                            <Pencil size={14} />
                          </Button>
                          <a
                            href={server.endpoint}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={buttonVariants({ variant: 'ghost', size: 'icon' })}
                            title="Open endpoint"
                          >
                            <ExternalLink size={14} />
                          </a>
                          <Button
                            variant="destructive-ghost"
                            size="icon"
                            onClick={() => void handleDelete(server.id)}
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </Button>
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

      <SettingsSection title="Supported Server Types">
        <div className="grid grid-cols-2 gap-3 text-sm">
          {serverTypeOptions.map((opt) => (
            <div key={opt.id} className="flex items-start gap-2">
              <div className="mt-0.5 flex h-5 w-5 items-center justify-center bg-muted">{serverIcon(opt.id, 12)}</div>
              <div>
                <p className="font-medium">{opt.label}</p>
                <p className="text-xs text-muted-foreground">{opt.description}</p>
              </div>
            </div>
          ))}
        </div>
      </SettingsSection>
      {confirmDialog}
    </div>
  );
}
