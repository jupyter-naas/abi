'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface SheetsProject {
  slug: string;
  title: string;
  branch: string;
  workbook_path: string;
  template_id: string;
  updated_at?: string | null;
  commit_sha?: string | null;
  archived?: boolean;
}

export type SheetsEditorMode = 'preview' | 'code';

export type SheetsSidebarView = 'sheets' | 'filmstrip';

export type SheetsFilmstripWorkbook = {
  workspaceId: string;
  slug: string;
  html: string;
  disabled: boolean;
};

export type SheetsRuntimeStatus =
  | 'idle'
  | 'ensuring'
  | 'ready'
  | 'degraded'
  | 'error';

/** Dispatched when Abi (or another client) writes the open workbook. */
export const SHEETS_DECK_UPDATED_EVENT = 'sheets-workbook-updated';

export type SheetsWorkbookUpdatedDetail = {
  slug?: string;
  source?: string;
};

export type SheetsWorkbookSource = 'sidecar' | 'forgejo' | null;

interface SheetsState {
  selectedSlug: string | null;
  selectedTitle: string | null;
  sidebarView: SheetsSidebarView;
  selectedIndex: number;
  /** Number of sheet tabs in the open workbook (0 when none is open). Sent to Abi with selectedIndex. */
  tabCount: number;
  filmstrip: SheetsFilmstripWorkbook | null;
  reorderOpenWorkbook: ((fromIndex: number, toIndex: number) => void) | null;
  editorMode: SheetsEditorMode;
  runtimeStatus: SheetsRuntimeStatus;
  runtimeDetail: string | null;
  forgejoBranch: string | null;
  coderWorkspace: string | null;
  coderPhase: string | null;
  /** Coder dashboard URL for the bound sheets workspace (new tab). */
  coderUiUrl: string | null;
  /** Local editor buffer differs from last Save. */
  workbookDirty: boolean;
  workbookRevision: string | null;
  setWorkbookRevision: (revision: string | null) => void;
  /** Where the last loaded preview came from (sidecar vs Forgejo snapshot). */
  workbookSource: SheetsWorkbookSource;
  /** Monotonic token; editor listens and reloads workbook from server. */
  refreshToken: number;
  /** True while Abi is running a sheets write/replace tool. */
  agentWriting: boolean;
  setSelectedSlug: (slug: string | null) => void;
  setSelectedTitle: (title: string | null) => void;
  setSidebarView: (view: SheetsSidebarView) => void;
  setSelectedIndex: (index: number) => void;
  setTabCount: (count: number) => void;
  setFilmstrip: (filmstrip: SheetsFilmstripWorkbook | null) => void;
  setReorderOpenWorkbook: (fn: ((fromIndex: number, toIndex: number) => void) | null) => void;
  setEditorMode: (mode: SheetsEditorMode) => void;
  setRuntimeStatus: (status: SheetsRuntimeStatus, detail?: string | null) => void;
  setRuntimeMeta: (meta: {
    forgejoBranch?: string | null;
    coderWorkspace?: string | null;
    coderPhase?: string | null;
    coderUiUrl?: string | null;
  }) => void;
  setWorkbookDirty: (dirty: boolean) => void;
  setWorkbookSource: (source: SheetsWorkbookSource) => void;
  requestWorkbookRefresh: (slug?: string | null) => void;
  setAgentWriting: (writing: boolean) => void;
}

export const useSheetsStore = create<SheetsState>()(
  persist(
    (set, get) => ({
      selectedSlug: null,
      selectedTitle: null,
      sidebarView: 'sheets',
      selectedIndex: 0,
      tabCount: 0,
      filmstrip: null,
      reorderOpenWorkbook: null,
      editorMode: 'preview',
      runtimeStatus: 'idle',
      runtimeDetail: null,
      forgejoBranch: null,
      coderWorkspace: null,
      coderPhase: null,
      coderUiUrl: null,
      workbookDirty: false,
      workbookRevision: null,
      setWorkbookRevision: (revision) => set({ workbookRevision: revision }),
      workbookSource: null,
      refreshToken: 0,
      agentWriting: false,
      setSelectedSlug: (slug) => set({ selectedSlug: slug, workbookRevision: slug === get().selectedSlug ? get().workbookRevision : null }),
      setSelectedTitle: (title) => set({ selectedTitle: title }),
      setSidebarView: (view) => set({ sidebarView: view }),
      setSelectedIndex: (index) => set({ selectedIndex: index }),
      setTabCount: (count) => set({ tabCount: count }),
      setFilmstrip: (filmstrip) => set({ filmstrip }),
      setReorderOpenWorkbook: (fn) => set({ reorderOpenWorkbook: fn }),
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
      setWorkbookDirty: (dirty) => set({ workbookDirty: dirty }),
      setWorkbookSource: (source) => set({ workbookSource: source }),
      requestWorkbookRefresh: (slug) => {
        const open = get().selectedSlug;
        if (slug && open && slug !== open) return;
        set({ refreshToken: get().refreshToken + 1 });
      },
      setAgentWriting: (writing) => set({ agentWriting: writing }),
    }),
    {
      name: 'nexus:sheets:selected',
      partialize: (s) => ({
        selectedSlug: s.selectedSlug,
        selectedTitle: s.selectedTitle,
        sidebarView: s.sidebarView,
      }),
    },
  ),
);

/**
 * Every backend tool in sheets_tools.py that persists a workbook change — must
 * stay in sync with that file's `@tool` defs. Missing one here means a real
 * edit (e.g. insert_slide) never triggers a Files/version refresh: the
 * chat-driven write succeeds, but the composer strip goes stale until the
 * user does something else that happens to match.
 */
export function isSheetsWriteTool(rawName: string | null | undefined): boolean {
  const raw = (rawName || '').toLowerCase();
  return (
    raw.includes('update_sheets_cells') ||
    raw.includes('write_sheets_workbook') ||
    raw.includes('create_sheets_project') ||
    raw.includes('evaluate_sheets_formulas') ||
    raw.includes('import_dataset_to_sheet')
  );
}

export function dispatchSheetsWorkbookUpdated(detail: SheetsWorkbookUpdatedDetail = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<SheetsWorkbookUpdatedDetail>(SHEETS_DECK_UPDATED_EVENT, { detail }),
  );
  useSheetsStore.getState().requestWorkbookRefresh(detail.slug ?? null);
}
