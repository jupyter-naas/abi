import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
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
  | 'lab'
  | 'ontology'
  | 'graph'
  | 'apps';

// AgentType is now a string to support dynamic agents
export type AgentType = string;

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  agent?: AgentType;
  images?: string[]; // Base64-encoded images for multimodal chat
  thinkingDuration?: number; // Duration in seconds the AI spent "thinking"
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

// ============================================
// GIT-BASED WORKSPACE SYSTEM
// ============================================

export interface WorkspaceBranch {
  id: string;
  name: string;
  description?: string;
  isDefault: boolean;
  isProtected: boolean;
  createdAt: Date;
  updatedAt: Date;
  lastCommitMessage?: string;
  lastCommitBy?: string;
  aheadOfMain?: number;
  behindMain?: number;
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
  branches: WorkspaceBranch[];
  currentBranchId: string;
  createdAt: Date;
  updatedAt: Date;
  isDemo?: boolean;
}

export interface GitCommit {
  id: string;
  message: string;
  author: string;
  timestamp: Date;
  branchId: string;
  changes: number;
}

// Sidebar expandable sections
export type SidebarSection = 'chat' | 'search' | 'files' | 'lab' | 'ontology' | 'graph' | 'apps';

interface WorkspaceState {
  // Navigation
  activeNav: NavigationItem;
  setActiveNav: (nav: NavigationItem) => void;

  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  expandedSections: SidebarSection[];
  toggleSection: (section: SidebarSection) => void;

  // Context panel
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;

