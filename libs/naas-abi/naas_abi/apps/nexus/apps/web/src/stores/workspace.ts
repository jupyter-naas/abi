import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { WorkspaceFeatureFlags } from '@/lib/feature-access';
import { useAuthStore } from './auth';
import { getApiUrl } from '@/lib/config';

// Throttled localStorage wrapper: prevents browser freeze during streaming.
// During chat streaming, updateLastMessage fires on every token, which causes
// Zustand persist to JSON.stringify + localStorage.setItem the entire state
// hundreds of times per second. This batches writes to at most once per second.
const throttledLocalStorage = () => {
  let pendingValue: string | null = null;
  let writeTimer: ReturnType<typeof setTimeout> | null = null;

  return {
    getItem: (name: string) => localStorage.getItem(name),
    setItem: (name: string, value: string) => {
      pendingValue = value;
      if (!writeTimer) {
        writeTimer = setTimeout(() => {
          if (pendingValue !== null) {
            try {
              localStorage.setItem(name, pendingValue);
            } catch {
              // Silently handle quota exceeded
            }
            pendingValue = null;
          }
          writeTimer = null;
        }, 1000);
      }
    },
    removeItem: (name: string) => localStorage.removeItem(name),
  };
};

export type NavigationItem =
  | 'chat'
  | 'search'
  | 'files'
  | 'code'
  | 'ontology'
  | 'graph'
  | 'apps'
  | 'marketplace';

// AgentType is now a string to support dynamic agents
export type AgentType = string;

export interface ToolCall {
  id: string;
  toolName: string;
  prefix: 'Tool' | 'Agent' | 'Handoff to' | 'Routing to';
  rawName: string;
  status: 'running' | 'done';
  input?: string;
  output?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  agent?: AgentType;
  activityLine?: string; // Single-line live status (legacy, kept for backward compat)
  toolCalls?: ToolCall[]; // Ordered list of tool invocations for this message
  images?: string[]; // Base64-encoded images for multimodal chat
  thinkingDuration?: number; // Duration in seconds the AI spent "thinking"
  executionTime?: number; // Total seconds from request sent to response complete
  sources?: string[]; // filenames of RAG documents used to answer
  // Author attribution (preserved across sessions and users)
  authorId?: string;
  authorName?: string;
}

export interface Conversation {
  id: string;
  workspaceId: string; // Workspace this conversation belongs to
  title: string;
  messages: Message[];
  agent: AgentType;
  createdAt: Date;
  updatedAt: Date;
  pinned?: boolean;
  archived?: boolean;
  projectId?: string;
}

export interface Project {
  id: string;
  name: string;
  color?: string;
}

export interface WorkspaceTheme {
  logoUrl?: string;
  logoEmoji?: string;
  primaryColor: string;
  accentColor?: string;
  backgroundColor?: string;
  sidebarColor?: string;
  fontFamily?: string;
}

export const DEFAULT_THEME: WorkspaceTheme = {
  primaryColor: '#22c55e', // Green
  accentColor: '#3b82f6',
  backgroundColor: '#0a0a0a',
  sidebarColor: '#111111',
};

