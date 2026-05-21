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
  enabled: boolean;
}

interface AppsState {
  apps: AppItem[];
  loading: boolean;
  workspaceId: string | null;

  fetchApps: (workspaceId: string) => Promise<void>;
  toggleApp: (appId: string) => Promise<void>;
}

const apiBase = () => getApiUrl();

export const useAppsStore = create<AppsState>()((set, get) => ({
  apps: [],
  loading: false,
  workspaceId: null,

  fetchApps: async (workspaceId: string) => {
    set({ loading: true, workspaceId });
    try {
      const response = await authFetch(
        `${apiBase()}/api/apps/?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) {
        set({ loading: false });
        return;
      }
      const data = await response.json();
      const apps: AppItem[] = Array.isArray(data?.apps) ? data.apps : [];
      set({ apps, loading: false });
    } catch (error) {
      console.error('Failed to fetch apps:', error);
      set({ loading: false });
    }
  },

  toggleApp: async (appId: string) => {
    const { workspaceId, apps } = get();
    if (!workspaceId) return;
    const target = apps.find((a) => a.app_id === appId);
    if (!target) return;

    const newEnabled = !target.enabled;

    // Optimistic update
    set({
      apps: apps.map((a) =>
        a.app_id === appId ? { ...a, enabled: newEnabled } : a
      ),
    });

    try {
      const response = await authFetch(
        `${apiBase()}/api/apps/${encodeURIComponent(workspaceId)}/${encodeURIComponent(appId)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: newEnabled }),
        }
      );
      if (!response.ok) {
        // Rollback
        set({
          apps: get().apps.map((a) =>
            a.app_id === appId ? { ...a, enabled: !newEnabled } : a
          ),
        });
        console.error('Failed to toggle app');
      }
    } catch (error) {
      set({
        apps: get().apps.map((a) =>
          a.app_id === appId ? { ...a, enabled: !newEnabled } : a
        ),
      });
      console.error('Failed to toggle app:', error);
    }
  },
}));
