/**
 * Secrets store - fetches from server-side API.
 * 
 * Secrets are stored server-side only. The frontend never sees raw values.
 * This store manages the masked secret list and provides CRUD operations.
 */

import { create } from 'zustand';
import { authFetch } from './auth';

import { getApiUrl } from '@/lib/config';

const API_BASE = getApiUrl();

export interface Secret {
  id: string;
  key: string;
  masked_value: string;  // Server returns masked value only
  description: string;
  category: 'api_keys' | 'credentials' | 'tokens' | 'other';
  workspace_id: string;
  created_at?: string;
  updated_at?: string;
}

interface SecretsState {
  secrets: Secret[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  fetchSecrets: (workspaceId: string) => Promise<void>;
  addSecret: (workspaceId: string, key: string, value: string, description?: string, category?: string) => Promise<string | null>;
  updateSecret: (id: string, updates: { value?: string; description?: string }) => Promise<void>;
  deleteSecret: (id: string) => Promise<void>;
  getSecretByKey: (key: string) => Secret | undefined;
  
  // Bulk operations
  importFromEnv: (workspaceId: string, envContent: string) => Promise<{ imported: number; updated: number }>;
  exportToEnv: () => string;
}

export const useSecretsStore = create<SecretsState>()(
  (set, get) => ({
    secrets: [],
    isLoading: false,
    error: null,

    fetchSecrets: async (workspaceId: string) => {
      set({ isLoading: true, error: null });
      try {
        const response = await authFetch(`${API_BASE}/api/secrets/${workspaceId}`);
        if (!response.ok) {
          throw new Error('Failed to fetch secrets');
        }
        const data = await response.json();
        set({ secrets: data, isLoading: false });
      } catch (error) {
        set({ 
          isLoading: false, 
          error: error instanceof Error ? error.message : 'Failed to fetch secrets' 
        });
      }
    },

    addSecret: async (workspaceId, key, value, description = '', category = 'other') => {
      try {
        const response = await authFetch(`${API_BASE}/api/secrets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            key,
            value,
            description,
            category,
          }),
        });
        
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to create secret');
        }
        
        const newSecret = await response.json();
        set((state) => ({
          secrets: [...state.secrets, newSecret],
        }));
        return newSecret.id;
      } catch (error) {
        set({ error: error instanceof Error ? error.message : 'Failed to create secret' });
        return null;
      }
    },

    updateSecret: async (id, updates) => {
      try {
        const response = await authFetch(`${API_BASE}/api/secrets/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        });
        
        if (!response.ok) throw new Error('Failed to update secret');
        
        const updated = await response.json();
        set((state) => ({
          secrets: state.secrets.map((s) =>
            s.id === id ? updated : s
          ),
        }));
      } catch (error) {
        set({ error: error instanceof Error ? error.message : 'Failed to update secret' });
      }
    },

    deleteSecret: async (id) => {
      try {
        const response = await authFetch(`${API_BASE}/api/secrets/${id}`, {
          method: 'DELETE',
        });
        
        if (!response.ok) throw new Error('Failed to delete secret');
        
        set((state) => ({
          secrets: state.secrets.filter((s) => s.id !== id),
        }));
      } catch (error) {
        set({ error: error instanceof Error ? error.message : 'Failed to delete secret' });
      }
    },

    getSecretByKey: (key) => {
      return get().secrets.find((s) => s.key === key);
    },

    importFromEnv: async (workspaceId, envContent) => {
      try {
        const response = await authFetch(`${API_BASE}/api/secrets/import`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            env_content: envContent,
          }),
        });
        
        if (!response.ok) throw new Error('Failed to import secrets');
        
        const result = await response.json();
        
        // Refresh the secrets list
        await get().fetchSecrets(workspaceId);
        
        return result;
      } catch (error) {
        set({ error: error instanceof Error ? error.message : 'Failed to import secrets' });
        return { imported: 0, updated: 0 };
      }
    },

    exportToEnv: () => {
      const { secrets } = get();
      const lines: string[] = ['# NEXUS Secrets Export', `# Generated: ${new Date().toISOString()}`, ''];
      
      const categories: Record<string, Secret[]> = {};
      for (const secret of secrets) {
        if (!categories[secret.category]) {
          categories[secret.category] = [];
        }
        categories[secret.category].push(secret);
      }
      
      const categoryLabels: Record<string, string> = {
        api_keys: 'API Keys',
        credentials: 'Credentials',
        tokens: 'Tokens',
        other: 'Other',
      };
      
      for (const [category, categorySecrets] of Object.entries(categories)) {
        lines.push(`# ${categoryLabels[category] || category}`);
        for (const secret of categorySecrets) {
          if (secret.description) {
            lines.push(`# ${secret.description}`);
          }
          // Export masked values (user needs to fill in real values)
          lines.push(`${secret.key}=${secret.masked_value}`);
        }
        lines.push('');
      }
      
      return lines.join('\n');
    },
  })
);
