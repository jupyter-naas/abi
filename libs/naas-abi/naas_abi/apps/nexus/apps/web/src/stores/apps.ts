import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

export interface AppItem {
  module_path: string;
  module_name?: string;
  app_name: string;
  app_id: string;
  category: string;
  name: string;
  description: string;
  url?: string | null;
  avatar_url?: string | null;
  icon_emoji?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  version?: string | null;
  author?: string | null;
  license?: string | null;
  keywords?: string[];
  tier?: string | null;
  maintainer?: string | null;
  installed: boolean;
}

interface AppsState {
  apps: AppItem[];
  loading: boolean;
  workspaceId: string | null;

  fetchApps: (workspaceId: string) => Promise<void>;
}

const apiBase = () => getApiUrl();

export const useAppsStore = create<AppsState>()((set, get) => ({
  apps: [],
  loading: false,
  workspaceId: null,

  fetchApps: async (workspaceId: string) => {
    const switched = get().workspaceId !== workspaceId;
    set({ loading: true, workspaceId, ...(switched ? { apps: [] } : {}) });
    try {
      const response = await authFetch(
        `${apiBase()}/api/apps/?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (get().workspaceId !== workspaceId) return;
      if (!response.ok) {
        set({ apps: [], loading: false });
        return;
      }
      const data = await response.json();
      const apps: AppItem[] = Array.isArray(data?.apps) ? data.apps : [];
      if (get().workspaceId !== workspaceId) return;
      set({ apps, loading: false });
    } catch (error) {
      console.error('Failed to fetch apps:', error);
      if (get().workspaceId !== workspaceId) return;
      set({ apps: [], loading: false });
    }
  },
}));
