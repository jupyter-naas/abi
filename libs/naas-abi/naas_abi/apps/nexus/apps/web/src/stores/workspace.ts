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
  | 'maps'
  | 'chat'
  | 'search'
  | 'files'
  | 'lab'
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
  status: 'running' | 'done' | 'awaiting_approval';
  input?: string;
  output?: string;
}

export type MessageFeedback = 'like' | 'dislike';

export interface MessageFeedbackDetails {
  type?: string | null;
  detail?: string | null;
  severity?: number | null;
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
  fileAttachments?: string[]; // Filenames of uploaded documents attached to this message
  thinkingDuration?: number; // Duration in seconds the AI spent "thinking"
  executionTime?: number; // Total seconds from request sent to response complete
  sources?: string[]; // filenames of RAG documents used to answer
  feedback?: MessageFeedback | null; // Reviewer thumbs up/down, persisted on metadata_
  feedbackDetails?: MessageFeedbackDetails | null; // Extended dislike details (type/detail/severity)
  // Chat "refresh" lineage. Every one of these messages is displayed; the flags
  // only shape what the model is given on later turns — see getModelHistory().
  regenerateOf?: string; // Assistant message id this turn re-ran
  supersededBy?: string; // Newer answer that replaced this one (set server-side)
  replayedPrompt?: boolean; // Prompt re-sent by a refresh (duplicate of an earlier one)
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
  // True for conversations created locally that have not yet been persisted
  // to the backend. Cleared once a message is sent or the conversation is
  // confirmed via syncWorkspaceConversations / loadConversationMessages.
  isDraft?: boolean;
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
  currentUserRole?: string;
  featureFlags?: WorkspaceFeatureFlags;
  platformDriveEnabled?: boolean;
  systemDriveEnabled?: boolean;
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
export type SidebarSection = 'maps' | 'chat' | 'search' | 'files' | 'lab' | 'code' | 'slides' | 'ontology' | 'graph' | 'apps' | 'marketplace' | 'settings';

export interface OpenAppModule {
  module_path: string;
  module_name?: string;
  name: string;
  description?: string;
  logo_url: string | null;
  icon_emoji?: string | null;
  category: string;
  app_url?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  maintainer?: string | null;
  tier?: string | null;
  version?: string | null;
  author?: string | null;
  license?: string | null;
  keywords?: string[];
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
  /** True when the Apps panel shows app metadata instead of the app list.
   *  Opt-in only — opening an app never sets it. Not persisted. */
  appDetailOpen: boolean;
  setAppDetailOpen: (open: boolean) => void;

  // Context panel (right AI / compare surface)
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;
  /** Width of the secondary left section panel (px). Persisted. */
  sectionPanelWidth: number;
  setSectionPanelWidth: (width: number) => void;
  /** Width of the right AI / compare pane (px). Persisted. */
  aiPaneWidth: number;
  setAiPaneWidth: (width: number) => void;

