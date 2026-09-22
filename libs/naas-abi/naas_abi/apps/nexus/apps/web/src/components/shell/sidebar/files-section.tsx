'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ChevronRight,
  File,
  Files,
  Folder,
  HardDrive,
  RefreshCw,
  Search,
  Server,
  Settings,
  Star,
  X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useFilesStore, type FileInfo, type SyncedFolder } from '@/stores/files';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { getApiUrl } from '@/lib/config';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { CollapsibleSection } from './collapsible-section';
import { SidebarToolbarButton } from './sidebar-toolbar';
import { getWorkspacePath } from './utils';
import { filesBrowsePath } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import { driveRootForSource } from '@/app/workspace/[workspaceId]/files/lib/drive-label';
import { shellTokens } from '../tokens';
import {
  canDropOntoExplorerFolder,
  explorerDirKey,
  explorerDirsToOpen,
  explorerDriveMatchesQuery,
  explorerListQuery,
  explorerParentPath,
  explorerPathAfterMove,
  explorerPathEqualsOrUnder,
  isValidExplorerEntryName,
  matchesExplorerQuery,
  normalizeExplorerPath,
} from './files-explorer';
import { FilesExplorerTree } from './files-explorer-tree';
import { useOntologyTreeKeyboard } from '@/hooks/use-ontology-tree-keyboard';

const EXPLORER_ROW_TYPO = 'files-explorer-list-row';

async function listLocalSyncedFolders(
  folder: SyncedFolder,
  subPath: string,
): Promise<FileInfo[]> {
  if (!folder.handle) {
    throw new Error('Folder handle not available. Re-sync the folder.');
  }
  let targetHandle: FileSystemDirectoryHandle = folder.handle;
  const parts = normalizeExplorerPath(subPath).split('/').filter(Boolean);
  for (const part of parts) {
    targetHandle = await targetHandle.getDirectoryHandle(part);
  }
  const files: FileInfo[] = [];
  for await (const entry of (targetHandle as unknown as { values: () => AsyncIterableIterator<{ name: string; kind: string }> }).values()) {
    files.push({
      name: entry.name,
      path: subPath ? `${normalizeExplorerPath(subPath)}/${entry.name}` : entry.name,
      type: entry.kind === 'directory' ? 'folder' : 'file',
      source: folder.id,
    });
  }
  files.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  return files;
}

