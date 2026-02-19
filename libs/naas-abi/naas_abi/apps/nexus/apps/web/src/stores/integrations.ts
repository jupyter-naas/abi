import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { getApiUrl, getOllamaUrl } from '@/lib/config';
import { authFetch } from './auth';

export type ProviderType = 'anthropic' | 'ollama' | 'openai' | 'cloudflare' | 'custom' | 'openrouter' | 'xai' | 'mistral' | 'google' | 'perplexity';

export interface ProviderConfig {
  id: string;
  name: string;
  type: ProviderType;
  enabled: boolean;
  endpoint?: string; // For Ollama/custom
  logoUrl?: string; // Per-model logo (OpenRouter: anthropic/openai/etc)
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
  refreshProviders: (prefetched?: Array<{ id: string; name: string; type: ProviderType; has_api_key: boolean; models: Array<{ id: string; name: string; logo_url?: string | null }> }>) => Promise<void>;
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
      // For OpenRouter: create one provider per model (Cursor-style) so each model appears in sidebar
      refreshProviders: async (prefetched?: Array<{ id: string; name: string; type: ProviderType; has_api_key: boolean; models: Array<{ id: string; name: string }> }>) => {
        try {
          let data: Array<{ id: string; name: string; type: ProviderType; has_api_key: boolean; models: Array<{ id: string; name: string; logo_url?: string | null }> }>;
          if (prefetched !== undefined) {
            data = prefetched;
          } else {
            const API_BASE = getApiUrl();
            const res = await authFetch(`${API_BASE}/api/providers/available`, { credentials: 'include' });
            if (!res.ok) {
              console.error(`[refreshProviders] API ${res.status} ${res.statusText}`);
              return;
            }
            data = await res.json();
          }
          const ENDPOINT_MAP: Record<string, string> = {
            ollama: OLLAMA_DEFAULT,
            openrouter: 'https://openrouter.ai/api/v1',
            openai: 'https://api.openai.com/v1',
            anthropic: 'https://api.anthropic.com/v1',
            xai: 'https://api.x.ai/v1',
            mistral: 'https://api.mistral.ai/v1',
            google: 'https://generativelanguage.googleapis.com/v1beta',
            perplexity: 'https://api.perplexity.ai',
            cloudflare: '',
          };
          const mapped: ProviderConfig[] = [];
          for (const p of data) {
            const isOllama = p.type === 'ollama';
            const hasKey = p.has_api_key;
            const models = p.models ?? [];

            // OpenRouter: one provider per model (like Cursor) - each model selectable, per-model logo
            if (p.type === 'openrouter' && models.length > 0) {
              for (const m of models) {
                const providerId = `openrouter-${m.id.replace(/\//g, '-')}`;
                mapped.push({
                  id: providerId,
                  name: `${p.name} - ${m.name}`,
                  type: p.type,
                  enabled: hasKey,
                  endpoint: ENDPOINT_MAP[p.type],
                  model: m.id,
                  logoUrl: m.logo_url ?? undefined,
                  createdAt: new Date(),
                  updatedAt: new Date(),
                } as ProviderConfig);
              }
              continue;
            }

            // Other providers: single provider with first model
            const defaultModel = models[0]?.id || '';
            mapped.push({
              id: p.id,
              name: p.name,
              type: p.type,
              enabled: isOllama ? true : hasKey,
              endpoint: ENDPOINT_MAP[p.type] || undefined,
              model: defaultModel,
              createdAt: new Date(),
              updatedAt: new Date(),
            } as ProviderConfig);
          }
          set((state) => {
            // Migrate old agent mappings: "openrouter" -> first OpenRouter provider
            const openrouterProviders = mapped.filter((x) => x.type === 'openrouter');
            const firstOpenRouterId = openrouterProviders[0]?.id;
            const updatedMappings = state.agentMappings.map((m) => {
              if (m.providerId === 'openrouter' && firstOpenRouterId) {
                return { ...m, providerId: firstOpenRouterId };
              }
              return m;
            });
            return { providers: mapped, agentMappings: updatedMappings };
          });
        } catch (e) {
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
      // Only persist agent mappings; providers are always fetched fresh so refresh works
      partialize: (s) => ({ agentMappings: s.agentMappings }),
    }
  )
);