  // Chat state
  conversations: Conversation[];
  activeConversationId: string | null;
  selectedAgent: AgentType;
  /** True when the user deliberately picked an agent (sidebar or composer),
   *  false when the agent was auto-selected as the workspace default.
   *  Drives the sidebar highlight: "New Chat" vs a specific agent. Not persisted. */
  agentExplicitlySelected: boolean;
  setSelectedAgent: (agent: AgentType, explicit?: boolean) => void;
  /** Drop the explicit selection without changing the agent — landing back on
   *  the chat route will then reset to the workspace default. */
  clearAgentExplicitSelection: () => void;
  /** One-shot text to seed the chat composer with (e.g. "/skill-slug " from the
   *  sidebar). Consumed and cleared by ChatInterface. Not persisted. */
  pendingComposerText: string | null;
  setPendingComposerText: (text: string | null) => void;
  /** Mobile list→thread navigation in flight (conversation id or "new"). Not persisted. */
  mobilePendingChatSlug: string | null;
  setMobilePendingChatSlug: (slug: string | null) => void;
  paneAgent: AgentType; // AI Pane agent selection (defaults to Abi)
  /** True when the user picked an AI Pane agent from the menu. */
  paneAgentExplicitlySelected: boolean;
  setPaneAgent: (agent: AgentType, explicit?: boolean) => void;
  clearPaneAgentExplicitSelection: () => void;
  /** Independent conversation bound to the right AI / compare pane. */
  paneConversationId: string | null;
  setPaneConversationId: (id: string | null) => void;
  /** Open conversation tabs in the right chat pane (Cursor-style). */
  paneOpenTabIds: string[];
  /** Open (or focus) a conversation as a pane tab. */
  openPaneTab: (id: string) => void;
  /** Close a pane tab; focuses a neighbor or blank new chat. */
  closePaneTab: (id: string) => void;
  createConversation: (
    projectId?: string,
    options?: { surface?: 'main' | 'pane' },
  ) => string;
  setActiveConversation: (id: string | null) => void;
  /** Record the latest agent used in a conversation (mirrors the backend,
   *  which updates conversation.agent on every send). */
  setConversationAgent: (conversationId: string, agent: AgentType) => void;
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
  updateMessageFeedback: (
    conversationId: string,
    messageId: string,
    feedback: MessageFeedback | null,
    details?: MessageFeedbackDetails | null,
  ) => void;
  renameMessageId: (
    conversationId: string,
    oldMessageId: string,
    newMessageId: string,
  ) => void;
  removeLastAssistantMessage: (conversationId: string) => void;
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
const generateConversationId = () => `conv-${Math.random().toString(36).substring(2, 14)}`;

type ApiChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string | null;
  created_at?: string;
  metadata?: Record<string, unknown> | null;
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

const isFailedAnswer = (message: Message): boolean => {
  const body = message.content.replace('▌', '').trim();
  return !body || body.startsWith('❌ Error:');
};

/**
 * The transcript as the model should see it. Every message is rendered in the
 * chat — this is only about context: a refresh must not hand the model the
 * answer it is re-running, or it repeats it instead of redoing the work.
 *
 * Superseded answers are derived from the turns themselves: a refresh tags its
 * answer with the one it re-ran, so a completed replacement drops the original.
 * A refresh that failed or is still empty drops nothing, and the rule re-derives
 * itself identically after a reload, whatever local state was lost.
 */
export const getModelHistory = (messages: Message[]): Message[] => {
  const replaced = new Set<string>();
  for (const message of messages) {
    if (message.role !== 'assistant' || !message.regenerateOf) continue;
    if (isFailedAnswer(message)) continue;
    replaced.add(message.regenerateOf);
  }
  return messages.filter(
    (message) =>
      !message.replayedPrompt &&
      !replaced.has(message.id) &&
      typeof message.supersededBy !== 'string',
  );
};

const mapApiMessage = (message: ApiChatMessage): Message => {
  const meta = message.metadata ?? {};
  const supersededBy = meta.superseded_by;
  const regenerateOf = meta.regenerate_of;
  const fb = meta.feedback;
  const fbType = meta.feedback_type;
  const fbDetail = meta.feedback_detail;
  const fbSeverity = meta.feedback_severity;
  const hasDetails =
    typeof fbType === 'string' ||
    typeof fbDetail === 'string' ||
    typeof fbSeverity === 'number';
  const rawSteps = meta.steps;
  const toolCalls = Array.isArray(rawSteps)
    ? rawSteps
        .map((step): ToolCall | null => {
          if (!step || typeof step !== 'object') return null;
          const record = step as Record<string, unknown>;
          const toolName = typeof record.tool_name === 'string' ? record.tool_name : '';
          const prefix = typeof record.prefix === 'string' ? record.prefix : 'Tool';
          const status =
            record.status === 'running'
              ? 'running'
              : record.status === 'awaiting_approval'
                ? 'awaiting_approval'
                : 'done';
          if (!toolName) return null;
          return {
            id: `${message.id}-step-${toolName}`,
            toolName,
            rawName: toolName,
            prefix: prefix as ToolCall['prefix'],
            status,
            input: typeof record.input === 'string' ? record.input : undefined,
            output: typeof record.output === 'string' ? record.output : undefined,
          };
        })
        .filter((step): step is ToolCall => step !== null)
    : undefined;
  const rawSources = meta.sources;
  const sources = Array.isArray(rawSources)
    ? rawSources.filter((src): src is string => typeof src === 'string' && src.length > 0)
    : undefined;
  const executionTime =
    typeof meta.execution_time === 'number' ? meta.execution_time : undefined;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: new Date(message.created_at || Date.now()),
    agent: message.agent || undefined,
    toolCalls: toolCalls && toolCalls.length > 0 ? toolCalls : undefined,
    sources: sources && sources.length > 0 ? sources : undefined,
    executionTime,
    // Refresh lineage, rebuilt from server metadata so getModelHistory() reaches
    // the same verdict after a reload as it did live.
    ...(typeof regenerateOf === 'string' ? { regenerateOf } : {}),
    ...(typeof supersededBy === 'string' ? { supersededBy } : {}),
    ...(meta.regenerate_replay === true ? { replayedPrompt: true } : {}),
    feedback: fb === 'like' || fb === 'dislike' ? fb : null,
    feedbackDetails: hasDetails
      ? {
          type: typeof fbType === 'string' ? fbType : null,
          detail: typeof fbDetail === 'string' ? fbDetail : null,
          severity: typeof fbSeverity === 'number' ? fbSeverity : null,
        }
      : null,
  };
};

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
  // Clearing the open app also drops the detail view: there is nothing to show.
  setOpenAppModule: (mod) => set(mod ? { openAppModule: mod } : { openAppModule: null, appDetailOpen: false }),
  appDetailOpen: false,
  setAppDetailOpen: (open) => set({ appDetailOpen: open }),

