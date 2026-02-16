import { create } from 'zustand';
import { getOllamaUrl, getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

const API_BASE = getApiUrl();

export type ServerType = 'ollama' | 'abi' | 'vllm' | 'llamacpp' | 'custom';

export type ServerStatus = 'online' | 'offline' | 'checking' | 'unknown';

export interface Server {
  id: string;
  name: string;
  type: ServerType;
  endpoint: string;        // Base URL (e.g., http://localhost:11434)
  description: string;
  enabled: boolean;
  status: ServerStatus;
  lastChecked: Date | null;
  // Optional auth
  apiKey?: string;
  // Health check endpoint (relative to base)
  healthPath?: string;
  // Models endpoint (relative to base)
  modelsPath?: string;
  createdAt: Date;
  updatedAt: Date;
}

interface ServersState {
  servers: Server[];
  loading: boolean;
  currentWorkspaceId: string | null;
  
  // Actions
  setCurrentWorkspace: (workspaceId: string) => void;
  fetchServers: (workspaceId: string) => Promise<void>;
  addServer: (server: Omit<Server, 'id' | 'status' | 'lastChecked' | 'createdAt' | 'updatedAt'>) => Promise<string>;
  updateServer: (id: string, updates: Partial<Omit<Server, 'id' | 'createdAt'>>) => Promise<void>;
  deleteServer: (id: string) => Promise<void>;
  toggleServer: (id: string) => Promise<void>;
  getServer: (id: string) => Server | undefined;
  setServerStatus: (id: string, status: ServerStatus) => void;
  
  // Health check
  checkServerHealth: (id: string) => Promise<boolean>;
  checkAllServers: () => Promise<void>;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

// Default server configurations
const serverDefaults: Record<ServerType, { healthPath: string; modelsPath: string }> = {
  ollama: { healthPath: '/api/tags', modelsPath: '/api/tags' },
  abi: { healthPath: '/health', modelsPath: '/api/v1/models' },
  vllm: { healthPath: '/health', modelsPath: '/v1/models' },
  llamacpp: { healthPath: '/health', modelsPath: '/v1/models' },
  custom: { healthPath: '/health', modelsPath: '/models' },
};

export const useServersStore = create<ServersState>()((set, get) => ({
  servers: [],
  loading: false,
  currentWorkspaceId: null,

  setCurrentWorkspace: (workspaceId: string) => {
    set({ currentWorkspaceId: workspaceId });
  },

  fetchServers: async (workspaceId: string) => {
    set({ loading: true, currentWorkspaceId: workspaceId });
    
    try {
      const response = await authFetch(`${API_BASE}/api/workspaces/${workspaceId}/servers`);

      if (!response.ok) {
        throw new Error('Failed to fetch servers');
      }

      const serversData = await response.json();
      
      // Map API response to store format
      const servers: Server[] = serversData.map((s: any) => ({
        id: s.id,
        name: s.name,
        type: s.type,
        endpoint: s.endpoint,
        description: s.description || '',
        enabled: s.enabled,
        status: 'unknown' as ServerStatus,
        lastChecked: null,
        apiKey: s.api_key,
        healthPath: s.health_path,
        modelsPath: s.models_path,
        createdAt: new Date(s.created_at),
        updatedAt: new Date(s.updated_at),
      }));

      set({ servers, loading: false });
      
      // Automatically check health of all enabled servers
      setTimeout(() => {
        get().checkAllServers();
      }, 100);
    } catch (error) {
      console.error('Failed to fetch servers:', error);
      set({ servers: [], loading: false });
    }
  },

  addServer: async (server) => {
    const { currentWorkspaceId } = get();
    if (!currentWorkspaceId) {
      throw new Error('No workspace selected');
    }

    const defaults = serverDefaults[server.type];
    
    try {
      const response = await authFetch(`${API_BASE}/api/workspaces/${currentWorkspaceId}/servers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: server.name,
          type: server.type,
          endpoint: server.endpoint,
          description: server.description,
          enabled: server.enabled,
          api_key: server.apiKey,
          health_path: server.healthPath || defaults.healthPath,
          models_path: server.modelsPath || defaults.modelsPath,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add server');
      }

      const newServerData = await response.json();
      
      const newServer: Server = {
        id: newServerData.id,
        name: newServerData.name,
        type: newServerData.type,
        endpoint: newServerData.endpoint,
        description: newServerData.description || '',
        enabled: newServerData.enabled,
        status: 'unknown',
        lastChecked: null,
        apiKey: newServerData.api_key,
        healthPath: newServerData.health_path,
        modelsPath: newServerData.models_path,
        createdAt: new Date(newServerData.created_at),
        updatedAt: new Date(newServerData.updated_at),
      };

      set((state) => ({
        servers: [...state.servers, newServer],
      }));
      
      return newServer.id;
    } catch (error) {
      console.error('Failed to add server:', error);
      throw error;
    }
  },

  updateServer: async (id, updates) => {
    const { currentWorkspaceId } = get();
    if (!currentWorkspaceId) {
      throw new Error('No workspace selected');
    }

    try {
      const response = await authFetch(`${API_BASE}/api/workspaces/${currentWorkspaceId}/servers/${id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: updates.name,
          endpoint: updates.endpoint,
          description: updates.description,
          enabled: updates.enabled,
          api_key: updates.apiKey,
          health_path: updates.healthPath,
          models_path: updates.modelsPath,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update server');
      }

      const updatedServerData = await response.json();

      set((state) => ({
        servers: state.servers.map((s) =>
          s.id === id
            ? {
                ...s,
                name: updatedServerData.name,
                endpoint: updatedServerData.endpoint,
                description: updatedServerData.description || '',
                enabled: updatedServerData.enabled,
                apiKey: updatedServerData.api_key,
                healthPath: updatedServerData.health_path,
                modelsPath: updatedServerData.models_path,
                updatedAt: new Date(updatedServerData.updated_at),
              }
            : s
        ),
      }));
    } catch (error) {
      console.error('Failed to update server:', error);
      throw error;
    }
  },

  deleteServer: async (id) => {
    const { currentWorkspaceId } = get();
    if (!currentWorkspaceId) {
      throw new Error('No workspace selected');
    }

    try {
      const response = await authFetch(`${API_BASE}/api/workspaces/${currentWorkspaceId}/servers/${id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete server');
      }

      set((state) => ({
        servers: state.servers.filter((s) => s.id !== id),
      }));
    } catch (error) {
      console.error('Failed to delete server:', error);
      throw error;
    }
  },

  toggleServer: async (id) => {
    const server = get().getServer(id);
    if (!server) return;

    await get().updateServer(id, { enabled: !server.enabled });
  },

  getServer: (id) => {
    return get().servers.find((s) => s.id === id);
  },

  setServerStatus: (id, status) => {
    set((state) => ({
      servers: state.servers.map((s) =>
        s.id === id ? { ...s, status, lastChecked: new Date() } : s
      ),
    }));
  },

  checkServerHealth: async (id) => {
    const server = get().getServer(id);
    if (!server) return false;

    get().setServerStatus(id, 'checking');

    try {
      const healthUrl = `${server.endpoint}${server.healthPath || '/health'}`;
      const response = await fetch(healthUrl, {
        method: 'GET',
        headers: server.apiKey ? { 'Authorization': `Bearer ${server.apiKey}` } : {},
        signal: AbortSignal.timeout(5000),
      });

      const isOnline = response.ok;
      get().setServerStatus(id, isOnline ? 'online' : 'offline');
      return isOnline;
    } catch {
      get().setServerStatus(id, 'offline');
      return false;
    }
  },

  checkAllServers: async () => {
    const { servers, checkServerHealth } = get();
    await Promise.all(
      servers.filter((s) => s.enabled).map((s) => checkServerHealth(s.id))
    );
  },
}));

// Server type labels and icons
export const serverTypeLabels: Record<ServerType, string> = {
  ollama: 'Ollama',
  abi: 'ABI Server',
  vllm: 'vLLM',
  llamacpp: 'llama.cpp',
  custom: 'Custom',
};

export const serverTypeDescriptions: Record<ServerType, string> = {
  ollama: 'Run open-source models locally with Ollama',
  abi: 'NEXUS ABI inference server (local or remote)',
  vllm: 'High-throughput LLM serving with vLLM',
  llamacpp: 'Efficient CPU/GPU inference with llama.cpp',
  custom: 'Custom OpenAI-compatible server',
};
