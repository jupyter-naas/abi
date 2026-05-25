'use client';

import { create } from 'zustand';
import { useWorkspaceStore } from './workspace';
import { authFetch } from './auth';

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

/** My Drive folder used by the Code IDE (matches backend `my_drive_code_root`). */
export const CODE_MY_DRIVE_FOLDER = 'code';
const CODE_FILES_SCOPE = 'my_drive' as const;
const codeScopeQuery = () => `scope=${CODE_FILES_SCOPE}`;

/** Resolve a new file/folder name to a path under the Code sandbox. */
export function resolveCodePath(name: string, selectedPath?: string | null): string {
  const { codeRoot, codeFiles, codeFolderContents } = useFilesStore.getState();
  const base = codeRoot || CODE_MY_DRIVE_FOLDER;

  if (name.startsWith('naas_abi/my-drive/')) return name;
  if (codeRoot && name.startsWith(`${codeRoot}/`)) return name;
  if (name.startsWith(`${CODE_MY_DRIVE_FOLDER}/`)) return name;

  if (selectedPath) {
    const allFiles = [
      ...codeFiles,
      ...Object.values(codeFolderContents).flat(),
    ];
    const item = allFiles.find((f) => f.path === selectedPath);
    if (item?.type === 'folder') return `${selectedPath}/${name}`;
    const parent = selectedPath.substring(0, selectedPath.lastIndexOf('/'));
    return parent ? `${parent}/${name}` : `${base}/${name}`;
  }

  return `${base}/${name}`;
}

// Storage source types - only Local (synced folders) and Cloud
export type StorageCategory = 'local' | 'cloud';

export interface StorageSource {
  id: string;
  name: string;
  icon: string;
  category: StorageCategory;
  enabled: boolean;
  connected: boolean;
  description?: string;
}

// Default storage sources
export const defaultStorageSources: StorageSource[] = [
  // Local - default workspace storage on server
  { id: 'my-drive', name: 'My Drive', icon: 'hard-drive', category: 'local', enabled: true, connected: true, description: 'Personal files shared across workspaces' },
  { id: 'workspace', name: 'Workspace Drive', icon: 'hard-drive', category: 'local', enabled: true, connected: true, description: 'Workspace files (create, edit, upload)' },
  { id: 'platform-drive', name: 'Platform Drive', icon: 'hard-drive', category: 'local', enabled: true, connected: true, description: 'Files shared across every workspace where platform drive is enabled' },
  { id: 'system-drive', name: 'System Drive', icon: 'server', category: 'local', enabled: true, connected: true, description: 'Full object storage tree (workspace admins only)' },
  
  // Cloud sources - third-party cloud storage
  { id: 'google-drive', name: 'Google Drive', icon: 'cloud', category: 'cloud', enabled: false, connected: false, description: 'Sync with Google Drive' },
  { id: 'icloud', name: 'iCloud Drive', icon: 'cloud', category: 'cloud', enabled: false, connected: false, description: 'Sync with iCloud' },
  { id: 'dropbox', name: 'Dropbox', icon: 'cloud', category: 'cloud', enabled: false, connected: false, description: 'Sync with Dropbox' },
  { id: 'onedrive', name: 'OneDrive', icon: 'cloud', category: 'cloud', enabled: false, connected: false, description: 'Sync with Microsoft OneDrive' },
  { id: 's3', name: 'AWS S3', icon: 'database', category: 'cloud', enabled: false, connected: false, description: 'Amazon S3 bucket' },
  { id: 'r2', name: 'Cloudflare R2', icon: 'database', category: 'cloud', enabled: false, connected: false, description: 'Cloudflare R2 storage' },
  { id: 'minio', name: 'MinIO', icon: 'server', category: 'cloud', enabled: false, connected: false, description: 'Self-hosted S3-compatible' },
];

// Synced folder interface - local folders synced via File System Access API
export interface SyncedFolder {
  id: string;
  name: string;
  localPath: string;  // Display path on user's machine
  handle?: FileSystemDirectoryHandle; // Native file system handle
  syncEnabled: boolean;
  lastSynced?: string;
}

