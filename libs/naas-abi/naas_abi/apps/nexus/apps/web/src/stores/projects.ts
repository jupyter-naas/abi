import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';

export interface ProjectModule {
  module_path: string;
  name: string;
  description: string;
  logo_url: string | null;
  category: string;
  installed: boolean;
}

interface ProjectsState {
  projects: ProjectModule[];
  lastFetchedAt: number | null;
  fetchProjects: (workspaceId: string) => Promise<void>;
  getProject: (modulePath: string) => ProjectModule | undefined;
}

const CACHE_TTL_MS = 5 * 60 * 1000;

export const useProjectsStore = create<ProjectsState>()((set, get) => ({
  projects: [],
  lastFetchedAt: null,

  fetchProjects: async (workspaceId: string) => {
    const { lastFetchedAt } = get();
    if (lastFetchedAt && Date.now() - lastFetchedAt < CACHE_TTL_MS) return;

    try {
      const { authFetch } = await import('./auth');
      const API_BASE = getApiUrl();
      const response = await authFetch(`${API_BASE}/api/modules/?workspace_id=${encodeURIComponent(workspaceId)}`);
      if (!response.ok) return;
      const data = await response.json();
      const installed: ProjectModule[] = (data.installed ?? []).map((m: ProjectModule) => ({
        module_path: m.module_path,
        name: m.name,
        description: m.description || '',
        logo_url: m.logo_url ?? null,
        category: m.category,
        installed: true,
      }));
      set({ projects: installed, lastFetchedAt: Date.now() });
    } catch {
      // silently fail
    }
  },

  getProject: (modulePath) => get().projects.find((p) => p.module_path === modulePath),
}));
