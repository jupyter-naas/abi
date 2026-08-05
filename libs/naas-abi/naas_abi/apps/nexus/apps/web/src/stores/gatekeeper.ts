import { create } from 'zustand';

export interface ResourceGrant {
  chatId: string;
  resourceType: string;
  resourceId: string;
  actions: string[];
  grantedAt: string;
}

export interface GrantResourceInput {
  resourceType: string;
  resourceId: string;
  actions: string[];
}

export interface GatekeeperPendingRetry {
  userMessage: string;
  agent: string;
  images?: string[];
  fileAttachments?: string[];
}

interface GatekeeperState {
  grantsByConversation: Record<string, ResourceGrant[]>;
  pendingRetryByConversation: Record<string, GatekeeperPendingRetry>;
  grantConversation: (
    workspaceId: string,
    conversationId: string,
    input: GrantResourceInput,
  ) => Promise<ResourceGrant>;
  fetchGrants: (
    workspaceId: string,
    conversationId: string,
    force?: boolean,
  ) => Promise<ResourceGrant[]>;
  hasGrant: (
    conversationId: string,
    resourceType: string,
    resourceId: string,
    action: string,
  ) => boolean;
  setPendingRetry: (conversationId: string, retry: GatekeeperPendingRetry) => void;
  getPendingRetry: (conversationId: string) => GatekeeperPendingRetry | null;
  clearPendingRetry: (conversationId: string) => void;
}

const mapApiGrant = (g: Record<string, unknown>): ResourceGrant => ({
  chatId: String(g.chat_id ?? ''),
  resourceType: String(g.resource_type ?? ''),
  resourceId: String(g.resource_id ?? ''),
  actions: Array.isArray(g.actions) ? g.actions.map(String) : [],
  grantedAt: String(g.granted_at ?? ''),
});

const apiHelpers = async () => {
  const { authFetch } = await import('./auth');
  const { getApiUrl } = await import('@/lib/config');
  return { authFetch, API_BASE: getApiUrl() };
};

const readDetail = async (response: Response, fallback: string): Promise<string> => {
  try {
    const body = await response.json();
    return body?.detail || fallback;
  } catch {
    return fallback;
  }
};

export const useGatekeeperStore = create<GatekeeperState>()((set, get) => ({
  grantsByConversation: {},
  pendingRetryByConversation: {},

  fetchGrants: async (workspaceId, conversationId, force = false) => {
    const cached = get().grantsByConversation[conversationId];
    if (!force && cached) return cached;

    const { authFetch, API_BASE } = await apiHelpers();
    const url =
      `${API_BASE}/api/gatekeeper/conversations/${encodeURIComponent(conversationId)}/grants` +
      `?workspace_id=${encodeURIComponent(workspaceId)}`;
    const response = await authFetch(url);
    if (!response.ok) {
      throw new Error(await readDetail(response, 'Failed to load gatekeeper grants'));
    }
    const data = await response.json();
    const grants = Array.isArray(data) ? data.map(mapApiGrant) : [];
    set((state) => ({
      grantsByConversation: {
        ...state.grantsByConversation,
        [conversationId]: grants,
      },
    }));
    return grants;
  },

  grantConversation: async (workspaceId, conversationId, input) => {
    const { authFetch, API_BASE } = await apiHelpers();
    const url =
      `${API_BASE}/api/gatekeeper/conversations/${encodeURIComponent(conversationId)}/grants` +
      `?workspace_id=${encodeURIComponent(workspaceId)}`;
    const response = await authFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resource_type: input.resourceType,
        resource_id: input.resourceId,
        actions: input.actions,
      }),
    });
    if (!response.ok) {
      throw new Error(await readDetail(response, 'Failed to grant access'));
    }
    const grant = mapApiGrant(await response.json());
    set((state) => {
      const existing = state.grantsByConversation[conversationId] ?? [];
      const filtered = existing.filter(
        (g) =>
          !(
            g.resourceType === grant.resourceType &&
            g.resourceId === grant.resourceId
          ),
      );
      return {
        grantsByConversation: {
          ...state.grantsByConversation,
          [conversationId]: [...filtered, grant],
        },
      };
    });
    return grant;
  },

  hasGrant: (conversationId, resourceType, resourceId, action) => {
    const grants = get().grantsByConversation[conversationId] ?? [];
    return grants.some(
      (grant) =>
        grant.resourceType === resourceType &&
        grant.resourceId === resourceId &&
        (grant.actions.includes(action) || grant.actions.includes('*')),
    );
  },

  setPendingRetry: (conversationId, retry) => {
    set((state) => ({
      pendingRetryByConversation: {
        ...state.pendingRetryByConversation,
        [conversationId]: retry,
      },
    }));
  },

  getPendingRetry: (conversationId) =>
    get().pendingRetryByConversation[conversationId] ?? null,

  clearPendingRetry: (conversationId) => {
    set((state) => {
      if (!state.pendingRetryByConversation[conversationId]) return state;
      const next = { ...state.pendingRetryByConversation };
      delete next[conversationId];
      return { pendingRetryByConversation: next };
    });
  },
}));
