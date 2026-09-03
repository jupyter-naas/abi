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

/** Dispatched when Abi (or another client) writes the open deck. */
export const SLIDES_DECK_UPDATED_EVENT = 'slides-deck-updated';

export type SlidesDeckUpdatedDetail = {
  slug?: string;
  source?: string;
};

export type SlidesDeckSource = 'sidecar' | 'forgejo' | null;

interface SlidesState {
  selectedSlug: string | null;
  selectedTitle: string | null;
  editorMode: SlidesEditorMode;
  runtimeStatus: SlidesRuntimeStatus;
  runtimeDetail: string | null;
  forgejoBranch: string | null;
  coderWorkspace: string | null;
  coderPhase: string | null;
  /** Coder dashboard URL for the bound slides workspace (new tab). */
  coderUiUrl: string | null;
  /** Local editor buffer differs from last Save. */
  deckDirty: boolean;
  /** Where the last loaded preview came from (sidecar vs Forgejo snapshot). */
  deckSource: SlidesDeckSource;
  /** Monotonic token; editor listens and reloads deck from server. */
  refreshToken: number;
  /** True while Abi is running a slides write/replace tool. */
  agentWriting: boolean;
  setSelectedSlug: (slug: string | null) => void;
  setSelectedTitle: (title: string | null) => void;
  setEditorMode: (mode: SlidesEditorMode) => void;
  setRuntimeStatus: (status: SlidesRuntimeStatus, detail?: string | null) => void;
  setRuntimeMeta: (meta: {
    forgejoBranch?: string | null;
    coderWorkspace?: string | null;
    coderPhase?: string | null;
    coderUiUrl?: string | null;
  }) => void;
  setDeckDirty: (dirty: boolean) => void;
  setDeckSource: (source: SlidesDeckSource) => void;
  requestDeckRefresh: (slug?: string | null) => void;
  setAgentWriting: (writing: boolean) => void;
}

export const useSlidesStore = create<SlidesState>()(
  persist(
    (set, get) => ({
      selectedSlug: null,
      selectedTitle: null,
      editorMode: 'preview',
      runtimeStatus: 'idle',
      runtimeDetail: null,
      forgejoBranch: null,
      coderWorkspace: null,
      coderPhase: null,
      coderUiUrl: null,
      deckDirty: false,
      deckSource: null,
      refreshToken: 0,
      agentWriting: false,
      setSelectedSlug: (slug) => set({ selectedSlug: slug }),
      setSelectedTitle: (title) => set({ selectedTitle: title }),
      setEditorMode: (mode) => set({ editorMode: mode }),
      setRuntimeStatus: (status, detail = null) =>
        set({ runtimeStatus: status, runtimeDetail: detail }),
      setRuntimeMeta: (meta) =>
        set({
          forgejoBranch:
            meta.forgejoBranch !== undefined ? meta.forgejoBranch : get().forgejoBranch,
          coderWorkspace:
            meta.coderWorkspace !== undefined
              ? meta.coderWorkspace
              : get().coderWorkspace,
          coderPhase:
            meta.coderPhase !== undefined ? meta.coderPhase : get().coderPhase,
          coderUiUrl:
            meta.coderUiUrl !== undefined ? meta.coderUiUrl : get().coderUiUrl,
        }),
      setDeckDirty: (dirty) => set({ deckDirty: dirty }),
      setDeckSource: (source) => set({ deckSource: source }),
      requestDeckRefresh: (slug) => {
        const open = get().selectedSlug;
        if (slug && open && slug !== open) return;
        set({ refreshToken: get().refreshToken + 1 });
      },
      setAgentWriting: (writing) => set({ agentWriting: writing }),
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

export function isSlidesWriteTool(rawName: string | null | undefined): boolean {
  const raw = (rawName || '').toLowerCase();
  return (
    raw.includes('write_slides') ||
    raw.includes('replace_in_slides') ||
    raw.includes('save_slides_asset') ||
    raw.includes('rename_slides')
  );
}

export function dispatchSlidesDeckUpdated(detail: SlidesDeckUpdatedDetail = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<SlidesDeckUpdatedDetail>(SLIDES_DECK_UPDATED_EVENT, { detail }),
  );
  useSlidesStore.getState().requestDeckRefresh(detail.slug ?? null);
}