  // Context panel (right AI / compare surface)
  contextPanelOpen: false,
  toggleContextPanel: () => set((state) => ({ contextPanelOpen: !state.contextPanelOpen })),
  sectionPanelWidth: 256,
  setSectionPanelWidth: (width) =>
    set({ sectionPanelWidth: Math.max(200, Math.min(480, Math.round(width))) }),
  aiPaneWidth: 440,
  setAiPaneWidth: (width) =>
    set({ aiPaneWidth: Math.max(320, Math.min(720, Math.round(width))) }),

  // Chat state
  conversations: [],
  activeConversationId: null,
  selectedAgent: '',
  agentExplicitlySelected: false,
  setSelectedAgent: (agent, explicit = false) =>
    set({ selectedAgent: agent, agentExplicitlySelected: explicit }),
  clearAgentExplicitSelection: () => set({ agentExplicitlySelected: false }),
  pendingComposerText: null,
  setPendingComposerText: (text) => set({ pendingComposerText: text }),
  mobilePendingChatSlug: null,
  setMobilePendingChatSlug: (slug) => set({ mobilePendingChatSlug: slug }),
  paneAgent: '', // Resolved to Abi after agents sync (see agents store)
  paneAgentExplicitlySelected: false,
  setPaneAgent: (agent, explicit = false) =>
    set({ paneAgent: agent, paneAgentExplicitlySelected: explicit }),
  clearPaneAgentExplicitSelection: () => set({ paneAgentExplicitlySelected: false }),
  paneConversationId: null,
  paneOpenTabIds: [],
  setPaneConversationId: (id) =>
    set((state) => {
      const conv = id ? state.conversations.find((c) => c.id === id) : null;
      const paneOpenTabIds =
        id && !state.paneOpenTabIds.includes(id)
          ? [...state.paneOpenTabIds, id]
          : state.paneOpenTabIds;
      // Opening a history tab syncs the composer agent for that thread, but must
      // NOT mark paneAgentExplicitlySelected. That flag is only for picker choices;
      // treating tabs as explicit locked non-Abi agents across New chat / refresh.
      if (!id) {
        return {
          paneConversationId: null,
          paneOpenTabIds,
        };
      }
      return {
        paneConversationId: id,
        paneOpenTabIds,
        ...(conv?.agent ? { paneAgent: conv.agent } : {}),
      };
    }),
  openPaneTab: (id) => {
    get().setPaneConversationId(id);
  },
  closePaneTab: (id) =>
    set((state) => {
      const paneOpenTabIds = state.paneOpenTabIds.filter((tabId) => tabId !== id);
      if (state.paneConversationId !== id) {
        return { paneOpenTabIds };
      }
      const closedIndex = state.paneOpenTabIds.indexOf(id);
      const nextId =
        paneOpenTabIds[Math.min(closedIndex, paneOpenTabIds.length - 1)] ?? null;
      const conv = nextId ? state.conversations.find((c) => c.id === nextId) : null;
      return {
        paneOpenTabIds,
        paneConversationId: nextId,
        ...(conv?.agent ? { paneAgent: conv.agent } : {}),
      };
    }),

