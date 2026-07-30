'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface SlidesProject {
  slug: string;
  title: string;
  branch: string;
  deck_path: string;
  template_id: string;
  updated_at?: string | null;
  commit_sha?: string | null;
}

export type SlidesEditorMode = 'preview' | 'code';

export type SlidesRuntimeStatus =
  | 'idle'
  | 'ensuring'
  | 'ready'
  | 'degraded'
  | 'error';

interface SlidesState {
  selectedSlug: string | null;
  selectedTitle: string | null;
  editorMode: SlidesEditorMode;
  runtimeStatus: SlidesRuntimeStatus;
  runtimeDetail: string | null;
  setSelectedSlug: (slug: string | null) => void;
  setSelectedTitle: (title: string | null) => void;
  setEditorMode: (mode: SlidesEditorMode) => void;
  setRuntimeStatus: (status: SlidesRuntimeStatus, detail?: string | null) => void;
}

export const useSlidesStore = create<SlidesState>()(
  persist(
    (set) => ({
      selectedSlug: null,
      selectedTitle: null,
      editorMode: 'preview',
      runtimeStatus: 'idle',
      runtimeDetail: null,
      setSelectedSlug: (slug) => set({ selectedSlug: slug }),
      setSelectedTitle: (title) => set({ selectedTitle: title }),
      setEditorMode: (mode) => set({ editorMode: mode }),
      setRuntimeStatus: (status, detail = null) =>
        set({ runtimeStatus: status, runtimeDetail: detail }),
    }),
    {
      name: 'nexus:slides:selected',
      partialize: (s) => ({
        selectedSlug: s.selectedSlug,
        selectedTitle: s.selectedTitle,
      }),
    },
  ),
);