  // Chat state
  conversations: Conversation[];
  activeConversationId: string | null;
  selectedAgent: AgentType;
  setSelectedAgent: (agent: AgentType) => void;
  createConversation: (projectId?: string) => string;
  setActiveConversation: (id: string | null) => void;
  addMessage: (conversationId: string, message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateLastMessage: (conversationId: string, content: string, thinkingDuration?: number) => void;
  togglePinConversation: (id: string) => void;
  toggleArchiveConversation: (id: string) => void;
  renameConversation: (id: string, newTitle: string) => void;
  deleteConversation: (id: string) => void;
  getWorkspaceConversations: () => Conversation[];
  setCurrentWorkspace: (id: string) => void;

  // Projects
  projects: Project[];
  createProject: (name: string) => string;

  // ============================================
  // GIT-BASED WORKSPACE SYSTEM
  // ============================================
  workspaces: Workspace[];
  currentWorkspaceId: string | null;
  recentCommits: GitCommit[];

  // Workspace actions
  createWorkspace: (name: string, description?: string) => Workspace;
  deleteWorkspace: (id: string) => void;
  selectWorkspace: (id: string) => void;
  updateWorkspace: (id: string, updates: Partial<Workspace>) => void;
  updateWorkspaceTheme: (updates: Partial<WorkspaceTheme>) => void;
  getCurrentWorkspace: () => Workspace | null;
  fetchWorkspaces: () => Promise<void>;

  // Branch actions
  createBranch: (name: string, description?: string, baseBranchId?: string) => WorkspaceBranch;
  deleteBranch: (branchId: string) => void;
  checkoutBranch: (branchId: string) => void;
  renameBranch: (branchId: string, newName: string) => void;
  getCurrentBranch: () => WorkspaceBranch | null;
  getBranches: () => WorkspaceBranch[];

  // Git operations
  commit: (message: string) => GitCommit | null;
  mergeBranch: (sourceBranchId: string, targetBranchId: string) => boolean;

  // Demo data
  initializeDemoWorkspace: () => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
  // Navigation
  activeNav: 'chat',
  setActiveNav: (nav) => set({ activeNav: nav }),

  // Sidebar
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  expandedSections: ['chat', 'search', 'files', 'lab', 'ontology'] as SidebarSection[],
  toggleSection: (section) =>
    set((state) => ({
      expandedSections: state.expandedSections.includes(section)
        ? state.expandedSections.filter((s) => s !== section)
        : [...state.expandedSections, section],
    })),

  // Context panel
  contextPanelOpen: false,
  toggleContextPanel: () => set((state) => ({ contextPanelOpen: !state.contextPanelOpen })),

  // Chat state
  conversations: [],
  activeConversationId: null,
  selectedAgent: 'aia', // Default to AIA - personal assistant for Chat
  setSelectedAgent: (agent) => set({ selectedAgent: agent }),

  createConversation: (projectId?: string) => {
    const id = generateId();
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

  updateLastMessage: (conversationId, content, thinkingDuration) => {
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

  // Projects
  projects: [],
  createProject: (name) => {
    const id = generateId();
    set((state) => ({
      projects: [...state.projects, { id, name }],
    }));
    return id;
  },

  // ============================================
  // GIT-BASED WORKSPACE SYSTEM
  // ============================================
  workspaces: [],
  currentWorkspaceId: null,
  recentCommits: [],

  // Workspace actions
  createWorkspace: (name, description) => {
    const mainBranch: WorkspaceBranch = {
      id: generateId(),
      name: 'main',
      description: 'Main production branch',
      isDefault: true,
      isProtected: true,
      createdAt: new Date(),
      updatedAt: new Date(),
      lastCommitMessage: 'Initial commit',
      lastCommitBy: useAuthStore.getState().user?.name || 'System',
    };

    const workspace: Workspace = {
      id: generateId(),
      name,
      description,
      theme: { ...DEFAULT_THEME },
      branches: [mainBranch],
      currentBranchId: mainBranch.id,
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
      const response = await authFetch('/api/workspaces/');
      if (!response.ok) {
        console.error('Failed to fetch workspaces:', response.status);
        return;
      }
      const apiWorkspaces = await response.json();
      const API_BASE = getApiUrl();
      const normalize = (url?: string | null) => (url && url.startsWith('/') ? `${API_BASE}${url}` : url || undefined);
      // NOTE: API_BASE/normalize defined once to avoid duplicate declarations
      
      // Transform API workspaces to store format with theme and branches
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
        branches: [{
          id: `branch-main-${ws.id}`,
          name: 'main',
          description: 'Main branch',
          isDefault: true,
          isProtected: true,
          createdAt: new Date(ws.created_at || Date.now()),
          updatedAt: new Date(ws.updated_at || Date.now()),
          lastCommitMessage: 'Initial commit',
          lastCommitBy: 'System',
        }],
        currentBranchId: `branch-main-${ws.id}`,
        createdAt: new Date(ws.created_at || Date.now()),
        updatedAt: new Date(ws.updated_at || Date.now()),
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

  // Branch actions
  createBranch: (name, description, baseBranchId) => {
    const workspace = get().getCurrentWorkspace();
    if (!workspace) throw new Error('No workspace selected');

    const baseBranch = baseBranchId
      ? workspace.branches.find((b) => b.id === baseBranchId)
      : workspace.branches.find((b) => b.isDefault);

    const newBranch: WorkspaceBranch = {
      id: generateId(),
      name,
      description,
      isDefault: false,
      isProtected: false,
      createdAt: new Date(),
      updatedAt: new Date(),
      lastCommitMessage: baseBranch?.lastCommitMessage,
      lastCommitBy: useAuthStore.getState().user?.name || 'System',
      aheadOfMain: 0,
      behindMain: 0,
    };

    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspace.id
          ? {
              ...w,
              branches: [...w.branches, newBranch],
              currentBranchId: newBranch.id,
              updatedAt: new Date(),
            }
          : w
      ),
    }));

    return newBranch;
  },

  deleteBranch: (branchId) => {
    const workspace = get().getCurrentWorkspace();
    if (!workspace) return;

    const branch = workspace.branches.find((b) => b.id === branchId);
    if (!branch || branch.isDefault || branch.isProtected) return;

    const mainBranch = workspace.branches.find((b) => b.isDefault);

    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspace.id
          ? {
              ...w,
              branches: w.branches.filter((b) => b.id !== branchId),
              currentBranchId:
                w.currentBranchId === branchId
                  ? mainBranch?.id || w.branches[0]?.id
                  : w.currentBranchId,
              updatedAt: new Date(),
            }
          : w
      ),
    }));
  },

  checkoutBranch: (branchId) => {
    const workspace = get().getCurrentWorkspace();
    if (!workspace) return;

    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspace.id
          ? { ...w, currentBranchId: branchId, updatedAt: new Date() }
          : w
      ),
    }));
  },

  renameBranch: (branchId, newName) => {
    const workspace = get().getCurrentWorkspace();
    if (!workspace) return;

    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspace.id
          ? {
              ...w,
              branches: w.branches.map((b) =>
                b.id === branchId ? { ...b, name: newName, updatedAt: new Date() } : b
              ),
              updatedAt: new Date(),
            }
          : w
      ),
    }));
  },

  getCurrentBranch: () => {
    const workspace = get().getCurrentWorkspace();
    if (!workspace) return null;
    return workspace.branches.find((b) => b.id === workspace.currentBranchId) || null;
  },

  getBranches: () => {
    const workspace = get().getCurrentWorkspace();
    return workspace?.branches || [];
  },

  // Git operations
  commit: (message) => {
    const workspace = get().getCurrentWorkspace();
    const branch = get().getCurrentBranch();
    if (!workspace || !branch) return null;

    const commit: GitCommit = {
      id: generateId(),
      message,
      author: useAuthStore.getState().user?.name || 'Anonymous',
      timestamp: new Date(),
      branchId: branch.id,
      changes: Math.floor(Math.random() * 10) + 1,
    };

    set((state) => ({
      recentCommits: [commit, ...state.recentCommits].slice(0, 50),
      workspaces: state.workspaces.map((w) =>
        w.id === workspace.id
          ? {
              ...w,
              branches: w.branches.map((b) =>
                b.id === branch.id
                  ? {
                      ...b,
                      lastCommitMessage: message,
                      lastCommitBy: commit.author,
                      updatedAt: new Date(),
                      aheadOfMain: b.isDefault ? 0 : (b.aheadOfMain || 0) + 1,
                    }
                  : b
              ),
              updatedAt: new Date(),
            }
          : w
      ),
    }));

    return commit;
  },

  mergeBranch: (sourceBranchId, targetBranchId) => {
    const workspace = get().getCurrentWorkspace();
    if (!workspace) return false;

    const sourceBranch = workspace.branches.find((b) => b.id === sourceBranchId);
    const targetBranch = workspace.branches.find((b) => b.id === targetBranchId);
    if (!sourceBranch || !targetBranch) return false;

    // Create a merge commit
    get().commit(`Merge branch '${sourceBranch.name}' into '${targetBranch.name}'`);

    // Reset ahead/behind counters
    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspace.id
          ? {
              ...w,
              branches: w.branches.map((b) =>
                b.id === sourceBranchId
                  ? { ...b, aheadOfMain: 0, behindMain: 0, updatedAt: new Date() }
                  : b
              ),
              updatedAt: new Date(),
            }
          : w
      ),
    }));

    return true;
  },

  // Initialize demo workspace with sample data
  initializeDemoWorkspace: () => {
    const { workspaces } = get();
    
    // Check if Nexus workspace already exists
    if (workspaces.some((w) => w.name === 'Nexus')) return;

    // Create main branch
    const mainBranch: WorkspaceBranch = {
      id: 'branch-main',
      name: 'main',
      description: 'Main production branch - always stable',
      isDefault: true,
      isProtected: true,
      createdAt: new Date('2026-01-01'),
      updatedAt: new Date(),
      lastCommitMessage: 'Release v1.0.0 - Production ready',
      lastCommitBy: 'System',
    };

    // Create demo branch
    const demoBranch: WorkspaceBranch = {
      id: 'branch-demo',
      name: 'demo',
      description: 'Demo branch with sample data - use this to explore the platform',
      isDefault: false,
      isProtected: true,
      createdAt: new Date('2026-01-15'),
      updatedAt: new Date(),
      lastCommitMessage: 'Add aviation demo scenario with BFO 7 Buckets',
      lastCommitBy: 'AI Assistant',
      aheadOfMain: 5,
      behindMain: 0,
    };

    // Create development branch
    const devBranch: WorkspaceBranch = {
      id: 'branch-dev',
      name: 'development',
      description: 'Active development branch',
      isDefault: false,
      isProtected: false,
      createdAt: new Date('2026-02-01'),
      updatedAt: new Date(),
      lastCommitMessage: 'WIP: Knowledge graph vis.js integration',
      lastCommitBy: 'Developer',
      aheadOfMain: 12,
      behindMain: 0,
    };

    // Create feature branch
    const featureBranch: WorkspaceBranch = {
      id: 'branch-feature-ontology',
      name: 'feature/ontology-import',
      description: 'Feature branch for ontology import improvements',
      isDefault: false,
      isProtected: false,
      createdAt: new Date('2026-02-03'),
      updatedAt: new Date(),
      lastCommitMessage: 'Implement BFO reference import',
      lastCommitBy: 'Developer',
      aheadOfMain: 3,
      behindMain: 2,
    };

    const nexusWorkspace: Workspace = {
      id: 'workspace-nexus',
      name: 'Nexus',
      description: 'Enterprise Knowledge Platform - Your organization\'s central data hub',
      icon: '🔮',
      color: '#22c55e',
      theme: {
        logoEmoji: '🔮',
        primaryColor: '#22c55e',
        accentColor: '#3b82f6',
        backgroundColor: '#0a0a0a',
        sidebarColor: '#111111',
      },
      branches: [mainBranch, demoBranch, devBranch, featureBranch],
      currentBranchId: demoBranch.id, // Start on demo branch
      createdAt: new Date('2026-01-01'),
      updatedAt: new Date(),
    };

    // Create default main branch for other workspaces
    const createDefaultBranch = (): WorkspaceBranch => ({
      id: `branch-main-${generateId()}`,
      name: 'main',
      description: 'Main branch',
      isDefault: true,
      isProtected: true,
      createdAt: new Date(),
      updatedAt: new Date(),
      lastCommitMessage: 'Initial commit',
      lastCommitBy: 'System',
    });

    // Forvis Mazars Workspace
    const forvisMazarsWorkspace: Workspace = {
      id: 'workspace-forvis-mazars',
      name: 'Forvis Mazars',
      description: 'Global audit, tax and advisory firm - Knowledge management platform',
      icon: '🏛️',
      color: '#0066cc',
      theme: {
        logoEmoji: '🏛️',
        primaryColor: '#0066cc',
        accentColor: '#00a3e0',
        backgroundColor: '#0a0a0a',
        sidebarColor: '#111111',
      },
      branches: [createDefaultBranch()],
      currentBranchId: 'branch-main',
      createdAt: new Date('2026-01-15'),
      updatedAt: new Date(),
    };
    forvisMazarsWorkspace.currentBranchId = forvisMazarsWorkspace.branches[0].id;

    // NCOR Workspace
    const ncorWorkspace: Workspace = {
      id: 'workspace-ncor',
      name: 'NCOR',
      description: 'National Center for Ontological Research - BFO and applied ontology',
      icon: '🔬',
      color: '#8b5cf6',
      theme: {
        logoEmoji: '🔬',
        primaryColor: '#8b5cf6',
        accentColor: '#a78bfa',
        backgroundColor: '#0a0a0a',
        sidebarColor: '#111111',
      },
      branches: [createDefaultBranch()],
      currentBranchId: 'branch-main',
      createdAt: new Date('2026-01-20'),
      updatedAt: new Date(),
    };
    ncorWorkspace.currentBranchId = ncorWorkspace.branches[0].id;

    // Acacia Workspace
    const acaciaWorkspace: Workspace = {
      id: 'workspace-acacia',
      name: 'Acacia',
      description: 'Enterprise data integration and analytics platform',
      icon: '🌳',
      color: '#10b981',
      theme: {
        logoEmoji: '🌳',
        primaryColor: '#10b981',
        accentColor: '#34d399',
        backgroundColor: '#0a0a0a',
        sidebarColor: '#111111',
      },
      branches: [createDefaultBranch()],
      currentBranchId: 'branch-main',
      createdAt: new Date('2026-01-25'),
      updatedAt: new Date(),
    };
    acaciaWorkspace.currentBranchId = acaciaWorkspace.branches[0].id;

    // NaasAI Workspace
    const naasaiWorkspace: Workspace = {
      id: 'workspace-naasai',
      name: 'NaasAI',
      description: 'AI-powered data platform - Notebooks as a Service',
      icon: '🚀',
      color: '#f97316',
      theme: {
        logoEmoji: '🚀',
        primaryColor: '#f97316',
        accentColor: '#fb923c',
        backgroundColor: '#0a0a0a',
        sidebarColor: '#111111',
      },
      branches: [createDefaultBranch()],
      currentBranchId: 'branch-main',
      createdAt: new Date('2026-01-10'),
      updatedAt: new Date(),
    };
    naasaiWorkspace.currentBranchId = naasaiWorkspace.branches[0].id;

    set((state) => ({
      workspaces: [
        nexusWorkspace,
        forvisMazarsWorkspace,
        ncorWorkspace,
        acaciaWorkspace,
        naasaiWorkspace,
        ...state.workspaces,
      ],
      currentWorkspaceId: nexusWorkspace.id,
    }));
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