  createConversation: (projectId?: string, options?: { surface?: 'main' | 'pane' }) => {
    const id = generateConversationId();
    const workspaceId = get().currentWorkspaceId;
    const surface = options?.surface ?? 'main';
    if (!workspaceId) {
      console.error('Cannot create conversation: no workspace selected');
      return id;
    }
    const agent = surface === 'pane' ? get().paneAgent : get().selectedAgent;
    const newConversation: Conversation = {
      id,
      workspaceId,
      title: 'New Conversation',
      messages: [],
      agent,
      createdAt: new Date(),
      updatedAt: new Date(),
      pinned: false,
      projectId,
      isDraft: true,
    };
    set((state) => ({
      conversations: [newConversation, ...state.conversations],
      ...(surface === 'pane'
        ? {
            paneConversationId: id,
            paneOpenTabIds: state.paneOpenTabIds.includes(id)
              ? state.paneOpenTabIds
              : [...state.paneOpenTabIds, id],
          }
        : { activeConversationId: id }),
    }));
    return id;
  },

  setActiveConversation: (id) =>
    set((state) => {
      // Opening a conversation restores its latest agent in the composer.
      const conv = id ? state.conversations.find((c) => c.id === id) : null;
      return {
        activeConversationId: id,
        ...(conv?.agent
          ? { selectedAgent: conv.agent, agentExplicitlySelected: false }
          : {}),
      };
    }),

