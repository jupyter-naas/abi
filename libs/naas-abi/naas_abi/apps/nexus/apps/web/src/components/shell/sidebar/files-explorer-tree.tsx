'use client';

import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type DragEvent,
  type Ref,
} from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight, Edit2, File, Folder, MoreVertical, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FileInfo } from '@/stores/files';
import {
  placeDocumentsProjectMenu,
  type DocumentsProjectMenuPlacement,
} from '@/components/documents/documents-project-menu';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import '@/components/documents/documents-project-menu.css';
import {
  canDropOntoExplorerFolder,
  explorerDirKey,
  explorerLoadedSubtreeMatches,
  filterExplorerEntriesByQuery,
  isExplorerPathSelected,
  matchesExplorerQuery,
  normalizeExplorerPath,
  NEXUS_FILE_DRAG_MIME,
} from './files-explorer';

const EXPLORER_ROW_TYPO = 'files-explorer-list-row';

const ROW_CLASS =
  'flex min-w-0 flex-1 items-center gap-1 rounded-md px-2 py-1 text-left transition-colors hover:bg-workspace-accent-10';

const useIsoLayoutEffect =
  typeof window !== 'undefined' ? useLayoutEffect : useEffect;

function Twisty({
  expanded,
  label,
  onToggle,
}: {
  expanded: boolean;
  label: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      data-ontology-tree-toggle
      aria-expanded={expanded}
      aria-label={label}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      className="flex h-5 w-4 flex-shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
    >
      <ChevronRight size={11} className={cn('transition-transform', expanded && 'rotate-90')} />
    </button>
  );
}

function FilesExplorerRowMenu({
  open,
  onOpenChange,
  onRename,
  onDelete,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<DocumentsProjectMenuPlacement | null>(null);
  const canPortal = typeof document !== 'undefined';

  useIsoLayoutEffect(() => {
    if (!open || !canPortal) {
      setPos(null);
      return;
    }
    const update = () => {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const menuEl = menuRef.current;
      setPos(
        placeDocumentsProjectMenu(
          rect,
          { width: window.innerWidth, height: window.innerHeight },
          {
            width: menuEl?.offsetWidth || 160,
            height: menuEl?.offsetHeight || 68,
          },
        ),
      );
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open, canPortal]);

  const panel = open ? (
    <FilesExplorerMenuPanel
      onRename={onRename}
      onDelete={onDelete}
      onOpenChange={onOpenChange}
      pos={canPortal ? pos : null}
      menuRef={menuRef}
    />
  ) : null;

  return (
    <div className="chat-list-row-wrap" data-testid="files-explorer-row-menu">
      <div
        ref={triggerRef}
        className="chat-list-row-menu-trigger"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenChange(!open);
        }}
        role="document"
        aria-label="Item options"
        title="More options"
      >
        <MoreVertical size={12} />
      </div>
      {open && !canPortal ? panel : null}
      {open && canPortal ? createPortal(panel, document.body) : null}
    </div>
  );
}

function FilesExplorerMenuPanel({
  onRename,
  onDelete,
  onOpenChange,
  pos,
  menuRef,
}: {
  onRename: () => void;
  onDelete: () => void;
  onOpenChange: (open: boolean) => void;
  pos: DocumentsProjectMenuPlacement | null;
  menuRef?: Ref<HTMLDivElement>;
}) {
  return (
    <>
      <div
        className="chat-context-menu-backdrop documents-project-menu-backdrop"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenChange(false);
        }}
      />
      <div
        ref={menuRef}
        className={`chat-context-menu documents-project-menu-panel${pos ? '' : ' is-measuring'}`}
        data-testid="files-explorer-menu-panel"
        data-placement={pos?.placement ?? 'below'}
        style={
          pos
            ? {
                position: 'fixed',
                top: pos.top,
                left: pos.left,
                right: 'auto',
                marginTop: 0,
              }
            : undefined
        }
      >
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onRename();
            onOpenChange(false);
          }}
          className="chat-context-menu-item"
          data-testid="files-explorer-rename"
        >
          <Edit2 size={12} />
          Rename
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDelete();
            onOpenChange(false);
          }}
          className="chat-context-menu-item is-destructive"
          data-testid="files-explorer-delete"
        >
          <Trash2 size={12} />
          Delete
        </button>
      </div>
    </>
  );
}

