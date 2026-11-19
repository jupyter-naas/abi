'use client';

import { create } from 'zustand';
import { useWorkspaceStore } from './workspace';
import { authFetch, useAuthStore } from './auth';
import { isSystemPath } from '@/lib/system-files';

// Helper to get current workspace ID
const getWorkspaceIdFromPathname = (): string | null => {
  if (typeof window === 'undefined') return null;

  const match = window.location.pathname.match(/\/workspace\/([^/]+)/);
  if (!match?.[1]) return null;

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
};

const getCurrentWorkspaceId = (): string | null => {
  return useWorkspaceStore.getState().currentWorkspaceId ?? getWorkspaceIdFromPathname();
};

export interface FileInfo {
  name: string;
  path: string;
  type: 'file' | 'folder';
  size?: number;
  modified?: string;
  content_type?: string;
  source?: string; // The view it was listed in
}

export interface StarredItem {
  path: string;
  name: string;
  type: 'file' | 'folder';
  /** The view it is in (`my-files`, `workspace-files`…). */
  source: FileViewSource;
  workspaceId: string;
}

export interface StarredNavigation {
  source: string;
  path: string;
  previewPath?: string; // for files: open preview after navigating to parent folder
}

const STARRED_STORAGE_KEY = 'nexus-starred-files';

/**
 * Starred items as stored: an item kept with an old drive source (`my-drive`,
 * `workspace`…) opens the view it became; one of a synced local folder (gone) or
 * unreadable is dropped.
 */
export function starredItemsFrom(stored: unknown): StarredItem[] {
  if (!Array.isArray(stored)) return [];
  return stored.flatMap((raw): StarredItem[] => {
    if (!raw || typeof raw !== 'object') return [];
    const item = raw as Partial<StarredItem> & { source?: unknown };
    const source = filesSourceFrom(typeof item.source === 'string' ? item.source : null);
    if (!source || !isFileViewSource(source)) return [];
    if (typeof item.path !== 'string' || typeof item.workspaceId !== 'string') return [];
    return [
      {
        path: item.path,
        name: typeof item.name === 'string' ? item.name : item.path.split('/').pop() || item.path,
        type: item.type === 'folder' ? 'folder' : 'file',
        source,
        workspaceId: item.workspaceId,
      },
    ];
  });
}

const getInitialStarredItems = (): StarredItem[] => {
  if (typeof window === 'undefined') return [];
  try {
    const stored = localStorage.getItem(STARRED_STORAGE_KEY);
    return stored ? starredItemsFrom(JSON.parse(stored)) : [];
  } catch {
    return [];
  }
};

const saveStarredItems = (items: StarredItem[]): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STARRED_STORAGE_KEY, JSON.stringify(items));
  } catch {
    // ignore storage errors
  }
};

// Sort preference for the Files page — persisted so it survives paging,
// navigation and reloads.
export type FileSortKey = 'name' | 'size' | 'modified';
export type SortDirection = 'asc' | 'desc';

const SORT_STORAGE_KEY = 'nexus-files-sort';

const getInitialSort = (): { sortBy: FileSortKey; sortDir: SortDirection } => {
  const fallback = { sortBy: 'name' as FileSortKey, sortDir: 'asc' as SortDirection };
  if (typeof window === 'undefined') return fallback;
  try {
    const stored = localStorage.getItem(SORT_STORAGE_KEY);
    if (!stored) return fallback;
    const parsed = JSON.parse(stored) as { sortBy?: FileSortKey; sortDir?: SortDirection };
    return {
      sortBy: parsed.sortBy === 'size' || parsed.sortBy === 'modified' ? parsed.sortBy : 'name',
      sortDir: parsed.sortDir === 'desc' ? 'desc' : 'asc',
    };
  } catch {
    return fallback;
  }
};

const saveSort = (sortBy: FileSortKey, sortDir: SortDirection): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(SORT_STORAGE_KEY, JSON.stringify({ sortBy, sortDir }));
  } catch {
    // ignore storage errors
  }
};

// View → Show system files (names starting with "."). Off unless chosen.
const SHOW_SYSTEM_STORAGE_KEY = 'nexus-files-show-system';

