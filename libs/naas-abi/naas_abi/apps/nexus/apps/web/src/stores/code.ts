import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CodeSession {
  id: string;
  name: string;
  rootPath: string;
  createdAt: string;
}

interface CodeStore {
  sessions: CodeSession[];
  activeSessionId: string | null;

  createSession: (name: string, rootPath: string) => void;
  deleteSession: (id: string) => void;
  setActiveSession: (id: string | null) => void;
  getActiveSession: () => CodeSession | null;
}

export const useCodeStore = create<CodeStore>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,

      createSession: (name, rootPath) => {
        const session: CodeSession = {
          id: Date.now().toString(),
          name,
          rootPath,
          createdAt: new Date().toISOString(),
        };
        set((state) => ({
          sessions: [...state.sessions, session],
          activeSessionId: session.id,
        }));
      },

      deleteSession: (id) => {
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== id),
          activeSessionId: state.activeSessionId === id
            ? (state.sessions.find((s) => s.id !== id)?.id ?? null)
            : state.activeSessionId,
        }));
      },

      setActiveSession: (id) => set({ activeSessionId: id }),

      getActiveSession: () => {
        const { sessions, activeSessionId } = get();
        return sessions.find((s) => s.id === activeSessionId) ?? null;
      },
    }),
    { name: 'nexus-code-sessions' }
  )
);
