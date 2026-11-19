'use client';

import { useEffect, useMemo } from 'react';
import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import { useFilesStore } from '@/stores/files';
import { fileViewsPath, parseFileViews, type FileView } from '@/lib/file-views';
import {
  ALL_VIEWS,
  isFileViewSource,
  viewFolders,
  type FileViewSource,
} from '@/app/workspace/[workspaceId]/files/lib/drive-label';

type Fetcher = (url: string) => Promise<Response>;

export type FileViewsStatus = 'loading' | 'ready' | 'error';

export interface FileViewsState {
  /** The workspace the views were asked from (`''` for none). */
  workspaceId: string;
  status: FileViewsStatus;
  views: FileView[];
  pending: { workspaceId: string; promise: Promise<void> } | null;
  load: (workspaceId: string, options?: { force?: boolean }) => Promise<void>;
}

/**
 * The views of the file system the caller may open from a workspace
 * (`GET /api/files/views`), shared by the Files page and the sidebar: one request
 * per workspace at a time. A failed read keeps this workspace's last answer (the
 * files API decides each call anyway); with none, no view is listed.
 */
export function createFileViewsStore(fetcher: Fetcher = authFetch) {
  return create<FileViewsState>((set, get) => ({
    workspaceId: '',
    status: 'loading',
    views: [],
    pending: null,
    load: (workspaceId, options) => {
      const pending = get().pending;
      if (pending?.workspaceId === workspaceId) return pending.promise;
      const known = get().workspaceId === workspaceId ? get().views : [];
      if (!options?.force && get().workspaceId === workspaceId && get().status === 'ready') {
        return Promise.resolve();
      }
      set({ workspaceId, status: known.length ? 'ready' : 'loading', views: known });
      const call = { workspaceId, promise: Promise.resolve() };
      call.promise = (async () => {
        try {
          const response = await fetcher(fileViewsPath(workspaceId || null));
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const views = parseFileViews(await response.json());
          if (get().workspaceId === workspaceId) set({ status: 'ready', views });
        } catch {
          if (get().workspaceId === workspaceId) set({ status: 'error', views: get().views });
        } finally {
          if (get().pending === call) set({ pending: null });
        }
      })();
      set({ pending: call });
      return call.promise;
    },
  }));
}

export const useFileViewsStore = createFileViewsStore();

/** The views the caller may open from `workspaceId`, read when the workspace changes. */
export function useFileViews(workspaceId: string | null | undefined): {
  status: FileViewsStatus;
  views: FileView[];
} {
  const id = workspaceId ?? '';
  const known = useFileViewsStore((s) => s.workspaceId);
  const status = useFileViewsStore((s) => s.status);
  const views = useFileViewsStore((s) => s.views);
  const load = useFileViewsStore((s) => s.load);

  useEffect(() => {
    void load(id);
  }, [id, load]);

  if (known !== id) return { status: 'loading', views: [] };
  return { status, views };
}

/**
 * The views the Files page and sidebar offer from `workspaceId`, under the chosen
 * drive (`folders`: All Views' folders and the View dropdown's views). A view
 * open but not offered (another workspace's, a link's, a starred item's, the other
 * drive's) goes back to All Views once the views are known.
 */
export function useOfferedFileViews(workspaceId: string | null | undefined): {
  status: FileViewsStatus;
  views: FileView[];
  folders: { source: FileViewSource; label: string }[];
} {
  const { status, views } = useFileViews(workspaceId);
  const activeDrive = useFilesStore((s) => s.activeDrive);
  const activeSource = useFilesStore((s) => s.activeSource);
  const chooseView = useFilesStore((s) => s.chooseView);
  const folders = useMemo(() => viewFolders(views, activeDrive), [views, activeDrive]);

  useEffect(() => {
    if (status !== 'ready' || !isFileViewSource(activeSource)) return;
    if (folders.some((folder) => folder.source === activeSource)) return;
    chooseView(ALL_VIEWS);
  }, [activeSource, chooseView, folders, status]);

  return { status, views, folders };
}