const getInitialShowSystemFiles = (): boolean => {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(SHOW_SYSTEM_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
};

const saveShowSystemFiles = (show: boolean): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(SHOW_SYSTEM_STORAGE_KEY, String(show));
  } catch {
    // ignore storage errors
  }
};

export interface FileContent {
  path: string;
  content: string;
  content_type: string;
}

interface FilesState {
  // Files page state (Finder-like navigation)
  files: FileInfo[];
  currentPath: string;
  loading: boolean;
  error: string | null;

  // Server-side pagination + search for the Files page. `filesTotal` is the
  // number of matching entries in the current directory; `filesLimit`/`filesOffset`
  // remember the last page requested and `filesSearch` the last search term, so
  // refreshFiles() can reload the same slice after a mutation.
  filesTotal: number;
  filesLimit: number | null;
  filesOffset: number;
  filesSearch: string;
  // Persisted sort preference, applied server-side.
  filesSortBy: FileSortKey;
  filesSortDir: SortDirection;
  // Persisted: list system (dot) files. Applied server-side.
  showSystemFiles: boolean;
  
  // Lab state (VS Code-like, always at workspace root)
  labFiles: FileInfo[];
  labLoading: boolean;
  labFolderContents: Record<string, FileInfo[]>;  // Cached folder contents for tree expansion
  
  // Editor state (shared between Lab and Files)
  openFiles: string[];
  activeFile: string | null;
  fileContents: Record<string, string>;  // path -> content
  unsavedChanges: Record<string, boolean>;  // path -> hasUnsavedChanges
  
  // What the Files page and sidebar show: All Views (`all`, one folder per view
  // the caller may open) or a view. `viewChoice` is the View dropdown: under All
  // Views, opening a view's folder keeps it, so the breadcrumb leads back.
  activeSource: FilesSource;
  viewChoice: FilesSource;
  // The Drive dropdown: All Drives, or one drive (File System, today's only).
  activeDrive: FilesDrive;

  // Starred items (persisted in localStorage)
  starredItems: StarredItem[];

  // Pending starred navigation: set by sidebar, consumed by the files page
  starredNavigation: StarredNavigation | null;

  // Upload progress (for folder / multi-file uploads)
  uploadProgress: {
    active: boolean;
    total: number;
    completed: number;
    failed: number;
    currentName: string | null;
  } | null;

  // Actions
  setFiles: (files: FileInfo[]) => void;
  setCurrentPath: (path: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  // Toggle/select the sort column. Same column flips direction; a new column
  // starts ascending. Persists the choice; the caller refetches to apply it.
  setFilesSort: (sortBy: FileSortKey) => void;
  // Persists the choice; the caller refetches to apply it.
  setShowSystemFiles: (show: boolean) => void;
  openFile: (path: string) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string | null) => void;
  setFileContent: (path: string, content: string) => void;
  
  // Starred item actions
  starItem: (item: StarredItem) => void;
  unstarItem: (path: string, workspaceId: string) => void;
  setStarredNavigation: (nav: StarredNavigation | null) => void;

  // View actions
  /** Open a view (or All Views): a link, a starred item, a folder of All Views. Old drive sources are read as their view. */
  setActiveSource: (source: string) => void;
  /** The View dropdown: open this view (or All Views) and keep it chosen. */
  chooseView: (source: FilesSource) => void;
  /** The Drive dropdown. */
  chooseDrive: (drive: FilesDrive) => void;
  
  // API actions
  fetchFiles: (
    path?: string,
    options?: { limit?: number; offset?: number; search?: string; workspaceId?: string }
  ) => Promise<void>;
  fetchLabFiles: () => Promise<void>;  // Always fetches workspace root for Lab
  fetchLabFolderContents: (folderPath: string) => Promise<FileInfo[]>;  // Fetch subfolder contents for Lab tree
  createFile: (path: string, content?: string) => Promise<FileInfo | null>;
  createFolder: (path: string) => Promise<FileInfo | null>;
  deleteFile: (path: string) => Promise<boolean>;
  renameFile: (oldPath: string, newPath: string) => Promise<boolean>;
  uploadFile: (file: File, relativeDir?: string) => Promise<FileInfo | null>;
  uploadFiles: (files: FileList | File[] | { file: File; relativeDir?: string }[]) => Promise<FileInfo[]>;
  refreshFiles: () => Promise<void>;
  refreshLabFiles: () => Promise<void>;  // Refreshes Lab's file tree
  readFile: (path: string) => Promise<string | null>;
  saveFile: (path: string) => Promise<boolean>;
}

