'use client';

import { create } from 'zustand';
import type { SearchTopic } from '@/lib/search-topics';
import { topicsApi } from '@/lib/search-topics-api';

/** Topics of the current workspace, shared by the search page, its sidebar column and settings. */
interface SearchTopicsState {
  workspaceId: string | null;
  topics: SearchTopic[];
  canEdit: boolean;
  loading: boolean;
  error: string | null;
  load: (workspaceId: string, force?: boolean) => Promise<void>;
  replace: (topic: SearchTopic) => void;
  remove: (topicId: string) => void;
}

const byOrder = (a: SearchTopic, b: SearchTopic) => a.order - b.order || a.label.localeCompare(b.label);

export const useSearchTopicsStore = create<SearchTopicsState>((set, get) => ({
  workspaceId: null,
  topics: [],
  canEdit: false,
  loading: false,
  error: null,
  load: async (workspaceId, force = false) => {
    const state = get();
    if (!force && state.workspaceId === workspaceId && (state.loading || state.topics.length)) return;
    set({ workspaceId, loading: true, error: null, ...(state.workspaceId !== workspaceId ? { topics: [] } : {}) });
    try {
      const { topics, can_edit } = await topicsApi.list(workspaceId);
      if (get().workspaceId === workspaceId) set({ topics: [...topics].sort(byOrder), canEdit: can_edit, loading: false });
    } catch (error) {
      if (get().workspaceId === workspaceId) set({ loading: false, error: error instanceof Error ? error.message : 'Could not load search topics' });
    }
  },
  replace: (topic) => set(state => ({
    topics: [...state.topics.filter(t => t.id !== topic.id), topic].sort(byOrder),
  })),
  remove: (topicId) => set(state => ({ topics: state.topics.filter(t => t.id !== topicId) })),
}));
