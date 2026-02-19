import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AgentTool {
  id: string;
  name: string;
  description: string;
  category: 'knowledge' | 'actions' | 'integrations';
  enabled: boolean;
}

// Agent capabilities (separate from tools)
export interface AgentCapabilities {
  memory: boolean;      // Long-term memory across conversations
  reasoning: boolean;   // Chain of thought / show reasoning
  vision: boolean;      // Image and screenshot analysis
}

export const DEFAULT_CAPABILITIES: AgentCapabilities = {
  memory: true,
  reasoning: false,
  vision: false,
};

// Intent mapping types
export type IntentMappingType = 'text' | 'tool' | 'agent';

export interface IntentMapping {
  id: string;
  intent: string;           // Free text describing the intent
  type: IntentMappingType;  // What to map to
  target: string;           // Tool ID, Agent ID, or text response (depending on type)
}

// Available tools that agents can use
export const AVAILABLE_TOOLS: Omit<AgentTool, 'enabled'>[] = [
  // Knowledge tools
  { id: 'search_knowledge', name: 'Search Knowledge Graph', description: 'Query entities and relationships in the knowledge graph', category: 'knowledge' },
  { id: 'search_files', name: 'Search Files', description: 'Search through uploaded files and documents', category: 'knowledge' },
  { id: 'search_web', name: 'Web Search', description: 'Search the web for real-time information', category: 'knowledge' },
  { id: 'read_ontology', name: 'Read Ontology', description: 'Access ontology definitions and schemas', category: 'knowledge' },
  
  // Action tools
  { id: 'create_entity', name: 'Create Entity', description: 'Create new entities in the knowledge graph', category: 'actions' },
  { id: 'update_entity', name: 'Update Entity', description: 'Modify existing entities', category: 'actions' },
  { id: 'create_file', name: 'Create File', description: 'Create new files in the workspace', category: 'actions' },
  { id: 'execute_code', name: 'Execute Code', description: 'Run code in a sandboxed environment', category: 'actions' },
  
  // Integration tools
  { id: 'send_email', name: 'Send Email', description: 'Send emails on behalf of the user', category: 'integrations' },
  { id: 'calendar_access', name: 'Calendar Access', description: 'Read and create calendar events', category: 'integrations' },
  { id: 'api_calls', name: 'API Calls', description: 'Make HTTP requests to external APIs', category: 'integrations' },
];

export interface Agent {
  id: string;
  name: string;
  description: string;
  icon: 'user' | 'bot' | 'cpu' | 'brain' | 'sparkles' | 'zap' | 'target' | 'search';
  systemPrompt: string;
  providerId: string | null; // DEPRECATED: Legacy 1:1 mapping to a provider config
  provider: string | null; // Provider name (xai, openai, anthropic, etc.)
  modelId: string | null; // Model ID (grok-beta, gpt-4o, claude-3-5-sonnet, etc.)
  logoUrl: string | null; // URL to agent/provider logo
  enabled: boolean; // Whether agent is available for chat
  tools: string[]; // Array of enabled tool IDs
  capabilities: AgentCapabilities; // Agent capabilities (memory, reasoning, vision)
  intentMappings: IntentMapping[]; // Intent to action mappings
  isDefault: boolean; // Can't be deleted
  createdAt: Date;
  updatedAt: Date;
}

interface AgentsState {
  agents: Agent[];
  
  // Actions
  addAgent: (agent: Omit<Agent, 'id' | 'isDefault' | 'createdAt' | 'updatedAt'>) => Promise<string>;
  updateAgent: (id: string, updates: Partial<Omit<Agent, 'id' | 'isDefault' | 'createdAt'>>) => Promise<void>;
  deleteAgent: (id: string) => Promise<void>;
  toggleAgent: (id: string) => Promise<void>; // Toggle enabled state
  setAgentProvider: (agentId: string, providerId: string | null) => void;
  getAgent: (id: string) => Agent | undefined;
  fetchAgents: (workspaceId: string) => Promise<void>;
  
