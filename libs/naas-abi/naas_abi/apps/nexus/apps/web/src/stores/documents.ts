'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface DocumentsProject {
  slug: string;
  title: string;
  branch: string;
  document_path: string;
  template_id: string;
  updated_at?: string | null;
  commit_sha?: string | null;
  archived?: boolean;
}

export type DocumentsEditorMode = 'preview' | 'code';

export type DocumentsSidebarView = 'documents' | 'outline';

export type DocumentsOutlineDocument = {
  workspaceId: string;
  slug: string;
  html: string;
  disabled: boolean;
};

export type DocumentsRuntimeStatus =
  | 'idle'
  | 'ensuring'
  | 'ready'
  | 'degraded'
  | 'error';

/** Dispatched when Abi (or another client) writes the open document. */
export const DOCUMENTS_UPDATED_EVENT = 'sections-document-updated';

export type DocumentsUpdatedDetail = {
  slug?: string;
  source?: string;
  title?: string;
};

export type DocumentsSource = 'sidecar' | 'forgejo' | null;

interface SectionsState {
  selectedSlug: string | null;
  selectedTitle: string | null;
  sidebarView: DocumentsSidebarView;
  selectedIndex: number;
  /** Number of sections in the open document (0 when none is open). Sent to Abi with selectedIndex. */
  sectionCount: number;
  outline: DocumentsOutlineDocument | null;
  reorderOpenDocument: ((fromIndex: number, toIndex: number) => void) | null;
  editorMode: DocumentsEditorMode;
  runtimeStatus: DocumentsRuntimeStatus;
  runtimeDetail: string | null;
  forgejoBranch: string | null;
  coderWorkspace: string | null;
  coderPhase: string | null;
  /** Coder dashboard URL for the bound sections workspace (new tab). */
  coderUiUrl: string | null;
  /** Local editor buffer differs from last Save. */
  documentDirty: boolean;
  /** Where the last loaded preview came from (sidecar vs Forgejo snapshot). */
  documentSource: DocumentsSource;
  /** Monotonic token; editor listens and reloads document from server. */
  refreshToken: number;
  /** True while Abi is running a sections write/replace tool. */
  agentWriting: boolean;
  setSelectedSlug: (slug: string | null) => void;
  setSelectedTitle: (title: string | null) => void;
  setSidebarView: (view: DocumentsSidebarView) => void;
  setSelectedIndex: (index: number) => void;
  setSectionCount: (count: number) => void;
  setOutline: (outline: DocumentsOutlineDocument | null) => void;
  setReorderOpenDocument: (fn: ((fromIndex: number, toIndex: number) => void) | null) => void;
  setEditorMode: (mode: DocumentsEditorMode) => void;
  setRuntimeStatus: (status: DocumentsRuntimeStatus, detail?: string | null) => void;
  setRuntimeMeta: (meta: {
    forgejoBranch?: string | null;
    coderWorkspace?: string | null;
    coderPhase?: string | null;
    coderUiUrl?: string | null;
  }) => void;
  setDocumentDirty: (dirty: boolean) => void;
  setDocumentSource: (source: DocumentsSource) => void;
  requestDocumentRefresh: (slug?: string | null) => void;
  setAgentWriting: (writing: boolean) => void;
}

export const useDocumentsStore = create<SectionsState>()(
  persist(
    (set, get) => ({
      selectedSlug: null,
      selectedTitle: null,
      sidebarView: 'documents',
      selectedIndex: 0,
      sectionCount: 0,
      outline: null,
      reorderOpenDocument: null,
      editorMode: 'preview',
      runtimeStatus: 'idle',
      runtimeDetail: null,
      forgejoBranch: null,
      coderWorkspace: null,
      coderPhase: null,
      coderUiUrl: null,
      documentDirty: false,
      documentSource: null,
      refreshToken: 0,
      agentWriting: false,
      setSelectedSlug: (slug) => set({ selectedSlug: slug }),
      setSelectedTitle: (title) => set({ selectedTitle: title }),
      setSidebarView: (view) => set({ sidebarView: view }),
      setSelectedIndex: (index) => set({ selectedIndex: index }),
      setSectionCount: (count) => set({ sectionCount: count }),
      setOutline: (outline) => set({ outline }),
      setReorderOpenDocument: (fn) => set({ reorderOpenDocument: fn }),
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
      setDocumentDirty: (dirty) => set({ documentDirty: dirty }),
      setDocumentSource: (source) => set({ documentSource: source }),
      requestDocumentRefresh: (slug) => {
        const open = get().selectedSlug;
        if (slug && open && slug !== open) return;
        set({ refreshToken: get().refreshToken + 1 });
      },
      setAgentWriting: (writing) => set({ agentWriting: writing }),
    }),
    {
      name: 'nexus:documents:selected',
      partialize: (s) => ({
        selectedSlug: s.selectedSlug,
        selectedTitle: s.selectedTitle,
        sidebarView: s.sidebarView,
      }),
    },
  ),
);

/**
 * Every backend tool in documents_tools.py that persists a document change — must
 * stay in sync with that file's `@tool` defs. Missing one here means a real
 * edit (e.g. insert_section) never triggers a Files/version refresh: the
 * chat-driven write succeeds, but the composer strip goes stale until the
 * user does something else that happens to match.
 */
export function isDocumentsWriteTool(rawName: string | null | undefined): boolean {
  const raw = (rawName || '').toLowerCase();
  return (
    raw.includes('write_document') ||
    raw.includes('replace_in_document') ||
    raw.includes('insert_section') ||
    raw.includes('delete_section') ||
    raw.includes('duplicate_section') ||
    raw.includes('reorder_sections') ||
    raw.includes('apply_document_commands') ||
    raw.includes('insert_page_break') ||
    raw.includes('insert_heading') ||
    raw.includes('insert_paragraph') ||
    raw.includes('apply_paragraph_style') ||
    raw.includes('create_documents_project') ||
    raw.includes('fill_document_slots') ||
    raw.includes('rename_document') ||
    raw.includes('update_title')
  );
}

export function dispatchDocumentUpdated(detail: DocumentsUpdatedDetail = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<DocumentsUpdatedDetail>(DOCUMENTS_UPDATED_EVENT, { detail }),
  );
  useDocumentsStore.getState().requestDocumentRefresh(detail.slug ?? null);
}
