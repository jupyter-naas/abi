'use client';

import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { iconTargetKey, type IconTarget } from '@/lib/ontology-icon-library';

type IconRecord = IconTarget & { icon: string };
type IconsState = {
  workspaceId: string | null;
  icons: Record<string, string>;
  canEdit: boolean;
  loading: boolean;
  error: string | null;
  loadedAt: number;
  load: (workspaceId: string, force?: boolean) => Promise<void>;
  save: (workspaceId: string, target: IconTarget, icon: string | null) => Promise<void>;
};
let generation = 0;
let writeRevision = 0;
let workspaceEpoch = 0;
export const useOntologyIconsStore = create<IconsState>((set, get) => ({
  workspaceId: null, icons: {}, canEdit: false, loading: false, error: null, loadedAt: 0,
  load: async (workspaceId, force = false) => {
    const previous = get();
    if (previous.workspaceId === workspaceId && (previous.loading || (!force && previous.loadedAt))) return;
    const request = ++generation;
    const revision = writeRevision;
    if (previous.workspaceId !== workspaceId) workspaceEpoch++;
    set({ workspaceId, loading: true, error: null, ...(previous.workspaceId !== workspaceId ? { icons: {}, canEdit: false, loadedAt: 0 } : {}) });
    try {
      const response = await authFetch(`${getApiUrl()}/api/ontology/icons?${new URLSearchParams({ workspace_id: workspaceId })}`, { signal: AbortSignal.timeout(20000) });
      if (!response.ok) throw new Error('Could not load the workspace icons.');
      const data: { items?: IconRecord[]; can_edit?: boolean } = await response.json();
      if (!Array.isArray(data.items)) throw new Error('The workspace icons could not be read.');
      const icons: Record<string, string> = {};
      for (const item of data.items) if (typeof item.kind === 'string' && typeof item.resource_id === 'string' && /^material-symbols-light:[a-z0-9-]+$/.test(item.icon)) icons[iconTargetKey(item)] = item.icon;
      if (request === generation) set({ ...(revision === writeRevision ? { icons } : {}), canEdit: data.can_edit === true, loading: false, loadedAt: Date.now() });
    } catch (error) {
      if (request === generation) set({ loading: false, error: error instanceof Error ? error.message : 'Could not load the workspace icons.' });
    }
  },
  save: async (workspaceId, target, icon) => {
    const epoch = workspaceEpoch;
    writeRevision++; // An in-flight list must not replace a more recent edit.
    const response = await authFetch(`${getApiUrl()}/api/ontology/icons?${new URLSearchParams({ workspace_id: workspaceId })}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(20000),
      body: JSON.stringify({ ...target, icon }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save the icon. Please try again.');
    }
    writeRevision++;
    if (epoch === workspaceEpoch && get().workspaceId === workspaceId) set(state => {
      const icons = { ...state.icons }; const key = iconTargetKey(target);
      if (icon) icons[key] = icon; else delete icons[key];
      return { icons, loading: false, error: null, loadedAt: Date.now() };
    });
  },
}));