function ExplorerFileRow({
  file,
  source,
  activeSource,
  currentPath,
  canDragFolders,
  onOpenFile,
  onRenameFolder,
  onDeleteFolder,
  rowPadClass,
  iconSize,
}: {
  file: FileInfo;
  source: string;
  activeSource: string;
  currentPath: string;
  canDragFolders: boolean;
  onOpenFile: (source: string, file: FileInfo) => void;
  onRenameFolder: (source: string, folder: FileInfo) => void;
  onDeleteFolder: (source: string, folder: FileInfo) => void;
  rowPadClass: string;
  iconSize: number;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const filePath = normalizeExplorerPath(file.path);
  const selected = isExplorerPathSelected(
    filePath,
    currentPath,
    source,
    activeSource,
  );

  const handleDragStart = (event: DragEvent) => {
    if (!canDragFolders) return;
    event.dataTransfer.setData(NEXUS_FILE_DRAG_MIME, filePath);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <li key={`${source}::file::${filePath}`} data-ontology-tree-row>
      <div
        className={cn('sections-overflow-host flex items-center', showMenu && 'is-menu-open')}
        onContextMenu={(event) => {
          event.preventDefault();
          setShowMenu(true);
        }}
      >
        {/* Spacer matches folder twisty width so icons align. */}
        <span className="h-5 w-4 flex-shrink-0" aria-hidden />
        <button
          type="button"
          title={filePath || file.name}
          aria-current={selected ? 'page' : undefined}
          data-ontology-tree-item={`${source}::file::${filePath}`}
          data-ontology-tree-select
          data-testid="files-explorer-file"
          data-path={filePath}
          draggable={canDragFolders}
          onDragStart={canDragFolders ? handleDragStart : undefined}
          onClick={() => onOpenFile(source, file)}
          className={cn(
            ROW_CLASS,
            rowPadClass,
            EXPLORER_ROW_TYPO,
            selected
              ? 'bg-workspace-accent-15 font-medium text-workspace-accent'
              : 'text-foreground',
          )}
        >
          <File size={iconSize} className="flex-shrink-0 text-muted-foreground" />
          <span className="truncate">{file.name}</span>
        </button>
        <FilesExplorerRowMenu
          open={showMenu}
          onOpenChange={setShowMenu}
          onRename={() => onRenameFolder(source, file)}
          onDelete={() => onDeleteFolder(source, file)}
        />
      </div>
    </li>
  );
}

function ExplorerFolderRow({
  folder,
  source,
  depth,
  folderCache,
  loadingDirs,
  dirErrors,
  expandedDirs,
  activeSource,
  currentPath,
  query,
  canDragFolders,
  onToggleDir,
  onOpenFolder,
  onOpenFile,
  onRenameFolder,
  onDeleteFolder,
  onMoveOntoFolder,
  rowPadClass,
  iconSize,
}: {
  folder: FileInfo;
  source: string;
  depth: number;
  folderCache: Record<string, FileInfo[]>;
  loadingDirs: Record<string, boolean>;
  dirErrors: Record<string, string | null>;
  expandedDirs: string[];
  activeSource: string;
  currentPath: string;
  query: string;
  canDragFolders: boolean;
  onToggleDir: (source: string, path: string) => void;
  onOpenFolder: (source: string, path: string) => void;
  onOpenFile: (source: string, file: FileInfo) => void;
  onRenameFolder: (source: string, folder: FileInfo) => void;
  onDeleteFolder: (source: string, folder: FileInfo) => void;
  onMoveOntoFolder: (source: string, targetPath: string, draggedPath: string) => void;
  rowPadClass: string;
  iconSize: number;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [isDropTarget, setIsDropTarget] = useState(false);
  const folderPath = normalizeExplorerPath(folder.path);
  const dirKey = explorerDirKey(source, folderPath);
  const filtering = query.trim().length > 0;
  const nameMatch = matchesExplorerQuery(folder.name, query);
  const childMatch =
    filtering
    && !nameMatch
    && explorerLoadedSubtreeMatches(source, folderPath, query, folderCache);
  const expanded = expandedDirs.includes(dirKey) || (filtering && childMatch);
  const selected = isExplorerPathSelected(
    folderPath,
    currentPath,
    source,
    activeSource,
  );

  const isInternalDrag = (event: DragEvent) =>
    event.dataTransfer.types.includes(NEXUS_FILE_DRAG_MIME);

  const handleDragStart = (event: DragEvent) => {
    if (!canDragFolders) return;
    event.dataTransfer.setData(NEXUS_FILE_DRAG_MIME, folderPath);
    event.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (event: DragEvent) => {
    if (!canDragFolders || !isInternalDrag(event)) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'move';
    setIsDropTarget(true);
  };

  const handleDragLeave = (event: DragEvent) => {
    if (!canDragFolders || !isInternalDrag(event)) return;
    event.stopPropagation();
    setIsDropTarget(false);
  };

  const handleDrop = (event: DragEvent) => {
    if (!canDragFolders || !isInternalDrag(event)) return;
    event.preventDefault();
    event.stopPropagation();
    setIsDropTarget(false);
    const draggedPath = event.dataTransfer.getData(NEXUS_FILE_DRAG_MIME);
    if (!draggedPath) return;
    if (!canDropOntoExplorerFolder(draggedPath, folderPath)) return;
    onMoveOntoFolder(source, folderPath, draggedPath);
  };

  return (
    <li key={dirKey} data-ontology-tree-row>
      <div
        className={cn(
          'sections-overflow-host flex items-center',
          showMenu && 'is-menu-open',
          isDropTarget && 'rounded-md bg-workspace-accent-15 ring-1 ring-inset ring-workspace-accent',
        )}
        onContextMenu={(event) => {
          event.preventDefault();
          setShowMenu(true);
        }}
        onDragOver={canDragFolders ? handleDragOver : undefined}
        onDragLeave={canDragFolders ? handleDragLeave : undefined}
        onDrop={canDragFolders ? handleDrop : undefined}
      >
        <Twisty
          expanded={expanded}
          label={`${expanded ? 'Collapse' : 'Expand'} ${folder.name}`}
          onToggle={() => onToggleDir(source, folderPath)}
        />
        <button
          type="button"
          title={folderPath || folder.name}
          aria-current={selected ? 'page' : undefined}
          data-ontology-tree-item={`${source}::folder::${folderPath}`}
          data-ontology-tree-select
          data-testid="files-explorer-folder"
          data-path={folderPath}
          draggable={canDragFolders}
          onDragStart={canDragFolders ? handleDragStart : undefined}
          onDragEnd={() => setIsDropTarget(false)}
          onClick={() => onOpenFolder(source, folderPath)}
          className={cn(
            ROW_CLASS,
            rowPadClass,
            EXPLORER_ROW_TYPO,
            selected
              ? 'bg-workspace-accent-15 font-medium text-workspace-accent'
              : 'text-foreground',
          )}
        >
          <Folder size={iconSize} className="flex-shrink-0 text-muted-foreground" />
          <span className="truncate">{folder.name}</span>
        </button>
        <FilesExplorerRowMenu
          open={showMenu}
          onOpenChange={setShowMenu}
          onRename={() => onRenameFolder(source, folder)}
          onDelete={() => onDeleteFolder(source, folder)}
        />
      </div>
      {expanded ? (
        <FilesExplorerTree
          source={source}
          parentPath={folderPath}
          depth={depth + 1}
          folderCache={folderCache}
          loadingDirs={loadingDirs}
          dirErrors={dirErrors}
          expandedDirs={expandedDirs}
          activeSource={activeSource}
          currentPath={currentPath}
          query={query}
          canDragFolders={canDragFolders}
          onToggleDir={onToggleDir}
          onOpenFolder={onOpenFolder}
          onOpenFile={onOpenFile}
          onRenameFolder={onRenameFolder}
          onDeleteFolder={onDeleteFolder}
          onMoveOntoFolder={onMoveOntoFolder}
          rowPadClass={rowPadClass}
          iconSize={iconSize}
        />
      ) : null}
    </li>
  );
}

export function FilesExplorerTree({
  source,
  parentPath,
  depth,
  folderCache,
  loadingDirs,
  dirErrors,
  expandedDirs,
  activeSource,
  currentPath,
  query,
  canDragFolders,
  onToggleDir,
  onOpenFolder,
  onOpenFile,
  onRenameFolder,
  onDeleteFolder,
  onMoveOntoFolder,
  rowPadClass,
  iconSize,
}: {
  source: string;
  parentPath: string;
  depth: number;
  folderCache: Record<string, FileInfo[]>;
  loadingDirs: Record<string, boolean>;
  dirErrors: Record<string, string | null>;
  expandedDirs: string[];
  activeSource: string;
  currentPath: string;
  query: string;
  canDragFolders: boolean;
  onToggleDir: (source: string, path: string) => void;
  onOpenFolder: (source: string, path: string) => void;
  onOpenFile: (source: string, file: FileInfo) => void;
  onRenameFolder: (source: string, folder: FileInfo) => void;
  onDeleteFolder: (source: string, folder: FileInfo) => void;
  onMoveOntoFolder: (source: string, targetPath: string, draggedPath: string) => void;
  rowPadClass: string;
  iconSize: number;
}) {
  const key = explorerDirKey(source, parentPath);
  const loading = Boolean(loadingDirs[key]);
  const error = dirErrors[key];
  const cached = folderCache[key];
  const entries = cached
    ? filterExplorerEntriesByQuery(cached, query, source, folderCache)
    : [];
  const filtering = query.trim().length > 0;

  if (loading && !cached) {
    return (
      <p
        className={cn(
          'px-2 py-1 text-muted-foreground',
          depth > 0 && 'ml-3',
          EXPLORER_ROW_TYPO,
        )}
        role="status"
      >
        Loading…
      </p>
    );
  }

  if (error && !cached) {
    return (
      <p
        role="alert"
        className={cn(
          'px-2 py-1 text-destructive',
          depth > 0 && 'ml-3',
          EXPLORER_ROW_TYPO,
        )}
      >
        {error}
      </p>
    );
  }

  if (cached && entries.length === 0) {
    return (
      <p
        className={cn(
          'px-2 py-1 text-muted-foreground',
          depth > 0 && 'ml-3',
          EXPLORER_ROW_TYPO,
        )}
      >
        {filtering ? 'No matching items' : 'No items'}
      </p>
    );
  }

  return (
    <ul
      className={cn('list-none space-y-0.5 p-0', depth > 0 && 'ml-3')}
      data-testid="files-explorer-tree"
    >
      {entries.map((entry) =>
        entry.type === 'folder' ? (
          <ExplorerFolderRow
            key={explorerDirKey(source, normalizeExplorerPath(entry.path))}
            folder={entry}
            source={source}
            depth={depth}
            folderCache={folderCache}
            loadingDirs={loadingDirs}
            dirErrors={dirErrors}
            expandedDirs={expandedDirs}
            activeSource={activeSource}
            currentPath={currentPath}
            query={query}
            canDragFolders={canDragFolders}
            onToggleDir={onToggleDir}
            onOpenFolder={onOpenFolder}
            onOpenFile={onOpenFile}
            onRenameFolder={onRenameFolder}
            onDeleteFolder={onDeleteFolder}
            onMoveOntoFolder={onMoveOntoFolder}
            rowPadClass={rowPadClass}
            iconSize={iconSize}
          />
        ) : (
          <ExplorerFileRow
            key={`${source}::file::${normalizeExplorerPath(entry.path)}`}
            file={entry}
            source={source}
            activeSource={activeSource}
            currentPath={currentPath}
            canDragFolders={canDragFolders}
            onOpenFile={onOpenFile}
            onRenameFolder={onRenameFolder}
            onDeleteFolder={onDeleteFolder}
            rowPadClass={rowPadClass}
            iconSize={iconSize}
          />
        ),
      )}
    </ul>
  );
}