export function FilesSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const rowPadClass = isMobilePanel ? 'px-2 py-2.5 min-h-11' : 'px-2 py-1';
  const iconSize = isMobilePanel ? 14 : 12;
  const treeKeyboard = useOntologyTreeKeyboard();
  const { currentWorkspaceId } = useWorkspaceStore();
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const platformDriveEnabled = Boolean(currentWorkspace?.platformDriveEnabled);
  const systemDriveEnabled = Boolean(currentWorkspace?.systemDriveEnabled);
  const workspaceRole = currentWorkspace?.currentUserRole;
  const isWorkspaceAdmin = workspaceRole === 'owner' || workspaceRole === 'admin';
  const [starredExpanded, setStarredExpanded] = useState(true);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [folderCache, setFolderCache] = useState<Record<string, FileInfo[]>>({});
  const [loadingDirs, setLoadingDirs] = useState<Record<string, boolean>>({});
  const [dirErrors, setDirErrors] = useState<Record<string, string | null>>({});
  const [explorerQuery, setExplorerQuery] = useState('');
  const loadGeneration = useRef(0);
  const folderCacheRef = useRef(folderCache);
  folderCacheRef.current = folderCache;
  const {
    expandedCategories: fileExpandedCategories,
    toggleCategory: toggleFileCategory,
    activeSource,
    setActiveSource,
    syncedFolders,
    fetchFiles,
    fetchLocalFiles,
    refreshFiles,
    currentPath,
    loading,
    starredItems,
    unstarItem,
    setStarredNavigation,
    renameFile,
    deleteFile,
  } = useFilesStore();
  const { prompt, dialog: promptDialog } = usePrompt();
  const { confirm, dialog: confirmDialog } = useConfirm();
  const authUserId = useAuthStore((state) => state.user?.id);

  const workspaceStarredItems = starredItems.filter(
    (i) => i.workspaceId === currentWorkspaceId,
  );
  const filtering = explorerQuery.trim().length > 0;
  const visibleStarredItems = filtering
    ? workspaceStarredItems.filter((item) => matchesExplorerQuery(item.name, explorerQuery))
    : workspaceStarredItems;

  const clearExplorerQuery = useCallback(() => setExplorerQuery(''), []);

  /**
   * Map a storage path to the explorer cache key path.
   * Drive roots are listed under `''`, not the absolute root prefix.
   */
  const explorerLoadPath = useCallback(
    (source: string, path: string) => {
      const normalized = normalizeExplorerPath(path);
      if (!normalized) return '';
      if (['my-drive', 'workspace', 'platform-drive', 'system-drive'].includes(source)) {
        const root = driveRootForSource(source, currentWorkspaceId || '', authUserId);
        if (root && normalized === normalizeExplorerPath(root)) return '';
      }
      return normalized;
    },
    [authUserId, currentWorkspaceId],
  );

  const openFilesBrowser = useCallback(() => {
    const target = isMobilePanel
      ? filesBrowsePath(currentWorkspaceId)
      : getWorkspacePath(currentWorkspaceId, '/files');
    router.push(target);
  }, [currentWorkspaceId, isMobilePanel, router]);

  const loadDir = useCallback(
    async (source: string, path: string, options?: { force?: boolean }) => {
      const key = explorerDirKey(source, path);
      if (!options?.force && folderCacheRef.current[key] !== undefined) return;
      const generation = loadGeneration.current;
      setLoadingDirs((prev) => ({ ...prev, [key]: true }));
      setDirErrors((prev) => ({ ...prev, [key]: null }));
      try {
        const synced = syncedFolders.find((folder) => folder.id === source);
        let files: FileInfo[];
        if (synced) {
          files = await listLocalSyncedFolders(synced, path);
        } else {
          const query = explorerListQuery(path, source, currentWorkspaceId);
          const response = await authFetch(`${getApiUrl()}/api/files/?${query}`);
          if (!response.ok) {
            throw new Error('Could not load directory');
          }
          const data = (await response.json()) as { files?: FileInfo[] };
          files = Array.isArray(data.files) ? data.files : [];
        }
        if (generation !== loadGeneration.current) return;
        setFolderCache((prev) => ({ ...prev, [key]: files }));
      } catch (error) {
        if (generation !== loadGeneration.current) return;
        setDirErrors((prev) => ({
          ...prev,
          [key]: error instanceof Error ? error.message : 'Could not load directory',
        }));
      } finally {
        if (generation === loadGeneration.current) {
          setLoadingDirs((prev) => ({ ...prev, [key]: false }));
        }
      }
    },
    [currentWorkspaceId, syncedFolders],
  );

  const ensureExpanded = useCallback((source: string, path: string) => {
    const key = explorerDirKey(source, path);
    setExpandedDirs((prev) => (prev.includes(key) ? prev : [...prev, key]));
  }, []);

  const toggleDir = useCallback(
    (source: string, path: string) => {
      const key = explorerDirKey(source, path);
      setExpandedDirs((prev) => {
        if (prev.includes(key)) {
          return prev.filter((value) => value !== key);
        }
        void loadDir(source, path);
        return [...prev, key];
      });
    },
    [loadDir],
  );

  const openFolder = useCallback(
    (source: string, path: string) => {
      setStarredNavigation({ source, path: normalizeExplorerPath(path) });
      openFilesBrowser();
    },
    [openFilesBrowser, setStarredNavigation],
  );

  const openFile = useCallback(
    (source: string, file: FileInfo) => {
      const filePath = normalizeExplorerPath(file.path);
      const parentPath = filePath.includes('/')
        ? filePath.slice(0, filePath.lastIndexOf('/'))
        : '';
      setStarredNavigation({
        source,
        path: parentPath,
        previewPath: filePath,
      });
      openFilesBrowser();
    },
    [openFilesBrowser, setStarredNavigation],
  );

  const purgeExplorerSubtree = useCallback((source: string, path: string) => {
    const normalized = normalizeExplorerPath(path);
    const prefix = `${source}::`;
    setFolderCache((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        if (!key.startsWith(prefix)) continue;
        const entryPath = key.slice(prefix.length);
        if (
          entryPath === normalized
          || (normalized !== '' && entryPath.startsWith(`${normalized}/`))
        ) {
          delete next[key];
        }
      }
      return next;
    });
    setExpandedDirs((prev) =>
      prev.filter((key) => {
        if (!key.startsWith(prefix)) return true;
        const entryPath = key.slice(prefix.length);
        if (entryPath === normalized) return false;
        if (normalized !== '' && entryPath.startsWith(`${normalized}/`)) return false;
        return true;
      }),
    );
    setDirErrors((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        if (!key.startsWith(prefix)) continue;
        const entryPath = key.slice(prefix.length);
        if (
          entryPath === normalized
          || (normalized !== '' && entryPath.startsWith(`${normalized}/`))
        ) {
          delete next[key];
        }
      }
      return next;
    });
  }, []);

  const navigateIfBrowsePathStale = useCallback(
    (source: string, affectedPath: string) => {
      if (activeSource !== source) return;
      if (!explorerPathEqualsOrUnder(currentPath, affectedPath)) return;
      setStarredNavigation({
        source,
        path: explorerParentPath(affectedPath),
      });
    },
    [activeSource, currentPath, setStarredNavigation],
  );

  const handleRenameFolder = useCallback(
    async (source: string, folder: FileInfo) => {
      const folderPath = normalizeExplorerPath(folder.path);
      // Drive roots are not rendered as tree rows; still guard empty paths.
      if (!folderPath) return;

      const newName = await prompt({
        title: 'Rename',
        description: `Rename "${folder.name}" to:`,
        defaultValue: folder.name,
        confirmLabel: 'Rename',
      });
      if (!newName || newName === folder.name) return;
      if (!isValidExplorerEntryName(newName)) {
        await confirm({
          title: 'Invalid name',
          description:
            'Name cannot be empty and cannot contain path separators (/ or \\).',
          confirmLabel: 'OK',
        });
        return;
      }

      const parentPath = explorerParentPath(folderPath);
      const newPath = parentPath ? `${parentPath}/${newName.trim()}` : newName.trim();
      if (source !== activeSource) {
        setActiveSource(source);
      }
      const ok = await renameFile(folderPath, newPath);
      if (!ok) return;

      purgeExplorerSubtree(source, folderPath);
      navigateIfBrowsePathStale(source, folderPath);
      void loadDir(source, explorerLoadPath(source, parentPath), { force: true });
    },
    [
      activeSource,
      confirm,
      explorerLoadPath,
      loadDir,
      navigateIfBrowsePathStale,
      prompt,
      purgeExplorerSubtree,
      renameFile,
      setActiveSource,
    ],
  );

  const handleDeleteFolder = useCallback(
    async (source: string, folder: FileInfo) => {
      const folderPath = normalizeExplorerPath(folder.path);
      if (!folderPath) return;

      const confirmed = await confirm({
        title: `Delete "${folder.name}"?`,
        description:
          folder.type === 'folder'
            ? 'This folder and all its contents will be permanently deleted.'
            : 'This file will be permanently deleted.',
        confirmLabel: 'Delete',
        destructive: true,
      });
      if (!confirmed) return;

      if (source !== activeSource) {
        setActiveSource(source);
      }
      const ok = await deleteFile(folderPath);
      if (!ok) return;

      const parentPath = explorerParentPath(folderPath);
      purgeExplorerSubtree(source, folderPath);
      navigateIfBrowsePathStale(source, folderPath);
      void loadDir(source, explorerLoadPath(source, parentPath), { force: true });
    },
    [
      activeSource,
      confirm,
      deleteFile,
      explorerLoadPath,
      loadDir,
      navigateIfBrowsePathStale,
      purgeExplorerSubtree,
      setActiveSource,
    ],
  );

  /** Move a canvas or explorer item onto a folder row (same drive only). */
  const handleMoveOntoFolder = useCallback(
    async (source: string, targetPath: string, draggedPath: string) => {
      // Local synced folders have no rename API path here.
      if (syncedFolders.some((folder) => folder.id === source)) return;
      // renameFile uses activeSource scope; reject cross-drive drops.
      if (source !== activeSource) return;

      const from = normalizeExplorerPath(draggedPath);
      const toFolder = normalizeExplorerPath(targetPath);
      if (!canDropOntoExplorerFolder(from, toFolder)) return;

      const name = from.includes('/') ? from.slice(from.lastIndexOf('/') + 1) : from;
      const newPath = toFolder ? `${toFolder}/${name}` : name;

      const ok = await renameFile(from, newPath);
      if (!ok) return;

      const oldParent = explorerParentPath(from);
      purgeExplorerSubtree(source, from);
      void loadDir(source, explorerLoadPath(source, oldParent), { force: true });
      void loadDir(source, explorerLoadPath(source, toFolder), { force: true });

      const rewritten = explorerPathAfterMove(currentPath, from, newPath);
      if (rewritten !== null) {
        setStarredNavigation({ source, path: rewritten });
      }
    },
    [
      activeSource,
      currentPath,
      explorerLoadPath,
      loadDir,
      purgeExplorerSubtree,
      renameFile,
      setStarredNavigation,
      syncedFolders,
    ],
  );

  const openRemoteDrive = async (sourceId: string) => {
    setActiveSource(sourceId);
    ensureExpanded(sourceId, '');
    void loadDir(sourceId, '', { force: true });
    await fetchFiles('', {
      limit: 50,
      offset: 0,
      search: '',
      workspaceId: currentWorkspaceId ?? undefined,
    });
    openFilesBrowser();
  };

  const openSyncedDrive = async (folderId: string) => {
    setActiveSource(folderId);
    ensureExpanded(folderId, '');
    void loadDir(folderId, '', { force: true });
    await fetchLocalFiles(folderId);
    openFilesBrowser();
  };

  const isRemoteDrive = ['my-drive', 'workspace', 'platform-drive', 'system-drive'].includes(
    activeSource,
  );
  const driveRoot = isRemoteDrive
    ? driveRootForSource(activeSource, currentWorkspaceId || '', authUserId)
    : '';

  // Keep the active drive expanded and open ancestor dirs so the current folder is visible.
  useEffect(() => {
    if (!activeSource) return;
    const dirsToOpen = isRemoteDrive
      ? explorerDirsToOpen(currentPath, driveRoot)
      : explorerDirsToOpen(currentPath, '');
    for (const dir of dirsToOpen) {
      ensureExpanded(activeSource, dir);
      void loadDir(activeSource, dir);
    }
  }, [activeSource, currentPath, driveRoot, ensureExpanded, isRemoteDrive, loadDir]);

  // Drop explorer cache when the workspace changes.
  useEffect(() => {
    loadGeneration.current += 1;
    setFolderCache({});
    setLoadingDirs({});
    setDirErrors({});
    setExpandedDirs([]);
    setExplorerQuery('');
  }, [currentWorkspaceId]);

  const handleRefresh = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    loadGeneration.current += 1;
    folderCacheRef.current = {};
    setFolderCache({});
    setDirErrors({});
    for (const key of expandedDirs) {
      const sep = key.indexOf('::');
      if (sep < 0) continue;
      const source = key.slice(0, sep);
      const path = key.slice(sep + 2);
      void loadDir(source, path, { force: true });
    }
    const activeSyncedFolder = syncedFolders.find((f) => f.id === activeSource);
    if (activeSyncedFolder) {
      fetchLocalFiles(activeSyncedFolder.id, currentPath);
    } else {
      refreshFiles();
    }
  };

  const handleOpenDriveSettings = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    router.push(getWorkspacePath(currentWorkspaceId, '/settings/drives'));
  };

  const driveExpanded = (sourceId: string) =>
    expandedDirs.includes(explorerDirKey(sourceId, ''));

  const renderDriveRow = (
    sourceId: string,
    label: string,
    icon: React.ReactNode,
    onOpen: () => void,
    title?: string,
  ) => {
    if (!explorerDriveMatchesQuery(label, sourceId, explorerQuery, folderCache)) {
      return null;
    }
    const labelMatch = matchesExplorerQuery(label, explorerQuery);
    const expanded =
      driveExpanded(sourceId)
      || (filtering && !labelMatch);
    const driveActive = activeSource === sourceId;
    const sourceRoot = ['my-drive', 'workspace', 'platform-drive', 'system-drive'].includes(sourceId)
      ? driveRootForSource(sourceId, currentWorkspaceId || '', authUserId)
      : '';
    const normalizedCurrent = normalizeExplorerPath(currentPath);
    const atRoot =
      driveActive
      && (normalizedCurrent === ''
        || (sourceRoot !== '' && normalizedCurrent === sourceRoot));
    // Drive-root rows are not real folders; only nested tree rows accept drops.
    const canDragFolders = !syncedFolders.some((folder) => folder.id === sourceId);
    return (
      <div key={sourceId} data-ontology-tree-row className="space-y-0.5">
        <div className="flex items-center">
          <button
            type="button"
            data-ontology-tree-toggle
            aria-expanded={expanded}
            aria-label={`${expanded ? 'Collapse' : 'Expand'} ${label}`}
            onClick={() => toggleDir(sourceId, '')}
            className="flex h-5 w-4 flex-shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
          >
            <ChevronRight
              size={11}
              className={cn('transition-transform', expanded && 'rotate-90')}
            />
          </button>
          <button
            type="button"
            title={title || label}
            aria-current={atRoot ? 'page' : undefined}
            data-ontology-tree-item={`drive:${sourceId}`}
            data-ontology-tree-select
            data-testid="files-explorer-drive"
            onClick={onOpen}
            className={cn(
              'flex min-w-0 flex-1 items-center gap-1 rounded-md transition-colors',
              rowPadClass,
              EXPLORER_ROW_TYPO,
              'hover:bg-workspace-accent-10',
              driveActive && 'bg-workspace-accent-15 text-workspace-accent',
            )}
          >
            {icon}
            <span className="flex-1 truncate text-left">{label}</span>
            {isMobilePanel && (
              <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />
            )}
          </button>
        </div>
        {expanded ? (
          <FilesExplorerTree
            source={sourceId}
            parentPath=""
            depth={1}
            folderCache={folderCache}
            loadingDirs={loadingDirs}
            dirErrors={dirErrors}
            expandedDirs={expandedDirs}
            activeSource={activeSource}
            currentPath={currentPath}
            query={explorerQuery}
            canDragFolders={canDragFolders}
            onToggleDir={toggleDir}
            onOpenFolder={openFolder}
            onOpenFile={openFile}
            onRenameFolder={handleRenameFolder}
            onDeleteFolder={handleDeleteFolder}
            onMoveOntoFolder={handleMoveOntoFolder}
            rowPadClass={rowPadClass}
            iconSize={iconSize}
          />
        ) : null}
      </div>
    );
  };

  const sectionActions = (
    <>
      <SidebarToolbarButton
        icon={<Settings size={14} />}
        label="Drive settings"
        onClick={handleOpenDriveSettings}
      />
      <SidebarToolbarButton
        icon={<RefreshCw size={14} />}
        label="Refresh"
        onClick={handleRefresh}
        disabled={loading}
        spinning={loading}
      />
    </>
  );

  return (
    <>
    {promptDialog}
    {confirmDialog}
    <CollapsibleSection
      id="files"
      icon={<Files size={18} />}
      label="Files"
      description="Workspace file storage"
      href={getWorkspacePath(currentWorkspaceId, '/files')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="mb-1 flex items-center justify-start gap-0.5">
        {sectionActions}
      </div>

      <h2 className="px-2 pb-1 pt-1 text-[13px] font-medium">Explorer</h2>
      <label className="relative mb-1.5 block px-0.5">
        <Search size={13} className="absolute left-2.5 top-2.5 text-muted-foreground" />
        <input
          type="search"
          aria-label="Search files explorer"
          placeholder="Search files…"
          value={explorerQuery}
          onChange={(event) => setExplorerQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              clearExplorerQuery();
            }
          }}
          className={cn(
            'w-full rounded-md border bg-background py-1.5 pl-7 pr-7 outline-none',
            'placeholder:text-muted-foreground focus-visible:border-workspace-accent',
            EXPLORER_ROW_TYPO,
          )}
        />
        {filtering ? (
          <button
            type="button"
            aria-label="Clear search"
            onClick={clearExplorerQuery}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground"
          >
            <X size={12} />
          </button>
        ) : null}
      </label>
      <nav
        {...treeKeyboard}
        aria-label="Files explorer"
        aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Home End Space"
        className="space-y-0.5"
        onKeyDown={(event) => {
          treeKeyboard.onKeyDown(event);
          // Space toggles folder/drive expand; ontology/KG keep Arrow-only expand.
          if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
            return;
          }
          if (event.key !== ' ') return;
          const target = event.target as HTMLElement;
          if (target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) {
            return;
          }
          const root = event.currentTarget;
          const row = target.closest('[data-ontology-tree-row]');
          if (!row || !root.contains(row)) return;
          // Stop page scroll and the focused button's default Space activation (open/navigate).
          event.preventDefault();
          event.stopPropagation();
          const toggle =
            row.matches('[data-ontology-tree-toggle]')
              ? (row as HTMLButtonElement)
              : Array.from(row.querySelectorAll<HTMLButtonElement>('[data-ontology-tree-toggle]')).find(
                  (button) => button.closest('[data-ontology-tree-row]') === row,
                );
          if (!toggle || toggle.disabled) return;
          const item =
            row.matches('[data-ontology-tree-item]')
              ? (row as HTMLButtonElement)
              : Array.from(row.querySelectorAll<HTMLButtonElement>('[data-ontology-tree-item]')).find(
                  (button) => button.closest('[data-ontology-tree-row]') === row,
                );
          item?.focus({ preventScroll: true });
          toggle.click();
        }}
      >
        <button
          type="button"
          onClick={() => toggleFileCategory('local')}
          className={cn(
            'flex w-full items-center gap-1 rounded-md px-1 py-1 hover:text-foreground',
            shellTokens.sidebar.sectionLabel,
          )}
        >
          <ChevronRight
            size={12}
            className={cn(
              'transition-transform',
              fileExpandedCategories.includes('local') && 'rotate-90',
            )}
          />
          <span className="flex-1 truncate text-left">Drives</span>
          <span className="text-[10px]">
            {2
              + (platformDriveEnabled ? 1 : 0)
              + (isWorkspaceAdmin && systemDriveEnabled ? 1 : 0)
              + syncedFolders.length}
          </span>
        </button>

        {fileExpandedCategories.includes('local') && (
          <div className="ml-1 space-y-0.5">
            {renderDriveRow(
              'my-drive',
              'My Drive',
              <HardDrive size={iconSize} className="text-muted-foreground" />,
              () => {
                void openRemoteDrive('my-drive');
              },
            )}
            {renderDriveRow(
              'workspace',
              'Workspace Drive',
              <HardDrive size={iconSize} className="text-muted-foreground" />,
              () => {
                void openRemoteDrive('workspace');
              },
            )}
            {platformDriveEnabled
              ? renderDriveRow(
                  'platform-drive',
                  'Platform Drive',
                  <HardDrive size={iconSize} className="text-muted-foreground" />,
                  () => {
                    void openRemoteDrive('platform-drive');
                  },
                  'Files shared across every workspace where platform drive is enabled',
                )
              : null}
            {isWorkspaceAdmin && systemDriveEnabled
              ? renderDriveRow(
                  'system-drive',
                  'System Drive',
                  <Server size={iconSize} className="text-muted-foreground" />,
                  () => {
                    void openRemoteDrive('system-drive');
                  },
                  'Full object storage tree, visible to workspace owners and admins',
                )
              : null}
            {syncedFolders.map((folder) =>
              renderDriveRow(
                folder.id,
                folder.name,
                <Folder size={iconSize} className="text-muted-foreground" />,
                () => {
                  void openSyncedDrive(folder.id);
                },
                folder.name,
              ),
            )}
          </div>
        )}

        <div className="mt-2 space-y-0.5 border-t border-border/50 pt-2">
          <button
            type="button"
            onClick={() => setStarredExpanded((v) => !v)}
            className={cn(
              'flex w-full items-center gap-1 rounded-md px-1 py-1 hover:text-foreground',
              shellTokens.sidebar.sectionLabel,
            )}
          >
            <ChevronRight
              size={12}
              className={cn('transition-transform', starredExpanded && 'rotate-90')}
            />
            <Star size={11} className="fill-amber-400 text-amber-400" />
            <span className="flex-1 truncate text-left">Starred</span>
            {workspaceStarredItems.length > 0 && (
              <span className="text-[10px]">
                {filtering ? `${visibleStarredItems.length}/${workspaceStarredItems.length}` : workspaceStarredItems.length}
              </span>
            )}
          </button>
          {starredExpanded && (
            <div className="ml-3 space-y-0.5">
              {workspaceStarredItems.length === 0 ? (
                <p className="px-2 py-1 text-[11px] text-muted-foreground">No starred items yet</p>
              ) : visibleStarredItems.length === 0 ? (
                <p className="px-2 py-1 text-[11px] text-muted-foreground">No matching starred items</p>
              ) : (
                visibleStarredItems.map((item) => (
                  <div
                    key={`${item.workspaceId}:${item.source}:${item.path}`}
                    data-ontology-tree-row
                    className="group flex items-center gap-0.5"
                  >
                    <button
                      type="button"
                      data-ontology-tree-item={`starred:${item.workspaceId}:${item.source}:${item.path}`}
                      data-ontology-tree-select
                      data-testid="files-explorer-starred"
                      onClick={() => {
                        if (item.type === 'folder') {
                          setStarredNavigation({ source: item.source, path: item.path });
                        } else {
                          const parentPath = item.path.includes('/')
                            ? item.path.substring(0, item.path.lastIndexOf('/'))
                            : '';
                          setStarredNavigation({
                            source: item.source,
                            path: parentPath,
                            previewPath: item.path,
                          });
                        }
                        router.push(
                          isMobilePanel
                            ? filesBrowsePath(currentWorkspaceId)
                            : getWorkspacePath(currentWorkspaceId, '/files'),
                        );
                      }}
                      className={cn(
                        'flex flex-1 items-center gap-1 rounded-md transition-colors',
                        rowPadClass,
                        EXPLORER_ROW_TYPO,
                        'hover:bg-workspace-accent-10',
                        activeSource === item.source && 'text-workspace-accent',
                      )}
                      title={item.path}
                    >
                      {item.type === 'folder' ? (
                        <Folder size={iconSize} className="flex-shrink-0 text-muted-foreground" />
                      ) : (
                        <File size={iconSize} className="flex-shrink-0 text-muted-foreground" />
                      )}
                      <span className="flex-1 truncate text-left">{item.name}</span>
                      {isMobilePanel && (
                        <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />
                      )}
                    </button>
                    <button
                      type="button"
                      title="Remove from starred"
                      onClick={() => unstarItem(item.path, item.workspaceId)}
                      className="hidden h-5 w-5 flex-shrink-0 items-center justify-center rounded text-amber-400 hover:text-amber-500 group-hover:flex"
                    >
                      <Star size={11} className="fill-current" />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </nav>
    </CollapsibleSection>
    </>
  );
}