  setConversationAgent: (conversationId, agent) =>
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId && conv.agent !== agent
          ? { ...conv, agent, updatedAt: new Date() }
          : conv
      ),
    })),

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
              isDraft: false,
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

  removeLastAssistantMessage: (conversationId) => {
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: (() => {
                const next = [...conv.messages];
                for (let i = next.length - 1; i >= 0; i -= 1) {
                  if (next[i].role === 'assistant') {
                    next.splice(i, 1);
                    break;
                  }
                }
                return next;
              })(),
              updatedAt: new Date(),
            }
          : conv,
      ),
    }));
  },

  updateMessageFeedback: (conversationId, messageId, feedback, details) => {
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: conv.messages.map((msg) =>
                msg.id === messageId
                  ? {
                      ...msg,
                      feedback,
                      feedbackDetails:
                        details === undefined ? msg.feedbackDetails : details,
                    }
                  : msg,
              ),
            }
          : conv,
      ),
    }));
  },

  renameMessageId: (conversationId, oldMessageId, newMessageId) => {
    if (!oldMessageId || !newMessageId || oldMessageId === newMessageId) return;
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: conv.messages.map((msg) =>
                msg.id === oldMessageId ? { ...msg, id: newMessageId } : msg,
              ),
            }
          : conv,
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
    set((state) => {
      const paneOpenTabIds = state.paneOpenTabIds.filter((tabId) => tabId !== id);
      const paneConversationId =
        state.paneConversationId === id
          ? paneOpenTabIds[paneOpenTabIds.length - 1] ?? null
          : state.paneConversationId;
      return {
        conversations: state.conversations.filter((c) => c.id !== id),
        activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
        paneOpenTabIds,
        paneConversationId,
      };
    });
    
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
    set((state) => ({
      currentWorkspaceId: id,
      activeConversationId: null,
      // Pane tabs are workspace-scoped. Leaving paneConversationId on a thread
      // from the previous workspace made send update a hidden conversation while
      // the right pane stayed empty (composer cleared, nothing visible).
      ...(state.currentWorkspaceId !== id
        ? { paneConversationId: null, paneOpenTabIds: [] as string[] }
        : {}),
    }));
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
        const apiIds = new Set(fromApi.map((c) => c.id));
        const mergedWorkspaceConversations = fromApi.map((apiConv) => {
          const existing = existingById.get(apiConv.id);
          if (!existing) return apiConv;
          return {
            ...apiConv,
            // Preserve loaded message history if we already have it in memory.
            messages: existing.messages.length > 0 ? existing.messages : apiConv.messages,
            isDraft: false,
          };
        });
        // Keep local-only threads that sync would otherwise drop (drafts, in-flight
        // first sends, open pane tabs). Dropping them left paneConversationId
        // pointing at a missing row so send cleared the composer with no UI update.
        const localOnly = state.conversations.filter((c) => {
          if (c.workspaceId !== targetWorkspaceId || apiIds.has(c.id)) return false;
          return (
            Boolean(c.isDraft) ||
            c.messages.length > 0 ||
            c.id === state.activeConversationId ||
            c.id === state.paneConversationId ||
            state.paneOpenTabIds.includes(c.id)
          );
        });
        const otherWorkspaces = state.conversations.filter(
          (c) => c.workspaceId !== targetWorkspaceId
        );
        const conversations = [
          ...mergedWorkspaceConversations,
          ...localOnly,
          ...otherWorkspaces,
        ].sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
        const knownIds = new Set(conversations.map((c) => c.id));
        const paneOpenTabIds = state.paneOpenTabIds.filter((id) => knownIds.has(id));
        const paneConversationId =
          state.paneConversationId && knownIds.has(state.paneConversationId)
            ? state.paneConversationId
            : null;
        const activeConversationId =
          state.activeConversationId && knownIds.has(state.activeConversationId)
            ? state.activeConversationId
            : null;
        return {
          conversations,
          paneOpenTabIds,
          paneConversationId,
          activeConversationId,
        };
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
        const existing = state.conversations.find((c) => c.id === mapped.id);
        // Preserve optimistic local messages (e.g. user just sent) that the API
        // snapshot does not include yet. Blind replace made send look like a no-op.
        const apiIds = new Set(mapped.messages.map((m) => m.id));
        const localOnly = existing
          ? existing.messages.filter((m) => !apiIds.has(m.id))
          : [];
        const merged: Conversation = {
          ...mapped,
          messages:
            mapped.messages.length === 0 && localOnly.length > 0
              ? existing!.messages
              : localOnly.length > 0
                ? [...mapped.messages, ...localOnly]
                : mapped.messages,
          isDraft: false,
        };
        const conversations = existing
          ? state.conversations.map((c) => (c.id === merged.id ? merged : c))
          : [merged, ...state.conversations];
        // If this conversation is the one on screen, reflect its latest agent
        // in the composer (unless the user just explicitly picked another one).
        const syncAgent =
          state.activeConversationId === mapped.id &&
          !state.agentExplicitlySelected &&
          mapped.agent;
        return {
          conversations,
          ...(syncAgent ? { selectedAgent: mapped.agent } : {}),
        };
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
    if (!useAuthStore.getState().token) return;
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
        paneAgent: state.paneAgent,
        // Do not persist paneAgentExplicitlySelected (same as main chat): a hard
        // refresh should re-default the right pane to Abi via agents sync.
        paneConversationId: state.paneConversationId,
        paneOpenTabIds: state.paneOpenTabIds,
        activePanelSection: state.activePanelSection,
        sectionPanelWidth: state.sectionPanelWidth,
        aiPaneWidth: state.aiPaneWidth,
      }),
      onRehydrateStorage: () => (state) => {
        // After hydration completes, fetch workspaces from API
        if (state) {
          // Drop legacy persisted paneAgentExplicitlySelected so hard refresh
          // re-defaults the right pane to Abi (agents sync), matching main chat.
          state.paneAgentExplicitlySelected = false;
          // Drop pane tabs that belong to another workspace (or missing rows).
          const ws = state.currentWorkspaceId;
          const known = new Set(
            state.conversations
              .filter((c) => !ws || c.workspaceId === ws)
              .map((c) => c.id)
          );
          state.paneOpenTabIds = (state.paneOpenTabIds || []).filter((id) => known.has(id));
          if (state.paneConversationId && !known.has(state.paneConversationId)) {
            state.paneConversationId = null;
          }
          // Use setTimeout to ensure we're outside the hydration cycle
          setTimeout(() => {
            state.fetchWorkspaces();
          }, 0);
        }
      },
    }
  )
);
