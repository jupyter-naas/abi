import { useEffect } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authFetch } from '@/stores/auth';

/** Shared selection for the Code sub-app: which repository the Workspaces /
 * Branches / Pull-requests views operate on. Persisted so it survives reloads
 * and is shared between the section panel (selector) and the pages. */
interface CodeState {
  selectedRepoId: string;
  /** Active git ref when browsing a repo (real Forgejo branch, not navbar fake). */
  activeBranch: string | null;
  /** Bound Coder workspace name when one is selected / running for the repo. */
  coderWorkspace: string | null;
  coderPhase: string | null;
  /** Coder dashboard URL for the focused workspace (new tab). */
  coderUiUrl: string | null;
  setSelectedRepoId: (repoId: string) => void;
  setRuntimeMeta: (meta: {
    activeBranch?: string | null;
    coderWorkspace?: string | null;
    coderPhase?: string | null;
    coderUiUrl?: string | null;
  }) => void;
  clearRuntimeMeta: () => void;
}

export const useCodeStore = create<CodeState>()(
  persist(
    (set, get) => ({
      selectedRepoId: '',
      activeBranch: null,
      coderWorkspace: null,
      coderPhase: null,
      coderUiUrl: null,
      setSelectedRepoId: (repoId) => set({ selectedRepoId: repoId }),
      setRuntimeMeta: (meta) =>
        set({
          activeBranch:
            meta.activeBranch !== undefined ? meta.activeBranch : get().activeBranch,
          coderWorkspace:
            meta.coderWorkspace !== undefined
              ? meta.coderWorkspace
              : get().coderWorkspace,
          coderPhase:
            meta.coderPhase !== undefined ? meta.coderPhase : get().coderPhase,
          coderUiUrl:
            meta.coderUiUrl !== undefined ? meta.coderUiUrl : get().coderUiUrl,
        }),
      clearRuntimeMeta: () =>
        set({
          activeBranch: null,
          coderWorkspace: null,
          coderPhase: null,
          coderUiUrl: null,
        }),
    }),
    {
      name: 'nexus:code:selected-repo',
      partialize: (s) => ({ selectedRepoId: s.selectedRepoId }),
    },
  ),
);

/** Ensure a repository is selected (defaulting to the first available) even
 * when the section panel (selector) is not mounted. Returns the current selection. */
export function useEnsureSelectedRepo(workspaceId: string): string {
  const { selectedRepoId, setSelectedRepoId } = useCodeStore();
  useEffect(() => {
    if (!workspaceId || selectedRepoId) return;
    void (async () => {
      try {
        // Seed from the team-shared default repo for this Nexus workspace.
        const res = await authFetch(
          `/api/coding-environments/default-repo?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok) return;
        const data = (await res.json()) as { repo_id?: string };
        if (data?.repo_id) setSelectedRepoId(data.repo_id);
      } catch {
        // ignore: pages fall back to the server default repo
      }
    })();
  }, [workspaceId, selectedRepoId, setSelectedRepoId]);
  return selectedRepoId;
}
