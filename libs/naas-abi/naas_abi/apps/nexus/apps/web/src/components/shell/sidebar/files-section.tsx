'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight, File, Files, Folder, Search, Star, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useFilesStore, type FileInfo } from '@/stores/files';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { getApiUrl } from '@/lib/config';
import { useFileViewsStore, useOfferedFileViews } from '@/hooks/use-file-views';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { filesBrowsePath } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import {
  ALL_VIEWS,
  driveRootForSource,
  isFileViewSource,
  type FileViewSource,
} from '@/app/workspace/[workspaceId]/files/lib/drive-label';
import { FilesViewPicker } from '@/app/workspace/[workspaceId]/files/components/files-view-picker';
import { FileViewIcon } from '@/app/workspace/[workspaceId]/files/components/files-views-root';
import { FILES_EXPLORER_REFRESH_EVENT } from '@/app/workspace/[workspaceId]/files/lib/explorer-refresh';
import { isSystemPath, withoutSystemFiles } from '@/lib/system-files';
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

/** Under All Views, the views shown expanded when the sidebar opens or the workspace changes. */
const DEFAULT_EXPANDED_VIEWS: readonly FileViewSource[] = ['workspace-files', 'my-files'];

export function FilesSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const rowPadClass = isMobilePanel ? 'px-2 py-2.5 min-h-11' : 'px-2 py-1';
  const iconSize = isMobilePanel ? 14 : 12;
  const treeKeyboard = useOntologyTreeKeyboard();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  // The views the caller may open from this workspace (GET /api/files/views), under the chosen drive.
  const {
    status: viewsStatus,
    views: fileViews,
    folders: viewFolderList,
  } = useOfferedFileViews(currentWorkspaceId);
  // Organization Files is the current workspace's organization's.
  const organizationId = currentWorkspace?.organizationId;
  const [starredExpanded, setStarredExpanded] = useState(true);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [rawFolderCache, setFolderCache] = useState<Record<string, FileInfo[]>>({});
  const [loadingDirs, setLoadingDirs] = useState<Record<string, boolean>>({});
  const [dirErrors, setDirErrors] = useState<Record<string, string | null>>({});
  const [explorerQuery, setExplorerQuery] = useState('');
  const loadGeneration = useRef(0);
  const folderCacheRef = useRef(rawFolderCache);
  folderCacheRef.current = rawFolderCache;
  // The tree caches whole listings and filters on render, so View → Show
  // system files flips without refetching every open folder.
  const showSystemFiles = useFilesStore((s) => s.showSystemFiles);
  const folderCache = useMemo(
    () =>
      showSystemFiles
        ? rawFolderCache
        : Object.fromEntries(
            Object.entries(rawFolderCache).map(([key, entries]) => [key, withoutSystemFiles(entries, false)]),
          ),
    [rawFolderCache, showSystemFiles],
  );
  const {
    activeSource,
    setActiveSource,
    viewChoice,
    chooseView,
    activeDrive,
    chooseDrive,
    fetchFiles,
    currentPath,
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
   * View roots are listed under `''`, not the absolute root prefix.
   */
  const explorerLoadPath = useCallback(
    (source: string, path: string) => {
      const normalized = normalizeExplorerPath(path);
      if (!normalized) return '';
      if (isFileViewSource(source)) {
        const root = driveRootForSource(source, currentWorkspaceId || '', authUserId, organizationId);
        if (root && normalized === normalizeExplorerPath(root)) return '';
      }
      return normalized;
    },
    [authUserId, currentWorkspaceId, organizationId],
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
        let files: FileInfo[];
        if (source === 'my-files' && useAuthStore.getState().view) {
          // The person's own files: private in a view, nothing is asked for.
          files = [];
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
    [currentWorkspaceId],
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
      // View roots are not rendered as tree rows; still guard empty paths.
      // System files are read-only.
      if (!folderPath || isSystemPath(folderPath)) return;

      const newName = await prompt({
        title: 'Rename',
        description: `Rename "${folder.name}" to:`,
        defaultValue: folder.name,
        confirmLabel: 'Rename',
      });
      if (!newName || newName === folder.name) return;
      if (isSystemPath(newName.trim())) {
        await confirm({
          title: 'Invalid name',
          description: 'Names starting with "." are system files, which are read-only.',
          confirmLabel: 'OK',
        });
        return;
      }
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
      if (!folderPath || isSystemPath(folderPath)) return;

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

  /** Move a canvas or explorer item onto a folder row (same view only). */
  const handleMoveOntoFolder = useCallback(
    async (source: string, targetPath: string, draggedPath: string) => {
      // renameFile uses activeSource scope; reject cross-view drops.
      if (source !== activeSource) return;

      const from = normalizeExplorerPath(draggedPath);
      const toFolder = normalizeExplorerPath(targetPath);
      if (!canDropOntoExplorerFolder(from, toFolder)) return;
      if (isSystemPath(from) || isSystemPath(toFolder)) return;

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
    ],
  );

  /** Open a view's root in the browser (a view row of All Views). */
  const openView = async (source: FileViewSource) => {
    setActiveSource(source);
    ensureExpanded(source, '');
    void loadDir(source, '', { force: true });
    await fetchFiles('', {
      limit: 50,
      offset: 0,
      search: '',
      workspaceId: currentWorkspaceId ?? undefined,
    });
    openFilesBrowser();
  };

  const activeView = isFileViewSource(activeSource) ? activeSource : null;
  const driveRoot = activeView
    ? driveRootForSource(activeView, currentWorkspaceId || '', authUserId, organizationId)
    : '';

  // Keep the open view expanded and open ancestor dirs so the current folder is visible.
  useEffect(() => {
    if (!activeView) return;
    for (const dir of explorerDirsToOpen(currentPath, driveRoot)) {
      ensureExpanded(activeView, dir);
      void loadDir(activeView, dir);
    }
  }, [activeView, currentPath, driveRoot, ensureExpanded, loadDir]);

  // Drop explorer cache when the workspace changes; the default views start expanded.
  useEffect(() => {
    loadGeneration.current += 1;
    folderCacheRef.current = {};
    setFolderCache({});
    setLoadingDirs({});
    setDirErrors({});
    setExpandedDirs(DEFAULT_EXPANDED_VIEWS.map((source) => explorerDirKey(source, '')));
    setExplorerQuery('');
  }, [currentWorkspaceId]);

  // List what opens expanded (cached loads are skipped): under All Views the default
  // views the caller may open, else the chosen view's root.
  useEffect(() => {
    if (!currentWorkspaceId) return;
    if (isFileViewSource(viewChoice)) {
      void loadDir(viewChoice, '');
      return;
    }
    for (const source of DEFAULT_EXPANDED_VIEWS) {
      if (viewFolderList.some((folder) => folder.source === source)) void loadDir(source, '');
    }
  }, [currentWorkspaceId, loadDir, viewChoice, viewFolderList]);

  // File → Refresh (TopNav) refreshes the page listing; the tree reloads here.
  const reloadTreeRef = useRef<() => void>(() => {});
  reloadTreeRef.current = () => {
    // Which views are open is asked again too (a policy may have changed).
    void useFileViewsStore.getState().load(currentWorkspaceId ?? '', { force: true });
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
  };

  useEffect(() => {
    const onRefresh = () => reloadTreeRef.current();
    window.addEventListener(FILES_EXPLORER_REFRESH_EVENT, onRefresh);
    return () => window.removeEventListener(FILES_EXPLORER_REFRESH_EVENT, onRefresh);
  }, []);

  const viewExpanded = (source: string) =>
    expandedDirs.includes(explorerDirKey(source, ''));

  const renderTree = (source: FileViewSource, depth: number) => (
    <FilesExplorerTree
      source={source}
      parentPath=""
      depth={depth}
      folderCache={folderCache}
      loadingDirs={loadingDirs}
      dirErrors={dirErrors}
      expandedDirs={expandedDirs}
      activeSource={activeSource}
      currentPath={currentPath}
      query={explorerQuery}
      canDragFolders
      onToggleDir={toggleDir}
      onOpenFolder={openFolder}
      onOpenFile={openFile}
      onRenameFolder={handleRenameFolder}
      onDeleteFolder={handleDeleteFolder}
      onMoveOntoFolder={handleMoveOntoFolder}
      rowPadClass={rowPadClass}
      iconSize={iconSize}
    />
  );

  /** One folder of All Views: the view's name, its tree below. */
  const renderViewRow = (sourceId: FileViewSource, label: string) => {
    if (!explorerDriveMatchesQuery(label, sourceId, explorerQuery, folderCache)) {
      return null;
    }
    const labelMatch = matchesExplorerQuery(label, explorerQuery);
    const expanded =
      viewExpanded(sourceId)
      || (filtering && !labelMatch);
    const viewActive = activeSource === sourceId;
    const sourceRoot = driveRootForSource(sourceId, currentWorkspaceId || '', authUserId, organizationId);
    const normalizedCurrent = normalizeExplorerPath(currentPath);
    const atRoot =
      viewActive
      && (normalizedCurrent === ''
        || (sourceRoot !== '' && normalizedCurrent === sourceRoot));
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
            title={label}
            aria-current={atRoot ? 'page' : undefined}
            data-ontology-tree-item={`view:${sourceId}`}
            data-ontology-tree-select
            data-testid="files-explorer-view"
            onClick={() => {
              void openView(sourceId);
            }}
            className={cn(
              'flex min-w-0 flex-1 items-center gap-1 rounded-md transition-colors',
              rowPadClass,
              EXPLORER_ROW_TYPO,
              'hover:bg-workspace-accent-10',
              viewActive && 'bg-workspace-accent-15 text-workspace-accent',
            )}
          >
            <FileViewIcon source={sourceId} size={iconSize} className="flex-shrink-0 text-muted-foreground" />
            <span className="flex-1 truncate text-left">{label}</span>
            {isMobilePanel && (
              <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />
            )}
          </button>
        </div>
        {expanded ? renderTree(sourceId, 1) : null}
      </div>
    );
  };

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
      <FilesViewPicker
        views={fileViews}
        drive={activeDrive}
        view={viewChoice}
        onDriveChange={chooseDrive}
        onViewChange={chooseView}
        compact
      />
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
        {isFileViewSource(viewChoice) ? (
          renderTree(viewChoice, 0)
        ) : viewFolderList.length === 0 ? (
          <p className={cn('px-2 py-1 text-muted-foreground', EXPLORER_ROW_TYPO)} role="status">
            {viewsStatus === 'loading' ? 'Loading…' : 'No view of the files is open to you here.'}
          </p>
        ) : (
          <div className="space-y-0.5">
            {viewFolderList.map((folder) => renderViewRow(folder.source, folder.label))}
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