import { getApiUrl } from '@/lib/config';
import {
  ALL_VIEWS,
  filesScopeForSource,
  filesSourceFrom,
  isFileViewSource,
  type FileViewSource,
  type FilesDrive,
  type FilesSource,
} from '@/app/workspace/[workspaceId]/files/lib/drive-label';

/** Said when an action needs a view but All Views is open. */
const NO_VIEW_OPEN = 'Open a view (My Files, Workspace Files…) first';

const getApiBase = () => getApiUrl();


// Files page listing requests. Each fetch bumps the generation; only the
// latest one may commit files, errors or the loading flag. Switching view also
// invalidates (and aborts) the pending listing.
let filesRequestGen = 0;
let filesRequestAbort: AbortController | null = null;

const beginFilesRequest = (): { gen: number; signal: AbortSignal } => {
  filesRequestAbort?.abort();
  filesRequestAbort = new AbortController();
  filesRequestGen += 1;
  return { gen: filesRequestGen, signal: filesRequestAbort.signal };
};

export const invalidateFilesRequests = (): void => {
  filesRequestAbort?.abort();
  filesRequestAbort = null;
  filesRequestGen += 1;
};

export const useFilesStore = create<FilesState>((set, get) => ({
  // Files page state (Finder-like)
  files: [],
  currentPath: '',
  loading: false,
  error: null,

  filesTotal: 0,
  filesLimit: null,
  filesOffset: 0,
  filesSearch: '',
  filesSortBy: getInitialSort().sortBy,
  filesSortDir: getInitialSort().sortDir,
  showSystemFiles: getInitialShowSystemFiles(),

  // Lab state (VS Code-like, always workspace root)
  labFiles: [],
  labLoading: false,
  labFolderContents: {},  // Cached folder contents for tree expansion
  
  // Editor state
  openFiles: [],
  activeFile: null,
  fileContents: {},
  unsavedChanges: {},
  
  activeSource: ALL_VIEWS,
  viewChoice: ALL_VIEWS,
  activeDrive: 'all',

  starredItems: getInitialStarredItems(),
  starredNavigation: null,

  uploadProgress: null,

  starItem: (item) => set((state) => {
    if (state.starredItems.some((i) => i.path === item.path && i.workspaceId === item.workspaceId)) {
      return state;
    }
    const newItems = [...state.starredItems, item];
    saveStarredItems(newItems);
    return { starredItems: newItems };
  }),

  unstarItem: (path, workspaceId) => set((state) => {
    const newItems = state.starredItems.filter(
      (i) => !(i.path === path && i.workspaceId === workspaceId)
    );
    saveStarredItems(newItems);
    return { starredItems: newItems };
  }),

  setStarredNavigation: (nav) => set({ starredNavigation: nav }),

  setFiles: (files) => set({ files }),
  setCurrentPath: (currentPath) => set({ currentPath }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  setFilesSort: (sortBy) => set((state) => {
    // Same column flips direction; switching columns starts ascending.
    const sortDir: SortDirection =
      state.filesSortBy === sortBy && state.filesSortDir === 'asc' ? 'desc' : 'asc';
    saveSort(sortBy, sortDir);
    return { filesSortBy: sortBy, filesSortDir: sortDir };
  }),

  setShowSystemFiles: (show) => {
    saveShowSystemFiles(show);
    set({ showSystemFiles: show });
  },
  
  setActiveSource: (raw) => {
    const source = filesSourceFrom(raw);
    if (!source) return;
    const { activeSource, viewChoice } = get();
    if (source !== activeSource) invalidateFilesRequests();
    // Under All Views a view opens inside it; with one view chosen, another becomes the choice.
    const nextChoice = viewChoice === ALL_VIEWS || source === ALL_VIEWS ? ALL_VIEWS : source;
    set({ activeSource: source, viewChoice: nextChoice });
  },

  chooseView: (source) => {
    if (source !== get().activeSource) invalidateFilesRequests();
    set({ activeSource: source, viewChoice: source });
  },

  chooseDrive: (drive) => set({ activeDrive: drive }),

  openFile: (path) => {
    const { openFiles } = get();
    if (!openFiles.includes(path)) {
      set({ openFiles: [...openFiles, path], activeFile: path });
      // Read file content when opening
      get().readFile(path);
    } else {
      set({ activeFile: path });
    }
  },
  
  closeFile: (path) => {
    const { openFiles, activeFile, fileContents, unsavedChanges } = get();
    const newOpenFiles = openFiles.filter((p) => p !== path);
    const newActiveFile = activeFile === path 
      ? (newOpenFiles.length > 0 ? newOpenFiles[newOpenFiles.length - 1] : null)
      : activeFile;
    
    // Clean up file content from memory
    const newFileContents = { ...fileContents };
    delete newFileContents[path];
    const newUnsavedChanges = { ...unsavedChanges };
    delete newUnsavedChanges[path];
    
    set({ 
      openFiles: newOpenFiles, 
      activeFile: newActiveFile,
      fileContents: newFileContents,
      unsavedChanges: newUnsavedChanges,
    });
  },
  
  setActiveFile: (activeFile) => set({ activeFile }),
  
  setFileContent: (path, content) => {
    const { fileContents, unsavedChanges } = get();
    set({ 
      fileContents: { ...fileContents, [path]: content },
      unsavedChanges: { ...unsavedChanges, [path]: true },
    });
  },

  fetchFiles: async (path = '', options) => {
    // Files page should reflect the object storage tree as-is.
    // Do not force a workspace prefix here.
    const relativePath = path.replace(/^\/+|\/+$/g, '');
    const workspaceId = options?.workspaceId ?? getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);

    // Pagination: when a limit is provided the server only lists that slice,
    // which is what keeps large folders (200+ files) from stalling the API.
    const limit = options?.limit ?? null;
    const offset = options?.offset ?? 0;
    // Search: filtered on the server (current folder only) so paging walks the
    // matches, not just whatever happened to load on the current page.
    const search = (options?.search ?? '').trim();
    const { gen, signal } = beginFilesRequest();
    const isCurrent = () => gen === filesRequestGen;

    // All Views is the views' folders, which the page draws: nothing is listed.
    // My Files is the person's own: in a view nothing of it is asked for or shown.
    if (!scope || (scope === 'my_drive' && useAuthStore.getState().view)) {
      set({
        files: [],
        currentPath: scope ? relativePath : '',
        filesTotal: 0,
        filesLimit: limit,
        filesOffset: offset,
        filesSearch: search,
        loading: false,
        error: null,
      });
      return;
    }

    // The files API requires a workspace for Workspace Files and Organization Files.
    // During app bootstrap the workspace can still be null.
    if (scope !== 'my_drive' && !relativePath && !workspaceId) {
      set({
        files: [],
        currentPath: '',
        filesTotal: 0,
        filesLimit: limit,
        filesOffset: offset,
        filesSearch: search,
        loading: false,
        error: null,
      });
      return;
    }

    // Sort is a persisted preference, so read it from state — every fetch (page,
    // search, refresh) stays consistently ordered.
    const { filesSortBy, filesSortDir, showSystemFiles } = get();

    set({ loading: true, error: null });
    try {
      const pageParams = limit != null ? `&limit=${limit}&offset=${offset}` : '';
      const searchParam = search ? `&search=${encodeURIComponent(search)}` : '';
      const sortParams = `&sort_by=${filesSortBy}&sort_dir=${filesSortDir}`;
      const hiddenParam = `&include_hidden=${showSystemFiles}`;
      const fetchListing = async (targetPath: string) => {
        const workspaceParam = scope !== 'my_drive' && workspaceId
          ? `&workspace_id=${encodeURIComponent(workspaceId)}`
          : '';
        const scopeParam = `&scope=${scope}`;
        const response = await authFetch(
          `${getApiBase()}/api/files/?path=${encodeURIComponent(targetPath)}${workspaceParam}${scopeParam}${pageParams}${searchParam}${sortParams}${hiddenParam}`,
          { signal }
        );
        if (!response.ok) {
          throw new Error('Failed to fetch files');
        }
        const data = await response.json();
        const listed = Array.isArray(data.files) ? (data.files as FileInfo[]) : [];
        const total = typeof data.total === 'number' ? data.total : listed.length;
        return { files: listed, total };
      };

      let resolvedPath = relativePath;
      let { files: resolvedFiles, total: resolvedTotal } = await fetchListing(relativePath);

      // Fallback: if the root has no entries at all, try the workspace root.
      // This handles deployments where objects are scoped under workspace IDs.
      // Keyed on total (not the page length) so an empty later page doesn't retry.
      if (!isCurrent()) return;
      if (scope === 'workspace' && !relativePath && resolvedTotal === 0 && workspaceId) {
        const workspaceListing = await fetchListing(workspaceId);
        if (workspaceListing.total > 0) {
          resolvedPath = workspaceId;
          resolvedFiles = workspaceListing.files;
          resolvedTotal = workspaceListing.total;
        }
      }

      if (!isCurrent()) return;
      set({
        files: resolvedFiles,
        currentPath: resolvedPath,
        filesTotal: resolvedTotal,
        filesLimit: limit,
        filesOffset: offset,
        filesSearch: search,
        loading: false,
      });
    } catch (error) {
      // Aborted or superseded: the newer request owns error/loading.
      if (!isCurrent()) return;
      set({ error: (error as Error).message, loading: false });
    }
  },

  // Fetch files for Lab - always at workspace root (independent of Files navigation)
  fetchLabFiles: async () => {
    const workspaceId = getCurrentWorkspaceId();
    if (!workspaceId) {
      set({ labLoading: false });
      return;
    }
    
    set({ labLoading: true });
    try {
      const response = await authFetch(
        `${getApiBase()}/api/files/?path=${encodeURIComponent(workspaceId)}&workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch lab files');
      }
      const data = await response.json();
      set({ labFiles: data.files, labLoading: false, labFolderContents: {} });
    } catch (error) {
      console.error('Error fetching lab files:', error);
      set({ labLoading: false });
    }
  },

  // Fetch contents of a specific folder for Lab tree expansion
  fetchLabFolderContents: async (folderPath: string) => {
    const workspaceId = getCurrentWorkspaceId();
    if (!workspaceId) {
      return [];
    }
    
    // Check cache first
    const cached = get().labFolderContents[folderPath];
    if (cached) {
      return cached;
    }
    
    try {
      // folderPath is relative to workspace, like "new-folder"
      const fullPath = `${workspaceId}/${folderPath}`;
      const response = await authFetch(
        `${getApiBase()}/api/files/?path=${encodeURIComponent(fullPath)}&workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch folder contents');
      }
      const data = await response.json();
      const files = data.files as FileInfo[];
      
      // Cache the results
      set((state) => ({
        labFolderContents: {
          ...state.labFolderContents,
          [folderPath]: files
        }
      }));
      
      return files;
    } catch (error) {
      console.error('Error fetching folder contents:', error);
      return [];
    }
  },

  createFile: async (path, content = '') => {
    const workspacePath = path.replace(/^\/+|\/+$/g, '');
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);

    if (!scope) {

      set({ error: NO_VIEW_OPEN, loading: false });

      return null;

    }

    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected', loading: false });
      return null;
    }
    
    set({ loading: true, error: null });
    try {
      const response = await authFetch(`${getApiBase()}/api/files/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: workspacePath,
          workspace_id: workspaceId,
          scope,
          content,
          content_type: 'text/plain',
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create file');
      }
      const file = await response.json();
      
      // Refresh files list
      await get().refreshFiles();
      
      set({ loading: false });
      return file;
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
      return null;
    }
  },

  createFolder: async (path) => {
    const workspacePath = path.replace(/^\/+|\/+$/g, '');
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);

    if (!scope) {

      set({ error: NO_VIEW_OPEN, loading: false });

      return null;

    }

    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected', loading: false });
      return null;
    }
    
    set({ loading: true, error: null });
    try {
      const response = await authFetch(`${getApiBase()}/api/files/folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: workspacePath, workspace_id: workspaceId, scope }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create folder');
      }
      const folder = await response.json();
      
      // Refresh files list
      await get().refreshFiles();
      
      set({ loading: false });
      return folder;
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
      return null;
    }
  },

  deleteFile: async (path) => {
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);
    if (!scope) {
      set({ error: NO_VIEW_OPEN, loading: false });
      return false;
    }
    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected', loading: false });
      return false;
    }

    set({ loading: true, error: null });
    try {
      const workspaceParam = scope !== 'my_drive' && workspaceId
        ? `workspace_id=${encodeURIComponent(workspaceId)}&`
        : '';
      const scopeParam = `scope=${scope}`;
      const response = await authFetch(`${getApiBase()}/api/files/${encodeURIComponent(path)}?${workspaceParam}${scopeParam}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete file');
      }
      
      // Refresh files list
      await get().refreshFiles();
      
      // Close file if open
      const { openFiles } = get();
      if (openFiles.includes(path)) {
        get().closeFile(path);
      }
      
      set({ loading: false });
      return true;
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
      return false;
    }
  },

  renameFile: async (oldPath, newPath) => {
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);
    if (!scope) {
      set({ error: NO_VIEW_OPEN, loading: false });
      return false;
    }
    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected', loading: false });
      return false;
    }

    set({ loading: true, error: null });
    try {
      const response = await authFetch(`${getApiBase()}/api/files/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_path: oldPath, new_path: newPath, workspace_id: workspaceId, scope }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to rename file');
      }
      
      // Update open files if renamed file was open
      const { openFiles, activeFile, fileContents, unsavedChanges } = get();
      if (openFiles.includes(oldPath)) {
        const newOpenFiles = openFiles.map(p => p === oldPath ? newPath : p);
        const newActiveFile = activeFile === oldPath ? newPath : activeFile;
        const newFileContents = { ...fileContents };
        if (newFileContents[oldPath]) {
          newFileContents[newPath] = newFileContents[oldPath];
          delete newFileContents[oldPath];
        }
        const newUnsavedChanges = { ...unsavedChanges };
        if (newUnsavedChanges[oldPath] !== undefined) {
          newUnsavedChanges[newPath] = newUnsavedChanges[oldPath];
          delete newUnsavedChanges[oldPath];
        }
        set({
          openFiles: newOpenFiles,
          activeFile: newActiveFile,
          fileContents: newFileContents,
          unsavedChanges: newUnsavedChanges,
        });
      }
      
      // Refresh files list
      await get().refreshFiles();
      
      set({ loading: false });
      return true;
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
      return false;
    }
  },

  uploadFile: async (file, relativeDir) => {
    const { currentPath } = get();
    const cleanRelative = (relativeDir || '').replace(/^\/+|\/+$/g, '');
    const uploadPath = [currentPath, cleanRelative].filter(Boolean).join('/');
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);

    if (!scope) {

      set({ error: NO_VIEW_OPEN, loading: false });

      return null;

    }

    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected', loading: false });
      return null;
    }

    set({ loading: true, error: null });
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('path', uploadPath);
      if (scope !== 'my_drive' && workspaceId) {
        formData.append('workspace_id', workspaceId);
      }
      formData.append('scope', scope);

      const response = await authFetch(`${getApiBase()}/api/files/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to upload file');
      }

      const uploadedFile = await response.json();
      
      // Refresh files list
      await get().refreshFiles();
      
      set({ loading: false });
      return uploadedFile;
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
      return null;
    }
  },

  uploadFiles: async (files) => {
    const results: FileInfo[] = [];
    // System files are read-only (the API refuses them): a dropped folder's
    // .DS_Store or .git is skipped rather than counted as a failed upload.
    const fileArray = Array.from(files as ArrayLike<File | { file: File; relativeDir?: string }>).filter(
      (item) => {
        const file = item instanceof File ? item : item.file;
        const relativeDir = item instanceof File ? '' : item.relativeDir ?? '';
        return !isSystemPath(relativeDir ? `${relativeDir}/${file.name}` : file.name);
      },
    );

    set({
      uploadProgress: {
        active: true,
        total: fileArray.length,
        completed: 0,
        failed: 0,
        currentName: null,
      },
    });

    try {
      for (const item of fileArray) {
        const file = item instanceof File ? item : item.file;
        const relativeDir = item instanceof File ? undefined : item.relativeDir;
        const displayName = relativeDir ? `${relativeDir}/${file.name}` : file.name;

        set((state) => ({
          uploadProgress: state.uploadProgress
            ? { ...state.uploadProgress, currentName: displayName }
            : state.uploadProgress,
        }));

        const result = await get().uploadFile(file, relativeDir);
        if (result) {
          results.push(result);
          set((state) => ({
            uploadProgress: state.uploadProgress
              ? { ...state.uploadProgress, completed: state.uploadProgress.completed + 1 }
              : state.uploadProgress,
          }));
        } else {
          set((state) => ({
            uploadProgress: state.uploadProgress
              ? { ...state.uploadProgress, failed: state.uploadProgress.failed + 1 }
              : state.uploadProgress,
          }));
        }
      }
    } finally {
      set((state) => ({
        uploadProgress: state.uploadProgress
          ? { ...state.uploadProgress, active: false, currentName: null }
          : state.uploadProgress,
      }));
      // Auto-clear after a short delay so the user sees the final state
      setTimeout(() => {
        set((state) => {
          if (state.uploadProgress && !state.uploadProgress.active) {
            return { uploadProgress: null };
          }
          return state;
        });
      }, 4000);
    }

    return results;
  },

  refreshFiles: async () => {
    const { currentPath, filesLimit, filesOffset, filesSearch } = get();
    await get().fetchFiles(
      currentPath,
      filesLimit != null
        ? { limit: filesLimit, offset: filesOffset, search: filesSearch }
        : { search: filesSearch }
    );
  },

  refreshLabFiles: async () => {
    await get().fetchLabFiles();
  },

  readFile: async (path) => {
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);
    if (!scope) {
      set({ error: NO_VIEW_OPEN });
      return null;
    }
    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected' });
      return null;
    }

    try {
      const workspaceParam = scope !== 'my_drive' && workspaceId
        ? `workspace_id=${encodeURIComponent(workspaceId)}&`
        : '';
      const scopeParam = `scope=${scope}`;
      const response = await authFetch(`${getApiBase()}/api/files/${encodeURIComponent(path)}?${workspaceParam}${scopeParam}`);
      if (!response.ok) {
        throw new Error('Failed to read file');
      }
      const data = await response.json();
      const { fileContents } = get();
      set({ 
        fileContents: { ...fileContents, [path]: data.content },
      });
      return data.content;
    } catch (error) {
      set({ error: (error as Error).message });
      return null;
    }
  },

  saveFile: async (path) => {
    const { fileContents, unsavedChanges } = get();
    const content = fileContents[path];
    const workspaceId = getCurrentWorkspaceId();
    const scope = filesScopeForSource(get().activeSource);
    
    if (content === undefined) {
      return false;
    }

    if (!scope) {

      set({ error: NO_VIEW_OPEN });

      return false;

    }

    if (scope !== 'my_drive' && !workspaceId) {
      set({ error: 'No workspace selected' });
      return false;
    }
    
    try {
      const workspaceParam = scope !== 'my_drive' && workspaceId
        ? `workspace_id=${encodeURIComponent(workspaceId)}&`
        : '';
      const scopeParam = `scope=${scope}`;
      const response = await authFetch(`${getApiBase()}/api/files/${encodeURIComponent(path)}?${workspaceParam}${scopeParam}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path,
          workspace_id: workspaceId,
          scope,
          content,
          content_type: 'text/plain',
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to save file');
      }
      
      // Mark as saved
      set({ 
        unsavedChanges: { ...unsavedChanges, [path]: false },
      });
      
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },
}));