export const PRESET_COLORS = [
  { name: 'Green', value: '#22c55e' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Purple', value: '#a855f7' },
  { name: 'Pink', value: '#ec4899' },
  { name: 'Orange', value: '#f97316' },
  { name: 'Red', value: '#ef4444' },
  { name: 'Cyan', value: '#06b6d4' },
  { name: 'Yellow', value: '#eab308' },
];

export interface Workspace {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  color?: string;
  theme: WorkspaceTheme;
  createdAt: Date;
  updatedAt: Date;
  currentUserRole?: string;
  featureFlags?: WorkspaceFeatureFlags;
  platformDriveEnabled?: boolean;
  systemDriveEnabled?: boolean;
  isDemo?: boolean;
}

// Sidebar expandable sections
export type SidebarSection = 'chat' | 'search' | 'files' | 'code' | 'ontology' | 'graph' | 'apps' | 'marketplace' | 'settings';

export interface OpenAppModule {
  module_path: string;
  name: string;
  description?: string;
  logo_url: string | null;
  category: string;
  app_url?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  maintainer?: string | null;
  tier?: string | null;
}

interface WorkspaceState {
  // Navigation
  activeNav: NavigationItem;
  setActiveNav: (nav: NavigationItem) => void;

  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  expandedSections: SidebarSection[];
  toggleSection: (section: SidebarSection) => void;
  activePanelSection: SidebarSection | null;
  setActivePanelSection: (section: SidebarSection | null) => void;
  lastActivePanelSection: SidebarSection | null;

  // Currently open app (for Apps section panel detail view)
  openAppModule: OpenAppModule | null;
  setOpenAppModule: (mod: OpenAppModule | null) => void;

  // Context panel
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;
  setContextPanelOpen: (open: boolean) => void;

  // Chat state
  conversations: Conversation[];
  activeConversationId: string | null;
  selectedAgent: AgentType;
  setSelectedAgent: (agent: AgentType) => void;
  paneAgent: AgentType; // AI Pane agent selection
  setPaneAgent: (agent: AgentType) => void;
  createConversation: (projectId?: string) => string;
  setActiveConversation: (id: string | null) => void;
  addMessage: (conversationId: string, message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateLastMessage: (
    conversationId: string,
    content: string,
    thinkingDuration?: number,
    sources?: string[],
    activityLine?: string | null,
    toolCalls?: ToolCall[] | null,
    executionTime?: number,
  ) => void;
  togglePinConversation: (id: string) => void;
  toggleArchiveConversation: (id: string) => void;
  renameConversation: (id: string, newTitle: string) => void;
  deleteConversation: (id: string) => void;
  getWorkspaceConversations: () => Conversation[];
  setCurrentWorkspace: (id: string) => void;
  syncWorkspaceConversations: (workspaceId?: string) => Promise<void>;
  loadConversationMessages: (conversationId: string) => Promise<void>;

  // Projects
  projects: Project[];
  createProject: (name: string) => string;

  workspaces: Workspace[];
  currentWorkspaceId: string | null;

  createWorkspace: (name: string, description?: string) => Workspace;
  deleteWorkspace: (id: string) => void;
  selectWorkspace: (id: string) => void;
  updateWorkspace: (id: string, updates: Partial<Workspace>) => void;
  updateWorkspaceTheme: (updates: Partial<WorkspaceTheme>) => void;
  getCurrentWorkspace: () => Workspace | null;
  fetchWorkspaces: () => Promise<void>;
}

const generateId = () => Math.random().toString(36).substring(2, 15);
const generateConversationId = () => `conv-${Math.random().toString(36).substring(2, 14)}`;

type ApiChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string | null;
  created_at?: string;
};

type ApiConversation = {
  id: string;
  workspace_id: string;
  title?: string;
  agent?: string;
  pinned?: boolean;
  archived?: boolean;
  created_at?: string;
  updated_at?: string;
  messages?: ApiChatMessage[];
};

const mapApiMessage = (message: ApiChatMessage): Message => ({
  id: message.id,
  role: message.role,
  content: message.content,
  timestamp: new Date(message.created_at || Date.now()),
  agent: message.agent || undefined,
});

const mapApiConversation = (conversation: ApiConversation): Conversation => ({
  id: conversation.id,
  workspaceId: conversation.workspace_id,
  title: conversation.title || 'New Conversation',
  messages: Array.isArray(conversation.messages) ? conversation.messages.map(mapApiMessage) : [],
  agent: conversation.agent || 'abi',
  createdAt: new Date(conversation.created_at || Date.now()),
  updatedAt: new Date(conversation.updated_at || Date.now()),
  pinned: Boolean(conversation.pinned),
  archived: Boolean(conversation.archived),
});

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
  // Navigation
  activeNav: 'chat',
  setActiveNav: (nav) => set({ activeNav: nav }),

  // Sidebar
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  expandedSections: ['chat'] as SidebarSection[],
  toggleSection: (section) =>
    set((state) => ({
      expandedSections: state.expandedSections.includes(section)
        ? state.expandedSections.filter((s) => s !== section)
        : [...state.expandedSections, section],
    })),
  activePanelSection: null,
  setActivePanelSection: (section) => set((state) => ({
    activePanelSection: section,
    lastActivePanelSection: section ?? state.lastActivePanelSection,
  })),
  lastActivePanelSection: null,

  openAppModule: null,
  setOpenAppModule: (mod) => set({ openAppModule: mod }),

  // Context panel
  contextPanelOpen: false,
  toggleContextPanel: () => set((state) => ({ contextPanelOpen: !state.contextPanelOpen })),
  setContextPanelOpen: (open) => set({ contextPanelOpen: open }),

  // Chat state
  conversations: [],
  activeConversationId: null,
  selectedAgent: 'abi', // Default to SupervisorAgent - omniscient supervisor agent for Chat
  setSelectedAgent: (agent) => set({ selectedAgent: agent }),
  paneAgent: 'abi', // Default to SupervisorAgent - omniscient supervisor agent for AI Pane
  setPaneAgent: (agent) => set({ paneAgent: agent }),

  createConversation: (projectId?: string) => {
    const id = generateConversationId();
    const workspaceId = get().currentWorkspaceId;
    if (!workspaceId) {
      console.error('Cannot create conversation: no workspace selected');
      return id;
    }
    const newConversation: Conversation = {
      id,
      workspaceId,
      title: 'New Conversation',
      messages: [],
      agent: get().selectedAgent,
      createdAt: new Date(),
      updatedAt: new Date(),
      pinned: false,
      projectId,
    };
    set((state) => ({
      conversations: [newConversation, ...state.conversations],
      activeConversationId: id,
    }));
    return id;
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  addMessage: (conversationId, message) => {
    const newMessage: Message = {
      ...message,
      id: generateId(),
      timestamp: new Date(),
      ...(message.role === 'user'
        ? {
            authorId: useAuthStore.getState().user?.id,
            authorName: useAuthStore.getState().user?.name,
          }
        : {}),
    };
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: [...conv.messages, newMessage],
              updatedAt: new Date(),
              title:
                conv.messages.length === 0 && message.role === 'user'
                  ? message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '')
                  : conv.title,
            }
          : conv
      ),
    }));
  },

  updateLastMessage: (conversationId, content, thinkingDuration, sources, activityLine, toolCalls, executionTime) => {
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: conv.messages.map((msg, idx) =>
                idx === conv.messages.length - 1
                  ? {
                      ...msg,
                      content,
                      ...(thinkingDuration !== undefined && { thinkingDuration }),
                      ...(sources !== undefined && { sources }),
                      ...(activityLine !== undefined && { activityLine: activityLine || undefined }),
                      ...(toolCalls !== undefined && { toolCalls: toolCalls || undefined }),
                      ...(executionTime !== undefined && { executionTime }),
                    }
                  : msg
              ),
              updatedAt: new Date(),
            }
          : conv
      ),
    }));
  },

  togglePinConversation: async (id) => {
    const conv = get().conversations.find(c => c.id === id);
    if (!conv) return;
    
    const newPinned = !conv.pinned;
    
    // Optimistic update
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, pinned: newPinned } : c
      ),
    }));
    
    // Sync with backend
    try {
      const { authFetch } = await import('./auth');
      await authFetch(`/api/chat/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pinned: newPinned }),
      });
    } catch (error) {
      console.error('Failed to update conversation:', error);
      // Rollback on error
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === id ? { ...c, pinned: !newPinned } : c
        ),
      }));
    }
  },

  toggleArchiveConversation: async (id) => {
    const conv = get().conversations.find(c => c.id === id);
    if (!conv) return;
    
    const newArchived = !conv.archived;
    
    // Optimistic update
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, archived: newArchived } : c
      ),
    }));
    
    // Sync with backend
    try {
      const { authFetch } = await import('./auth');
      await authFetch(`/api/chat/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archived: newArchived }),
      });
    } catch (error) {
      console.error('Failed to update conversation:', error);
      // Rollback on error
      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === id ? { ...c, archived: !newArchived } : c
        ),
      }));
    }
  },

  renameConversation: async (id, newTitle) => {
    const oldTitle = get().conversations.find(c => c.id === id)?.title;
    
    // Optimistic update
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === id ? { ...conv, title: newTitle, updatedAt: new Date() } : conv
      ),
    }));
    
    // Sync with backend
    try {
      const { authFetch } = await import('./auth');
      await authFetch(`/api/chat/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      });
    } catch (error) {
      console.error('Failed to rename conversation:', error);
      // Rollback on error
      if (oldTitle) {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === id ? { ...conv, title: oldTitle } : conv
          ),
        }));
      }
    }
  },

  deleteConversation: async (id) => {
    const conv = get().conversations.find(c => c.id === id);
    
    // Optimistic delete
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
    }));
    
    // Sync with backend
    try {
      const { authFetch } = await import('./auth');
      await authFetch(`/api/chat/conversations/${id}`, {
        method: 'DELETE',
      });
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      // Rollback on error
      if (conv) {
        set((state) => ({
          conversations: [...state.conversations, conv].sort((a, b) => 
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          ),
        }));
      }
    }
  },

  getWorkspaceConversations: () => {
    const { conversations, currentWorkspaceId } = get();
    if (!currentWorkspaceId) return [];
    return conversations.filter((c) => c.workspaceId === currentWorkspaceId);
  },

  setCurrentWorkspace: (id) => {
    set({ currentWorkspaceId: id, activeConversationId: null });
  },

  syncWorkspaceConversations: async (workspaceId) => {
    const targetWorkspaceId = workspaceId || get().currentWorkspaceId;
    if (!targetWorkspaceId) return;

    try {
      const { authFetch } = await import('./auth');
      const response = await authFetch(
        `/api/chat/conversations?workspace_id=${encodeURIComponent(targetWorkspaceId)}`
      );
      if (!response.ok) {
        console.error('Failed to fetch conversations:', response.status);
        return;
      }

      const apiConversations = (await response.json()) as ApiConversation[];
      const fromApi = Array.isArray(apiConversations)
        ? apiConversations.map(mapApiConversation)
        : [];

      set((state) => {
        const existingById = new Map(state.conversations.map((c) => [c.id, c]));
        const mergedWorkspaceConversations = fromApi.map((apiConv) => {
          const existing = existingById.get(apiConv.id);
          if (!existing) return apiConv;
          return {
            ...apiConv,
            // Preserve loaded message history if we already have it in memory.
            messages: existing.messages.length > 0 ? existing.messages : apiConv.messages,
          };
        });
        const otherWorkspaces = state.conversations.filter(
          (c) => c.workspaceId !== targetWorkspaceId
        );
        const conversations = [...mergedWorkspaceConversations, ...otherWorkspaces].sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
        return { conversations };
      });
    } catch (error) {
      console.error('Failed to sync workspace conversations:', error);
    }
  },

  loadConversationMessages: async (conversationId) => {
    if (!conversationId) return;
    try {
      const { authFetch } = await import('./auth');
      const response = await authFetch(`/api/chat/conversations/${conversationId}`);
      if (!response.ok) {
        console.error('Failed to fetch conversation details:', response.status);
        return;
      }

      const apiConversation = (await response.json()) as ApiConversation;
      const mapped = mapApiConversation(apiConversation);

      set((state) => {
        const alreadyExists = state.conversations.some((c) => c.id === mapped.id);
        const conversations = alreadyExists
          ? state.conversations.map((c) => (c.id === mapped.id ? mapped : c))
          : [mapped, ...state.conversations];
        return { conversations };
      });
    } catch (error) {
      console.error('Failed to load conversation messages:', error);
    }
  },

  // Projects
  projects: [],
  createProject: (name) => {
    const id = generateId();
    set((state) => ({
      projects: [...state.projects, { id, name }],
    }));
    return id;
  },

  workspaces: [],
  currentWorkspaceId: null,

  createWorkspace: (name, description) => {
    const workspace: Workspace = {
      id: generateId(),
      name,
      description,
      theme: { ...DEFAULT_THEME },
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    set((state) => ({
      workspaces: [...state.workspaces, workspace],
      currentWorkspaceId: workspace.id,
    }));

    return workspace;
  },

  deleteWorkspace: (id) => {
    set((state) => ({
      workspaces: state.workspaces.filter((w) => w.id !== id),
      currentWorkspaceId: state.currentWorkspaceId === id ? null : state.currentWorkspaceId,
    }));
  },

  selectWorkspace: (id) => {
    set({ currentWorkspaceId: id });
  },

  updateWorkspace: (id, updates) => {
    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === id ? { ...w, ...updates, updatedAt: new Date() } : w
      ),
    }));
  },

  updateWorkspaceTheme: async (updates) => {
    const { currentWorkspaceId } = get();
    if (!currentWorkspaceId) return;
    
    // Optimistic update
    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === currentWorkspaceId
          ? { ...w, theme: { ...w.theme, ...updates }, updatedAt: new Date() }
          : w
      ),
    }));
    
    // Sync with backend
    try {
      const { authFetch } = await import('./auth');
      const response = await authFetch(`/api/workspaces/${currentWorkspaceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          logo_url: updates.logoUrl,
          logo_emoji: updates.logoEmoji,
          primary_color: updates.primaryColor,
          accent_color: updates.accentColor,
          background_color: updates.backgroundColor,
          sidebar_color: updates.sidebarColor,
          font_family: updates.fontFamily,
        }),
      });
      
      if (!response.ok) {
        if (response.status === 403) {
          alert('⚠️ Permission denied: Only workspace admins can change theme settings.');
        } else {
          console.error('Failed to update workspace theme:', response.status);
        }
        // Revert optimistic update on error
        await get().fetchWorkspaces();
      }
    } catch (error) {
      console.error('Failed to update workspace theme:', error);
      alert('❌ Failed to save theme changes. Please try again.');
      // Revert optimistic update on error
      await get().fetchWorkspaces();
    }
  },

  getCurrentWorkspace: () => {
    const { workspaces, currentWorkspaceId } = get();
    return workspaces.find((w) => w.id === currentWorkspaceId) || null;
  },

  fetchWorkspaces: async () => {
    try {
      const { authFetch } = await import('./auth');
      const response = await authFetch('/api/workspaces');
      if (!response.ok) {
        console.error('Failed to fetch workspaces:', response.status);
        return;
      }
      const apiWorkspaces = await response.json();
      const API_BASE = getApiUrl();
      const normalize = (url?: string | null) => (url && url.startsWith('/') ? `${API_BASE}${url}` : url || undefined);
      // NOTE: API_BASE/normalize defined once to avoid duplicate declarations
      
      const workspaces: Workspace[] = apiWorkspaces.map((ws: any) => ({
        id: ws.id,
        name: ws.name,
        description: ws.description,
        icon: ws.icon || ws.logo_emoji,
        color: ws.color,
        theme: {
          // Inherit org logo if workspace has none; prefer workspace override.
          // Also consider rectangle URL for better presence on lists.
          logoUrl: normalize(ws.logo_url) 
            || normalize(ws.organization_logo_url)
            || normalize(ws.organization_logo_rectangle_url),
          logoEmoji: ws.logo_emoji,
          primaryColor: ws.primary_color || DEFAULT_THEME.primaryColor,
          accentColor: ws.accent_color || DEFAULT_THEME.accentColor,
          backgroundColor: ws.background_color || DEFAULT_THEME.backgroundColor,
          sidebarColor: ws.sidebar_color || DEFAULT_THEME.sidebarColor,
          fontFamily: ws.font_family,
        },
        createdAt: new Date(ws.created_at || Date.now()),
        updatedAt: new Date(ws.updated_at || Date.now()),
        currentUserRole: ws.current_user_role,
        featureFlags: ws.feature_flags,
        platformDriveEnabled: Boolean(ws.platform_drive_enabled),
        systemDriveEnabled: Boolean(ws.system_drive_enabled),
      }));

      set({ workspaces });
      
      // If no current workspace or current one not in list, select first
      const { currentWorkspaceId } = get();
      if (!currentWorkspaceId || !workspaces.find(w => w.id === currentWorkspaceId)) {
        if (workspaces.length > 0) {
          set({ currentWorkspaceId: workspaces[0].id });
        }
      }
    } catch (error) {
      console.error('Failed to fetch workspaces:', error);
    }
  },
}),
    {
      name: 'nexus-workspace-storage',
      storage: createJSONStorage(throttledLocalStorage),
      partialize: (state) => ({
        // Persist these parts of state
        workspaces: state.workspaces,
        currentWorkspaceId: state.currentWorkspaceId,
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
        projects: state.projects,
        sidebarCollapsed: state.sidebarCollapsed,
        expandedSections: state.expandedSections,
        selectedAgent: state.selectedAgent,
        paneAgent: state.paneAgent,
        activePanelSection: state.activePanelSection,
      }),
      onRehydrateStorage: () => (state) => {
        // After hydration completes, fetch workspaces from API
        if (state) {
          // Use setTimeout to ensure we're outside the hydration cycle
          setTimeout(() => {
            state.fetchWorkspaces();
          }, 0);
        }
      },
    }
  )
);
