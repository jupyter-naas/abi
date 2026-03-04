import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { getApiUrl, getOllamaUrl } from '@/lib/config';
import { authFetch } from './auth';

export type ProviderType = 'anthropic' | 'ollama' | 'openai' | 'cloudflare' | 'custom';

export interface ProviderConfig {
  id: string;
  name: string;
  type: ProviderType;
  enabled: boolean;
  endpoint?: string; // For Ollama/custom
  apiKeySecretKey?: string; // Reference to secret key (e.g., "OPENAI_API_KEY")
  accountIdSecretKey?: string; // Reference to secret key for Cloudflare Account ID
  // Legacy fields - kept for backwards compatibility, will be migrated
  apiKey?: string;
  accountId?: string;
  model: string;
  defaultForAgents?: string[]; // Which agents use this by default
  createdAt: Date;
  updatedAt: Date;
}

export interface AgentProviderMapping {
  agentId: string;
  providerId: string;
}

interface IntegrationsState {
  providers: ProviderConfig[];
  agentMappings: AgentProviderMapping[];
  
  // Provider actions
  refreshProviders: () => Promise<void>;
  addProvider: (provider: Omit<ProviderConfig, 'id' | 'createdAt' | 'updatedAt'>) => void;
  updateProvider: (id: string, updates: Partial<ProviderConfig>) => void;
  deleteProvider: (id: string) => void;
  toggleProvider: (id: string) => void;
  syncOllamaProviders: (models: string[]) => void;
  
  // Agent mapping actions
  setAgentProvider: (agentId: string, providerId: string) => void;
  getProviderForAgent: (agentId: string) => ProviderConfig | undefined;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

// Default Ollama endpoint (centralized)
const OLLAMA_DEFAULT = getOllamaUrl();

// Default providers are empty; populated dynamically from API /api/providers/available
const defaultProviders: ProviderConfig[] = [];

export const useIntegrationsStore = create<IntegrationsState>()(
  persist(
    (set, get) => ({
      providers: defaultProviders,
      agentMappings: [
        // Prefer Ollama by default; server falls back if unavailable
        { agentId: 'abi', providerId: 'ollama' },
        { agentId: 'aia', providerId: 'ollama' },
        { agentId: 'bob', providerId: 'anthropic' },
        { agentId: 'system', providerId: 'anthropic' },
      ],

      // Fetch available providers from API and populate store to avoid drift
      refreshProviders: async () => {
        try {
          const API_BASE = getApiUrl();
          const res = await authFetch(`${API_BASE}/api/providers/available`);
          if (!res.ok) return;
          const data: Array<{ id: string; name: string; type: ProviderType; has_api_key: boolean; models: Array<{ id: string; name: string }> }> = await res.json();
          const mapped: ProviderConfig[] = data.map((p) => {
            // Choose a sensible default model (first in registry list)
            const defaultModel = p.models?.[0]?.id || '';
            const isOllama = p.type === 'ollama';
            return {
              id: p.id,
              name: p.name,
              type: p.type,
              enabled: isOllama ? true : p.has_api_key,
              endpoint: isOllama ? OLLAMA_DEFAULT : undefined,
              model: defaultModel,
              createdAt: new Date(),
              updatedAt: new Date(),
            } as ProviderConfig;
          });
          set({ providers: mapped });
        } catch (e) {
          // Silently ignore; UI can retry
          console.warn('Failed to refresh providers', e);
        }
      },

      addProvider: (provider) => {
        const newProvider: ProviderConfig = {
          ...provider,
          id: generateId(),
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({
          providers: [...state.providers, newProvider],
        }));
      },

      updateProvider: (id, updates) => {
        set((state) => ({
          providers: state.providers.map((p) =>
            p.id === id ? { ...p, ...updates, updatedAt: new Date() } : p
          ),
        }));
      },

      deleteProvider: (id) => {
        set((state) => ({
          providers: state.providers.filter((p) => p.id !== id),
          agentMappings: state.agentMappings.filter((m) => m.providerId !== id),
        }));
      },

      toggleProvider: (id) => {
        set((state) => ({
          providers: state.providers.map((p) =>
            p.id === id ? { ...p, enabled: !p.enabled, updatedAt: new Date() } : p
          ),
        }));
      },

      syncOllamaProviders: (models) => {
        set((state) => {
          // Remove all existing Ollama providers
          const nonOllamaProviders = state.providers.filter((p) => p.type !== 'ollama');
          
          // Create new providers for each model
          const newOllamaProviders: ProviderConfig[] = models.map((model) => ({
            id: `ollama-${model.replace(/[^a-zA-Z0-9]/g, '-')}`,
            name: `Ollama - ${model}`,
            type: 'ollama' as ProviderType,
            enabled: false,
            endpoint: OLLAMA_DEFAULT,
            model: model,
            createdAt: new Date(),
            updatedAt: new Date(),
          }));
          
          // Update agent mappings - remove mappings to deleted Ollama providers
          const ollamaProviderIds = newOllamaProviders.map((p) => p.id);
          const updatedMappings = state.agentMappings.map((m) => {
            const oldProvider = state.providers.find((p) => p.id === m.providerId);
            if (oldProvider?.type === 'ollama' && !ollamaProviderIds.includes(m.providerId)) {
              // Reset to empty if the Ollama model was removed
              return { ...m, providerId: '' };
            }
            return m;
          });
          
          return {
            providers: [...nonOllamaProviders, ...newOllamaProviders],
            agentMappings: updatedMappings,
          };
        });
      },

      setAgentProvider: (agentId, providerId) => {
        set((state) => {
          const existing = state.agentMappings.find((m) => m.agentId === agentId);
          if (existing) {
            return {
              agentMappings: state.agentMappings.map((m) =>
                m.agentId === agentId ? { ...m, providerId } : m
              ),
            };
          }
          return {
            agentMappings: [...state.agentMappings, { agentId, providerId }],
          };
        });
      },

      getProviderForAgent: (agentId) => {
        const mapping = get().agentMappings.find((m) => m.agentId === agentId);
        if (!mapping) return undefined;
        return get().providers.find((p) => p.id === mapping.providerId);
      },
    }),
    {
      name: 'nexus-integrations',
    }
  )
);