export interface FileInfo {
  name: string;
  path: string;
  type: 'file' | 'folder';
  size?: number;
  modified?: string;
  content_type?: string;
  source?: string; // Storage source ID
}

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
  
  // Lab state (VS Code-like, always at workspace root)
  labFiles: FileInfo[];
  labLoading: boolean;
  labFolderContents: Record<string, FileInfo[]>;  // Cached folder contents for tree expansion
  
  // Editor state (shared between Lab and Files)
  openFiles: string[];
  activeFile: string | null;
  fileContents: Record<string, string>;  // path -> content
  unsavedChanges: Record<string, boolean>;  // path -> hasUnsavedChanges

  // Code section (My Drive `code/` via /api/files)
  codeFiles: FileInfo[];
  codeFolderContents: Record<string, FileInfo[]>;
  codeLoading: boolean;
  codeOpenFiles: string[];
  codeActiveFile: string | null;
  codeFileContents: Record<string, string>;
  codeUnsavedChanges: Record<string, boolean>;
  /** Full object-storage path to the user's `code/` root, e.g. naas_abi/my-drive/{userId}/code */
  codeRoot: string;
  codeDiffs: Record<string, { additions: number; deletions: number; status: string }>;
  codeTreeVersion: number;
  
  // Storage sources
  storageSources: StorageSource[];
  expandedCategories: StorageCategory[];
  activeSource: string;
  
  // Synced folders
  syncedFolders: SyncedFolder[];

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
  openFile: (path: string) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string | null) => void;
  setFileContent: (path: string, content: string) => void;
  
  // Storage source actions
  toggleCategory: (category: StorageCategory) => void;
  toggleSource: (sourceId: string) => void;
  setActiveSource: (sourceId: string) => void;
  connectSource: (sourceId: string) => Promise<void>;
  disconnectSource: (sourceId: string) => void;
  
  // Synced folder actions
  addSyncedFolder: (folder: Omit<SyncedFolder, 'id'>) => void;
  removeSyncedFolder: (id: string) => void;
  toggleSyncFolder: (id: string) => void;
  syncLocalFolder: () => Promise<SyncedFolder | null>;  // Opens native folder picker
  fetchLocalFiles: (folderId: string, subPath?: string) => Promise<void>;  // Reads files from synced folder
  
  // API actions
  fetchFiles: (path?: string) => Promise<void>;
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

  // Code actions (My Drive `code/` folder)
  fetchCodeFiles: (path?: string) => Promise<void>;
  fetchCodeFolderContents: (folderPath: string) => Promise<FileInfo[]>;
  refreshCodeFiles: () => Promise<void>;
  openCodeFile: (path: string) => void;
  closeCodeFile: (path: string) => void;
  setCodeActiveFile: (path: string | null) => void;
  setCodeFileContent: (path: string, content: string) => void;
  readCodeFile: (path: string) => Promise<string | null>;
  saveCodeFile: (path: string) => Promise<boolean>;
  createCodeFile: (path: string, content?: string) => Promise<string | null>;
  createCodeFolder: (path: string) => Promise<boolean>;
  deleteCodeFile: (path: string) => Promise<boolean>;
  renameCodeFile: (oldPath: string, newPath: string) => Promise<boolean>;
  setCodeDiffs: (diffs: Array<{ file: string; additions: number; deletions: number; status: string }>) => void;
  clearCodeDiffs: () => void;
  syncCodeWorkdir: (direction?: 'pull' | 'push' | 'both') => Promise<void>;
}

import { getApiUrl } from '@/lib/config';

const getApiBase = () => getApiUrl();

const getFilesScope = (activeSource: string): 'workspace' | 'my_drive' | 'platform_drive' | 'system_drive' => {
  if (activeSource === 'my-drive') return 'my_drive';
  if (activeSource === 'platform-drive') return 'platform_drive';
  if (activeSource === 'system-drive') return 'system_drive';
  return 'workspace';
};

