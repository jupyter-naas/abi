import { useEffect } from 'react';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authFetch } from '@/stores/auth';

/** Shared selection for the Code sub-app: which repository the Workspaces /
 * Branches / Pull-requests views operate on. Persisted so it survives reloads
 * and is shared between the section panel (selector) and the pages. */
interface CodeState {
  selectedRepoId: string;
  setSelectedRepoId: (repoId: string) => void;
}

export const useCodeStore = create<CodeState>()(
  persist(
    (set) => ({
      selectedRepoId: '',
      setSelectedRepoId: (repoId) => set({ selectedRepoId: repoId }),
    }),
    { name: 'nexus:code:selected-repo' },
  ),
);

/** Ensure a repository is selected (defaulting to the first available) even
 * when the section panel — which hosts the selector — isn't mounted. Returns
 * the current selection. */
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
        // ignore — pages fall back to the server default repo
      }
    })();
  }, [workspaceId, selectedRepoId, setSelectedRepoId]);
  return selectedRepoId;
}