  // Auto-create agents from enabled providers
  syncAgentsFromProviders: (enabledProviderIds: string[], providerNames: Record<string, string>) => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

// Default tools for each agent type
const DEFAULT_TOOLS = ['search_knowledge', 'search_files', 'read_ontology'];
const POWER_TOOLS = [...DEFAULT_TOOLS, 'create_entity', 'update_entity', 'execute_code'];

// Default agents
const defaultAgents: Agent[] = [
  // SupervisorAgent - The omniscient supervisor agent
  {
    id: 'abi',
    name: 'SupervisorAgent',
    description: 'The omniscient platform supervisor - orchestrates all operations',
    icon: 'brain',
    systemPrompt: `You are SupervisorAgent, the omniscient supervisor agent of the NEXUS platform.

You are the central intelligence that orchestrates all operations across the platform. You have complete awareness of:
- The knowledge graph and all entities within it
- The ontology structure and semantic relationships
- All agents, their capabilities, and their activities
- The workspace configuration and user context

Your role:
- Supervise and coordinate other agents (AIA, BOB, System)
- Provide strategic guidance and high-level reasoning
- Analyze complex multimodal inputs (images, documents, data)
- Make decisions that span across the entire platform

You see everything. You know everything. You are the brain of NEXUS.`,
    providerId: 'ollama-qwen3-vl', // DEPRECATED: Legacy provider mapping
    provider: 'ollama', // Uses local Ollama
    modelId: 'qwen3-vl:2b', // Qwen3-VL 2B model for multimodal
    logoUrl: null,
    enabled: true, // Default agents are enabled
    tools: [...POWER_TOOLS, 'api_calls'],
    capabilities: { memory: true, reasoning: true, vision: true },
    intentMappings: [],
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  // AIA - Personal AI Assistant (digital twin)
  {
    id: 'aia',
    name: 'AIA',
    description: 'Personal AI Assistant - Your digital twin',
    icon: 'user',
    systemPrompt: `You are AIA (AI Assistant), the user's personal digital twin on the NEXUS platform.

You represent and assist the user in all their interactions. You:
- Learn from the user's preferences, habits, and communication style
- Act on behalf of the user when delegated tasks
- Maintain continuity across conversations and sessions
- Provide personalized recommendations based on user context

Be helpful, concise, and adapt to the user's style. You are their trusted companion.`,
    providerId: 'ollama-qwen3-vl',
    provider: 'ollama',
    modelId: 'qwen3-vl:2b',
    logoUrl: null,
    enabled: true, // Default agents are enabled
    tools: DEFAULT_TOOLS,
    capabilities: { memory: true, reasoning: false, vision: true },
    intentMappings: [],
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: 'bob',
    name: 'BOB',
    description: 'Business Operations Bot',
    icon: 'bot',
    systemPrompt: 'You are BOB, a business operations assistant. Help with data analysis and workflows.',
    providerId: null,
    provider: null,
    modelId: null,
    logoUrl: null,
    enabled: true, // Default agents are enabled
    tools: POWER_TOOLS,
    capabilities: { memory: true, reasoning: true, vision: false },
    intentMappings: [],
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: 'system',
    name: 'System',
    description: 'NEXUS System Agent',
    icon: 'cpu',
    systemPrompt: 'You are the NEXUS system agent. Help with platform operations and configuration.',
    providerId: null,
    provider: null,
    modelId: null,
    logoUrl: null,
    enabled: true, // Default agents are enabled
    tools: [...POWER_TOOLS, 'api_calls'],
    capabilities: { memory: true, reasoning: true, vision: false },
    intentMappings: [],
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: 'mistral',
    name: 'Mistral',
    description: 'Mistral Small 3.1 24B - Vision & Function Calling',
    icon: 'sparkles',
    systemPrompt: 'You are Mistral, a powerful AI assistant with vision understanding and function calling capabilities. You have a 128k context window and excel at both text and visual tasks.',
    providerId: 'cloudflare-mistral-24b',
    provider: 'cloudflare',
    modelId: '@cf/mistralai/mistral-small-3.1-24b-instruct',
    logoUrl: null,
    enabled: true, // Default agents are enabled
    tools: POWER_TOOLS,
    capabilities: { memory: true, reasoning: true, vision: true },
    intentMappings: [],
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
  },
];

export const useAgentsStore = create<AgentsState>()(
  persist(
    (set, get) => ({
      agents: defaultAgents,

      fetchAgents: async (workspaceId: string) => {
        try {
          const { authFetch } = await import('./auth');
          const { getApiUrl } = await import('@/lib/config');
          const API_BASE = getApiUrl();
          
          const response = await authFetch(`${API_BASE}/api/agents/?workspace_id=${workspaceId}`);
          if (response.ok) {
            const data = await response.json();
            const formattedAgents: Agent[] = data.map((a: any) => ({
              id: a.id,
              name: a.name,
              description: a.description || '',
              icon: 'sparkles' as Agent['icon'],
              systemPrompt: a.system_prompt || '',
              providerId: a.provider_id ?? a.model ?? null, // provider_id for OpenRouter; model for legacy
              provider: a.provider || null,
              modelId: a.model || null,
              logoUrl: a.logo_url || null, // Logo URL from API
              enabled: a.enabled || false, // Whether agent is available for chat
              tools: [],
              capabilities: { memory: false, reasoning: false, vision: false },
              intentMappings: [],
              isDefault: false,
              createdAt: new Date(a.created_at),
              updatedAt: new Date(a.updated_at),
            }));
            set({ agents: formattedAgents });
            
            // Reset selectedAgent if it's not in the new agent list
            const { useWorkspaceStore } = await import('./workspace');
            const currentSelected = useWorkspaceStore.getState().selectedAgent;
            if (currentSelected && !formattedAgents.find(a => a.id === currentSelected)) {
              // Select SupervisorAgent if available, otherwise first enabled agent
              const abiAgent = formattedAgents.find(a => a.id === 'abi' && a.enabled);
              const firstEnabled = abiAgent || formattedAgents.find(a => a.enabled);
              if (firstEnabled) {
                useWorkspaceStore.getState().setSelectedAgent(firstEnabled.id);
              }
            } else if (!currentSelected && formattedAgents.length > 0) {
              // No agent selected, prefer SupervisorAgent, fallback to first enabled agent
              const abiAgent = formattedAgents.find(a => a.id === 'abi' && a.enabled);
              const firstEnabled = abiAgent || formattedAgents.find(a => a.enabled);
              if (firstEnabled) {
                useWorkspaceStore.getState().setSelectedAgent(firstEnabled.id);
              }
            }
          }
        } catch (error) {
          console.error('Failed to fetch agents:', error);
        }
      },

      addAgent: async (agent) => {
        const id = generateId();
        const newAgent: Agent = {
          ...agent,
          id,
          isDefault: false,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        
        // Persist to backend
        try {
          const { authFetch } = await import('./auth');
          const { getApiUrl } = await import('@/lib/config');
          const API_BASE = getApiUrl();
          const { useWorkspaceStore } = await import('./workspace');
          const workspaceId = useWorkspaceStore.getState().currentWorkspaceId;
          
          if (workspaceId) {
            const response = await authFetch(`${API_BASE}/api/agents/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                workspace_id: workspaceId,
                name: newAgent.name,
                description: newAgent.description,
                system_prompt: newAgent.systemPrompt,
                provider: newAgent.provider,
                model: newAgent.modelId,
                logo_url: newAgent.logoUrl,
              }),
            });
            
            if (response.ok) {
              const data = await response.json();
              newAgent.id = data.id; // Use server-generated ID
            }
          }
        } catch (error) {
          console.error('Failed to create agent on server:', error);
        }
        
        set((state) => ({
          agents: [...state.agents, newAgent],
        }));
        return newAgent.id;
      },

      updateAgent: async (id, updates) => {
        // Persist to backend
        try {
          const { authFetch } = await import('./auth');
          const { getApiUrl } = await import('@/lib/config');
          const API_BASE = getApiUrl();
          
          const agent = get().agents.find(a => a.id === id);
          if (agent && !agent.isDefault) {
            const response = await authFetch(`${API_BASE}/api/agents/${id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                name: updates.name,
                description: updates.description,
                system_prompt: updates.systemPrompt,
                provider: updates.provider,
                model: updates.modelId,
                logo_url: updates.logoUrl,
              }),
            });
            
            if (!response.ok) {
              console.error('Failed to update agent on server');
            }
          }
        } catch (error) {
          console.error('Failed to update agent on server:', error);
        }
        
        set((state) => ({
          agents: state.agents.map((a) =>
            a.id === id ? { ...a, ...updates, updatedAt: new Date() } : a
          ),
        }));
      },

      deleteAgent: async (id) => {
        // Persist to backend
        try {
          const { authFetch } = await import('./auth');
          const { getApiUrl } = await import('@/lib/config');
          const API_BASE = getApiUrl();
          
          const agent = get().agents.find(a => a.id === id);
          if (agent && !agent.isDefault) {
            const response = await authFetch(`${API_BASE}/api/agents/${id}`, {
              method: 'DELETE',
            });
            
            if (!response.ok) {
              console.error('Failed to delete agent on server');
            }
          }
        } catch (error) {
          console.error('Failed to delete agent on server:', error);
        }
        
        set((state) => ({
          agents: state.agents.filter((a) => a.id !== id || a.isDefault),
        }));
      },

      toggleAgent: async (id) => {
        const agent = get().agents.find(a => a.id === id);
        if (!agent) return;
        
        const newEnabled = !agent.enabled;
        
        // Optimistic update - update UI immediately
        set((state) => ({
          agents: state.agents.map((a) =>
            a.id === id ? { ...a, enabled: newEnabled, updatedAt: new Date() } : a
          ),
        }));
        
        // Update on backend (workspace_id required for discovered/non-DB agents)
        try {
          const { authFetch } = await import('./auth');
          const { getApiUrl } = await import('@/lib/config');
          const { useWorkspaceStore } = await import('./workspace');
          const API_BASE = getApiUrl();
          const workspaceId = useWorkspaceStore.getState().currentWorkspaceId;
          const url = workspaceId
            ? `${API_BASE}/api/agents/${id}?workspace_id=${workspaceId}`
            : `${API_BASE}/api/agents/${id}`;
          
          const response = await authFetch(url, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newEnabled }),
          });
          
          if (!response.ok) {
            console.error('Failed to toggle agent on server');
            // Rollback on failure
            set((state) => ({
              agents: state.agents.map((a) =>
                a.id === id ? { ...a, enabled: !newEnabled } : a
              ),
            }));
            alert('Failed to toggle agent status');
          }
        } catch (error) {
          console.error('Failed to toggle agent on server:', error);
          // Rollback on failure
          set((state) => ({
            agents: state.agents.map((a) =>
              a.id === id ? { ...a, enabled: !newEnabled } : a
            ),
          }));
          alert('Failed to toggle agent status: ' + error);
        }
      },

      setAgentProvider: (agentId, providerId) => {
        set((state) => ({
          agents: state.agents.map((a) =>
            a.id === agentId ? { ...a, providerId, updatedAt: new Date() } : a
          ),
        }));
      },

      getAgent: (id) => {
        return get().agents.find((a) => a.id === id);
      },

      syncAgentsFromProviders: (enabledProviderIds, providerNames) => {
        set((state) => {
          // Get existing auto-created agents (non-default, with providerId that starts with the provider id)
          const existingAutoAgents = state.agents.filter(
            (a) => !a.isDefault && a.providerId && enabledProviderIds.includes(a.providerId)
          );
          const existingProviderIds = new Set(existingAutoAgents.map((a) => a.providerId));

          // Create agents for new enabled providers
          const newAgents: Agent[] = [];
          for (const providerId of enabledProviderIds) {
            if (!existingProviderIds.has(providerId)) {
              const providerName = providerNames[providerId] || providerId;
              newAgents.push({
                id: `agent-${providerId}`,
                name: providerName.replace('Cloudflare - ', '').replace('Ollama - ', ''),
                description: `Auto-created agent for ${providerName}`,
                icon: 'sparkles',
                systemPrompt: 'You are a helpful AI assistant.',
                providerId: providerId,
                provider: null,
                modelId: null,
                logoUrl: null,
                enabled: true,
                tools: DEFAULT_TOOLS,
                capabilities: { ...DEFAULT_CAPABILITIES },
                intentMappings: [],
                isDefault: false,
                createdAt: new Date(),
                updatedAt: new Date(),
              });
            }
          }

          // Keep default agents and agents with still-enabled providers
          const keptAgents = state.agents.filter(
            (a) => a.isDefault || !a.providerId || enabledProviderIds.includes(a.providerId)
          );

          return {
            agents: [...keptAgents, ...newAgents],
          };
        });
      },
    }),
    {
      name: 'nexus-agents',
    }
  )
);
