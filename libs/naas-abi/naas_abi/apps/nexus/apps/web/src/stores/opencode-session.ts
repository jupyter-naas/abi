import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import type { OpencodeSession } from '@/lib/opencode-sessions';
import { useAuthStore } from './auth';

const getApiBase = () => getApiUrl();

const authHeaders = (): Record<string, string> => {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

interface OpencodeSessionStore {
  opencodeSessionId: string;
  ocSessions: OpencodeSession[];
  canForkSession: boolean;
  setOpencodeSessionId: (id: string) => void;
  setCanForkSession: (value: boolean) => void;
  fetchOcSessions: () => Promise<OpencodeSession[]>;
  fetchSessionDiff: (sessionId: string) => Promise<void>;
  createOcSession: (title?: string) => Promise<OpencodeSession | null>;
  forkOcSession: (sessionId: string, messageId?: string) => Promise<OpencodeSession | null>;
}

export const useOpencodeSessionStore = create<OpencodeSessionStore>((set, get) => ({
  opencodeSessionId: `nexus-${Date.now()}`,
  ocSessions: [],
  canForkSession: false,

  setOpencodeSessionId: (id) => {
    set({ opencodeSessionId: id });
    // Clear per-session tracking when the user switches sessions.
    import('./files').then(({ useFilesStore }) => {
      const store = useFilesStore.getState();
      store.clearLocalChanges();
      store.clearOriginalContents();
    });
  },

  setCanForkSession: (value) => set({ canForkSession: value }),

  fetchOcSessions: async () => {
    try {
      const r = await fetch(`${getApiBase()}/api/opencode/sessions`, {
        headers: authHeaders(),
      });
      if (!r.ok) return get().ocSessions;
      const data = await r.json();
      const sessions = (Array.isArray(data) ? data : []) as OpencodeSession[];
      set({ ocSessions: sessions });
      return sessions;
    } catch {
      return get().ocSessions;
    }
  },

  fetchSessionDiff: async (sessionId) => {
    if (!sessionId || sessionId.startsWith('nexus-')) {
      const { useFilesStore } = await import('./files');
      useFilesStore.getState().clearCodeDiffs();
      return;
    }
    try {
      const r = await fetch(`${getApiBase()}/api/opencode/sessions/${sessionId}/diff`, {
        headers: authHeaders(),
      });
      const { useFilesStore } = await import('./files');
      const filesStore = useFilesStore.getState();
      if (!r.ok) {
        filesStore.clearCodeDiffs();
        return;
      }
      const data = await r.json();
      const diffs = (Array.isArray(data) ? data : []) as import('@/lib/code-diff').CodeDiffEntry[];
      filesStore.replaceCodeDiffs(diffs);
    } catch {
      /* ignore */
    }
  },

  createOcSession: async (title = 'New session') => {
    try {
      const r = await fetch(`${getApiBase()}/api/opencode/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ title }),
      });
      if (!r.ok) return null;
      const created = (await r.json()) as OpencodeSession;
      set({ opencodeSessionId: created.id, canForkSession: false });
      await get().fetchOcSessions();
      await get().fetchSessionDiff(created.id);
      return created;
    } catch {
      return null;
    }
  },

  forkOcSession: async (sessionId, messageId = '') => {
    try {
      const body = messageId ? { message_id: messageId } : {};
      const r = await fetch(`${getApiBase()}/api/opencode/sessions/${sessionId}/fork`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      });
      if (!r.ok) return null;
      const forked = (await r.json()) as OpencodeSession;
      set({ opencodeSessionId: forked.id });
      await get().fetchOcSessions();
      await get().fetchSessionDiff(forked.id);
      return forked;
    } catch {
      return null;
    }
  },
}));