export const useFilesStore = create<FilesState>((set, get) => ({
  // Files page state (Finder-like)
  files: [],
  currentPath: '',
  loading: false,
  error: null,
  
  // Lab state (VS Code-like, always workspace root)
  labFiles: [],
  labLoading: false,
  labFolderContents: {},  // Cached folder contents for tree expansion
  
  // Editor state
  openFiles: [],
  activeFile: null,
  fileContents: {},
  unsavedChanges: {},

  // Code section state
  codeFiles: [],
  codeFolderContents: {},
  codeLoading: false,
  codeOpenFiles: [],
  codeActiveFile: null,
  codeFileContents: {},
  codeUnsavedChanges: {},
  codeRoot: '',
  codeDiffs: {},
  codeTreeVersion: 0,
  
  // Storage sources
  storageSources: defaultStorageSources,
  expandedCategories: ['local'] as StorageCategory[],
  activeSource: 'workspace',  // Default to workspace (server storage)
  
  // Synced folders
  syncedFolders: [] as SyncedFolder[],

  uploadProgress: null,

  setFiles: (files) => set({ files }),
  setCurrentPath: (currentPath) => set({ currentPath }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  
  // Storage source actions
  toggleCategory: (category) => set((state) => ({
    expandedCategories: state.expandedCategories.includes(category)
      ? state.expandedCategories.filter((c) => c !== category)
      : [...state.expandedCategories, category],
  })),
  
  toggleSource: (sourceId) => set((state) => ({
    storageSources: state.storageSources.map((s) =>
      s.id === sourceId ? { ...s, enabled: !s.enabled } : s
    ),
  })),
  
  setActiveSource: (sourceId) => set({ activeSource: sourceId }),
  
  connectSource: async (sourceId) => {
    // TODO: Implement OAuth or API key connection flow for cloud sources
    set((state) => ({
      storageSources: state.storageSources.map((s) =>
        s.id === sourceId ? { ...s, connected: true, enabled: true } : s
      ),
    }));
  },
  
  disconnectSource: (sourceId) => set((state) => ({
    storageSources: state.storageSources.map((s) =>
      s.id === sourceId ? { ...s, connected: false, enabled: false } : s
    ),
  })),
  
  // Synced folder actions
  addSyncedFolder: (folder) => set((state) => {
    const newId = `synced-${Date.now()}`;
    return {
      syncedFolders: [
        ...state.syncedFolders,
        { ...folder, id: newId },
      ],
      // Auto-select if it's the first synced folder
      activeSource: state.activeSource === '' ? newId : state.activeSource,
    };
  }),
  
  removeSyncedFolder: (id) => set((state) => ({
    syncedFolders: state.syncedFolders.filter((f) => f.id !== id),
    // Clear activeSource if we're removing the active one
    activeSource: state.activeSource === id 
      ? (state.syncedFolders.find((f) => f.id !== id)?.id || '')
      : state.activeSource,
  })),
  
  toggleSyncFolder: (id) => set((state) => ({
    syncedFolders: state.syncedFolders.map((f) =>
      f.id === id ? { ...f, syncEnabled: !f.syncEnabled } : f
    ),
  })),
  
  // Open native folder picker and sync a local folder
  syncLocalFolder: async () => {
    try {
      // Check if File System Access API is supported
      if (!('showDirectoryPicker' in window)) {
        set({ error: 'Your browser does not support folder selection. Please use Chrome, Edge, or another Chromium-based browser.' });
        return null;
      }
      
      // Open native folder picker
      const handle = await (window as Window & { showDirectoryPicker: () => Promise<FileSystemDirectoryHandle> }).showDirectoryPicker();
      
      const newId = `synced-${Date.now()}`;
      const newFolder: SyncedFolder = {
        id: newId,
        name: handle.name,
        localPath: handle.name, // We can only get the folder name, not the full path for security
        handle,
        syncEnabled: true,
        lastSynced: new Date().toISOString(),
      };
      
      set((state) => ({
        syncedFolders: [...state.syncedFolders, newFolder],
        activeSource: newId,
      }));
      
      // Fetch files from the newly synced folder
      await get().fetchLocalFiles(newId);
      
      return newFolder;
    } catch (err) {
      // User cancelled the picker or browser doesn't support it
      const errorName = (err as Error).name;
      if (errorName !== 'AbortError' && errorName !== 'SecurityError') {
        console.error('Error syncing folder:', err);
        set({ error: 'Failed to sync folder. Make sure your browser supports the File System Access API.' });
      }
      // Clear any previous error on cancellation
      if (errorName === 'AbortError') {
        set({ error: null });
      }
      return null;
    }
  },
  
  // Fetch files from a synced local folder using File System Access API
  fetchLocalFiles: async (folderId, subPath = '') => {
    const { syncedFolders } = get();
    const folder = syncedFolders.find((f) => f.id === folderId);
    
    if (!folder?.handle) {
      set({ error: 'Folder handle not available. Please re-sync the folder.' });
      return;
    }
    
    set({ loading: true, error: null });
    
    try {
      const files: FileInfo[] = [];
      let targetHandle: FileSystemDirectoryHandle = folder.handle;
      
      // Navigate to subpath if provided
      if (subPath) {
        const parts = subPath.split('/').filter(Boolean);
        for (const part of parts) {
          targetHandle = await targetHandle.getDirectoryHandle(part);
        }
      }
      
      // Read directory contents
      for await (const entry of (targetHandle as any).values()) {
        const fileInfo: FileInfo = {
          name: entry.name,
          path: subPath ? `${subPath}/${entry.name}` : entry.name,
          type: entry.kind === 'directory' ? 'folder' : 'file',
          source: folderId,
        };
        
        // Get file size and modified date for files
        if (entry.kind === 'file') {
          try {
            const file = await entry.getFile();
            fileInfo.size = file.size;
            fileInfo.modified = file.lastModified ? new Date(file.lastModified).toISOString() : undefined;
            fileInfo.content_type = file.type || undefined;
          } catch {
            // Ignore errors getting file metadata
          }
        }
        
        files.push(fileInfo);
      }
      
      // Sort: folders first, then by name
      files.sort((a, b) => {
        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      
      set({ files, currentPath: subPath, loading: false });
    } catch (err) {
      console.error('Error reading local folder:', err);
      set({ 
        error: 'Failed to read folder contents. You may need to re-grant access.',
        loading: false,
        files: [],
      });
    }
  },
  
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

  fetchFiles: async (path = '') => {
    // Files page should reflect the object storage tree as-is.
    // Do not force a workspace prefix here.
    const relativePath = path.replace(/^\/+|\/+$/g, '');
    const workspaceId = getCurrentWorkspaceId();
    const scope = getFilesScope(get().activeSource);

    // The files API requires a workspace for workspace/platform-drive scopes.
    // During app bootstrap the workspace can still be null.
    if (scope !== 'my_drive' && !relativePath && !workspaceId) {
      set({ files: [], currentPath: '', loading: false, error: null });
      return;
    }
    
    set({ loading: true, error: null });
    try {
      const fetchListing = async (targetPath: string) => {
        const workspaceParam = scope !== 'my_drive' && workspaceId
          ? `&workspace_id=${encodeURIComponent(workspaceId)}`
          : '';
        const scopeParam = `&scope=${scope}`;
        const response = await authFetch(
          `${getApiBase()}/api/files/?path=${encodeURIComponent(targetPath)}${workspaceParam}${scopeParam}`
        );
        if (!response.ok) {
          throw new Error('Failed to fetch files');
        }
        const data = await response.json();
        return Array.isArray(data.files) ? (data.files as FileInfo[]) : [];
      };

      let resolvedPath = relativePath;
      let resolvedFiles = await fetchListing(relativePath);

      // Fallback: if root appears empty, try workspace root.
      // This handles deployments where objects are scoped under workspace IDs.
      if (scope === 'workspace' && !relativePath && resolvedFiles.length === 0 && workspaceId) {
        const workspaceFiles = await fetchListing(workspaceId);
        if (workspaceFiles.length > 0) {
          resolvedPath = workspaceId;
          resolvedFiles = workspaceFiles;
        }
      }

      set({ files: resolvedFiles, currentPath: resolvedPath, loading: false });
    } catch (error) {
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
    const scope = getFilesScope(get().activeSource);

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
    const scope = getFilesScope(get().activeSource);

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
    const scope = getFilesScope(get().activeSource);
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
    const scope = getFilesScope(get().activeSource);
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
    const scope = getFilesScope(get().activeSource);

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
    const fileArray = Array.from(files as ArrayLike<File | { file: File; relativeDir?: string }>);

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
    const { currentPath } = get();
    await get().fetchFiles(currentPath);
  },

  refreshLabFiles: async () => {
    await get().fetchLabFiles();
  },

  readFile: async (path) => {
    const workspaceId = getCurrentWorkspaceId();
    const scope = getFilesScope(get().activeSource);
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
    const scope = getFilesScope(get().activeSource);
    
    if (content === undefined) {
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

  // ─── Code actions (My Drive via /api/files) ───────────────────────────────

  fetchCodeFiles: async (path = CODE_MY_DRIVE_FOLDER) => {
    set({ codeLoading: true });
    try {
      const response = await authFetch(
        `${getApiBase()}/api/files/?path=${encodeURIComponent(path)}&${codeScopeQuery()}`
      );
      if (!response.ok) throw new Error('Failed to fetch code files');
      const data = await response.json();
      const listedPath = (data.path as string) || path;
      set({
        codeFiles: data.files as FileInfo[],
        codeLoading: false,
        codeRoot: listedPath,
      });
    } catch (error) {
      console.error('Error fetching code files:', error);
      set({ codeLoading: false });
    }
  },

  fetchCodeFolderContents: async (folderPath: string) => {
    const cached = get().codeFolderContents[folderPath];
    if (cached) return cached;

    try {
      const response = await authFetch(
        `${getApiBase()}/api/files/?path=${encodeURIComponent(folderPath)}&${codeScopeQuery()}`
      );
      if (!response.ok) throw new Error('Failed to fetch folder');
      const data = await response.json();
      const files = data.files as FileInfo[];
      set((state) => ({
        codeFolderContents: { ...state.codeFolderContents, [folderPath]: files },
      }));
      return files;
    } catch (error) {
      console.error('Error fetching code folder:', error);
      return [];
    }
  },

  refreshCodeFiles: async () => {
    const codeRoot = get().codeRoot || CODE_MY_DRIVE_FOLDER;
    set((state) => ({ codeFolderContents: {}, codeTreeVersion: state.codeTreeVersion + 1 }));
    await get().fetchCodeFiles(codeRoot);
  },

  openCodeFile: (path) => {
    const { codeOpenFiles } = get();
    if (!codeOpenFiles.includes(path)) {
      set({ codeOpenFiles: [...codeOpenFiles, path], codeActiveFile: path });
      get().readCodeFile(path);
    } else {
      set({ codeActiveFile: path });
    }
  },

  closeCodeFile: (path) => {
    const { codeOpenFiles, codeActiveFile, codeFileContents, codeUnsavedChanges } = get();
    const newOpen = codeOpenFiles.filter((p) => p !== path);
    const newActive = codeActiveFile === path
      ? (newOpen.length > 0 ? newOpen[newOpen.length - 1] : null)
      : codeActiveFile;
    const newContents = { ...codeFileContents };
    delete newContents[path];
    const newUnsaved = { ...codeUnsavedChanges };
    delete newUnsaved[path];
    set({
      codeOpenFiles: newOpen,
      codeActiveFile: newActive,
      codeFileContents: newContents,
      codeUnsavedChanges: newUnsaved,
    });
  },

  setCodeActiveFile: (codeActiveFile) => set({ codeActiveFile }),

  setCodeFileContent: (path, content) => {
    const { codeFileContents, codeUnsavedChanges } = get();
    set({
      codeFileContents: { ...codeFileContents, [path]: content },
      codeUnsavedChanges: { ...codeUnsavedChanges, [path]: true },
    });
  },

  readCodeFile: async (path) => {
    try {
      const response = await authFetch(
        `${getApiBase()}/api/files/${encodeURIComponent(path)}?${codeScopeQuery()}`
      );
      if (!response.ok) throw new Error('Failed to read file');
      const data = await response.json();
      const content = data.content as string;
      set((state) => ({ codeFileContents: { ...state.codeFileContents, [path]: content } }));
      return content;
    } catch (error) {
      console.error('Error reading code file:', error);
      return null;
    }
  },

  saveCodeFile: async (path) => {
    const { codeFileContents, codeUnsavedChanges } = get();
    const content = codeFileContents[path];
    if (content === undefined) return false;
    try {
      const response = await authFetch(
        `${getApiBase()}/api/files/${encodeURIComponent(path)}?${codeScopeQuery()}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path,
            scope: CODE_FILES_SCOPE,
            content,
            content_type: 'text/plain',
          }),
        }
      );
      if (!response.ok) throw new Error('Failed to save file');
      set({ codeUnsavedChanges: { ...codeUnsavedChanges, [path]: false } });
      await get().syncCodeWorkdir('push');
      return true;
    } catch (error) {
      console.error('Error saving code file:', error);
      return false;
    }
  },

  createCodeFile: async (path, content = '') => {
    try {
      const response = await authFetch(`${getApiBase()}/api/files/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path,
          scope: CODE_FILES_SCOPE,
          content,
          content_type: 'text/plain',
        }),
      });
      if (!response.ok) throw new Error('Failed to create file');
      const created = (await response.json()) as FileInfo;
      const resolvedPath = created.path || path;
      void get().refreshCodeFiles();
      void get().syncCodeWorkdir('push');
      return resolvedPath;
    } catch (error) {
      console.error('Error creating code file:', error);
      return null;
    }
  },

  createCodeFolder: async (path) => {
    try {
      const response = await authFetch(`${getApiBase()}/api/files/folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, scope: CODE_FILES_SCOPE }),
      });
      if (!response.ok) throw new Error('Failed to create folder');
      await get().refreshCodeFiles();
      await get().syncCodeWorkdir('push');
      return true;
    } catch (error) {
      console.error('Error creating code folder:', error);
      return false;
    }
  },

  deleteCodeFile: async (path) => {
    try {
      const response = await authFetch(
        `${getApiBase()}/api/files/${encodeURIComponent(path)}?${codeScopeQuery()}`,
        { method: 'DELETE' }
      );
      if (!response.ok) throw new Error('Failed to delete');
      const { codeOpenFiles } = get();
      if (codeOpenFiles.includes(path)) get().closeCodeFile(path);
      await get().refreshCodeFiles();
      await get().syncCodeWorkdir('push');
      return true;
    } catch (error) {
      console.error('Error deleting code path:', error);
      return false;
    }
  },

  renameCodeFile: async (oldPath, newPath) => {
    try {
      const response = await authFetch(`${getApiBase()}/api/files/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          old_path: oldPath,
          new_path: newPath,
          scope: CODE_FILES_SCOPE,
        }),
      });
      if (!response.ok) throw new Error('Failed to rename');
      const { codeOpenFiles, codeActiveFile, codeFileContents, codeUnsavedChanges } = get();
      if (codeOpenFiles.includes(oldPath)) {
        const newContents = { ...codeFileContents, [newPath]: codeFileContents[oldPath] };
        delete newContents[oldPath];
        const newUnsaved = { ...codeUnsavedChanges, [newPath]: codeUnsavedChanges[oldPath] };
        delete newUnsaved[oldPath];
        set({
          codeOpenFiles: codeOpenFiles.map((p) => (p === oldPath ? newPath : p)),
          codeActiveFile: codeActiveFile === oldPath ? newPath : codeActiveFile,
          codeFileContents: newContents,
          codeUnsavedChanges: newUnsaved,
        });
      }
      await get().refreshCodeFiles();
      await get().syncCodeWorkdir('push');
      return true;
    } catch (error) {
      console.error('Error renaming code path:', error);
      return false;
    }
  },

  setCodeDiffs: (diffs) => {
    set((state) => ({
      codeDiffs: {
        ...state.codeDiffs,
        ...Object.fromEntries(
          diffs.map((d) => [d.file, { additions: d.additions, deletions: d.deletions, status: d.status }])
        ),
      },
    }));
  },

  clearCodeDiffs: () => set({ codeDiffs: {} }),

  syncCodeWorkdir: async (direction = 'both') => {
    try {
      await authFetch(`${getApiBase()}/api/code/sync?direction=${direction}`, { method: 'POST' });
    } catch (error) {
      console.warn('Code workdir sync failed (non-fatal):', error);
    }
  },
}));
