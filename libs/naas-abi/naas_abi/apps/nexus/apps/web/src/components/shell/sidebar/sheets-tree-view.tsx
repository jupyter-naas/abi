'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, File, FileCode2, Folder, Image as ImageIcon, Table2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SheetsProjectOverflowMenu } from '@/components/sheets/sheets-project-menu';
import {
  SHEETS_ALL_ROW_LABEL,
  SHEETS_WORKBOOK_FILE_NAME,
  SHEETS_TREE_ROOT_LABEL,
  isSheetsGalleryPath,
  type SheetsTreeWorkbookNode,
  type SheetsTreeFileNode,
} from './sheets-tree';

/**
 * The Sheets sidebar tree.
 *
 * Nested disclosure lists rather than `role="tree"`: every row here is already
 * a real link or button, so Tab reaches all of them and Enter activates them.
 * Claiming `role="tree"` would promise one tab stop plus roving focus, which
 * this does not implement, and a false role is worse than no role.
 *
 * Workbooks are anchors, so cmd-click and middle-click open a workbook in a new
 * tab while a plain click stays inside the workspace shell.
 */

/** Match Ontology/KG/Files density (12/18); keep global shell listRow at 14/19. */
const SHEETS_ROW_TYPO = 'sheets-sidebar-list-row';

const ROW_CLASS =
  'flex min-w-0 flex-1 items-center gap-1 rounded-md px-2 py-1 no-underline transition-colors hover:bg-workspace-accent-10';

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
      aria-expanded={expanded}
      aria-label={label}
      onClick={onToggle}
      className="flex h-5 w-4 flex-shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
    >
      <ChevronRight size={11} className={cn('transition-transform', expanded && 'rotate-90')} />
    </button>
  );
}

/** Keeps a row's text aligned with rows that do have a disclosure triangle. */
function TwistySpacer() {
  return <span className="h-5 w-4 flex-shrink-0" aria-hidden />;
}

function FileIcon({ node }: { node: SheetsTreeFileNode }) {
  if (node.type === 'dir') {
    return <Folder size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  if (node.name === SHEETS_WORKBOOK_FILE_NAME) {
    return <FileCode2 size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  if (/\.(png|jpe?g|gif|svg|webp)$/i.test(node.name)) {
    return <ImageIcon size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  return <File size={11} className="flex-shrink-0 text-muted-foreground" />;
}

function WorkbookRow({
  workbook,
  currentPath,
  expanded,
  onToggleWorkbook,
  onOpenWorkbook,
  renaming,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  workbook: SheetsTreeWorkbookNode;
  currentPath?: string;
  expanded: boolean;
  onToggleWorkbook: (slug: string) => void;
  onOpenWorkbook: (workbook: SheetsTreeWorkbookNode) => void;
  renaming?: boolean;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(workbook.label);
  const canAct = Boolean(onStartRename && onRename && onArchive);

  const submitRename = () => {
    const next = editValue.trim();
    if (next && next !== workbook.label) onRename?.(workbook.slug, next);
    onCancelRename?.();
  };

  return (
    <div
      className={`sheets-overflow-host flex items-center${showMenu ? ' is-menu-open' : ''}`}
      onContextMenu={(event) => {
        if (!canAct || renaming) return;
        event.preventDefault();
        setShowMenu(true);
      }}
    >
      <Twisty
        expanded={expanded}
        label={`${expanded ? 'Collapse' : 'Expand'} ${workbook.label}`}
        onToggle={() => onToggleWorkbook(workbook.slug)}
      />
      {renaming ? (
        <div className="chat-rename-row min-w-0 flex-1">
          <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
          <input
            type="text"
            value={editValue}
            onChange={(event) => setEditValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submitRename();
              else if (event.key === 'Escape') onCancelRename?.();
            }}
            onBlur={submitRename}
            autoFocus
            className="chat-rename-input"
            data-testid="sheets-rename-input"
          />
        </div>
      ) : (
        <>
          <Link
            href={workbook.href}
            onClick={() => onOpenWorkbook(workbook)}
            title={workbook.label}
            aria-current={workbook.href === currentPath ? 'page' : undefined}
            data-testid="sheets-tree-workbook"
            data-slug={workbook.slug}
            className={cn(
              ROW_CLASS,
              SHEETS_ROW_TYPO,
              workbook.active
                ? 'bg-workspace-accent-15 font-medium text-workspace-accent'
                : 'text-foreground',
            )}
          >
            <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{workbook.label}</span>
          </Link>
          {canAct ? (
            <SheetsProjectOverflowMenu
              open={showMenu}
              onOpenChange={setShowMenu}
              onRename={() => {
                setEditValue(workbook.label);
                onStartRename?.(workbook.slug);
              }}
              onArchive={() => onArchive?.(workbook.slug)}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function FileRows({
  nodes,
  workbookHref,
  onOpenWorkbook,
  expandedDirs,
  onToggleDir,
}: {
  nodes: SheetsTreeFileNode[];
  workbookHref: string;
  onOpenWorkbook: () => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
}) {
  return (
    <ul className="ml-3 list-none space-y-0.5 p-0">
      {nodes.map((node) => {
        const expandable = node.type === 'dir' && node.children.length > 0;
        const expanded = expandable && expandedDirs.includes(node.path);
        // workbook.html is the file the Sheets pane edits, so it routes to the
        // workbook. project.json and assets have no viewer, so they stay inert
        // instead of pretending to be clickable.
        const isWorkbookFile = node.type === 'file' && node.name === SHEETS_WORKBOOK_FILE_NAME;
        return (
          <li key={node.path || node.name}>
            <div className="flex items-center">
              {expandable ? (
                <Twisty
                  expanded={expanded}
                  label={`${expanded ? 'Collapse' : 'Expand'} ${node.name}`}
                  onToggle={() => onToggleDir(node.path)}
                />
              ) : (
                <TwistySpacer />
              )}
              {isWorkbookFile ? (
                <Link
                  href={workbookHref}
                  onClick={onOpenWorkbook}
                  title={node.path}
                  data-testid="sheets-tree-file"
                  className={cn(
                    ROW_CLASS,
                    SHEETS_ROW_TYPO,
                    node.open ? 'text-workspace-accent' : 'text-foreground',
                  )}
                >
                  <FileIcon node={node} />
                  <span className="truncate">{node.name}</span>
                </Link>
              ) : (
                <span
                  title={node.path}
                  data-testid="sheets-tree-file"
                  className={cn(
                    'flex min-w-0 flex-1 items-center gap-1 px-2 py-1 text-muted-foreground',
                    SHEETS_ROW_TYPO,
                  )}
                >
                  <FileIcon node={node} />
                  <span className="truncate">{node.name}</span>
                </span>
              )}
            </div>
            {expanded ? (
              <FileRows
                nodes={node.children}
                workbookHref={workbookHref}
                onOpenWorkbook={onOpenWorkbook}
                expandedDirs={expandedDirs}
                onToggleDir={onToggleDir}
              />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function WorkbookList({
  workbooks,
  currentPath,
  expandedWorkbooks,
  onToggleWorkbook,
  expandedDirs,
  onToggleDir,
  onOpenWorkbook,
  emptyLabel,
  renamingSlug,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  workbooks: SheetsTreeWorkbookNode[];
  currentPath?: string;
  expandedWorkbooks: string[];
  onToggleWorkbook: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenWorkbook: (workbook: SheetsTreeWorkbookNode) => void;
  emptyLabel: string;
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  if (workbooks.length === 0) {
    return (
      <li>
        <p className={cn('px-2 py-1 text-muted-foreground', SHEETS_ROW_TYPO)}>
          {emptyLabel}
        </p>
      </li>
    );
  }
  return (
    <>
      {workbooks.map((workbook) => {
        const expanded = expandedWorkbooks.includes(workbook.slug);
        return (
          <li key={workbook.slug}>
            <WorkbookRow
              workbook={workbook}
              currentPath={currentPath}
              expanded={expanded}
              onToggleWorkbook={onToggleWorkbook}
              onOpenWorkbook={onOpenWorkbook}
              renaming={renamingSlug === workbook.slug}
              onStartRename={onStartRename}
              onRename={onRename}
              onCancelRename={onCancelRename}
              onArchive={onArchive}
            />
            {expanded ? (
              workbook.filesLoaded ? (
                <FileRows
                  nodes={workbook.files}
                  workbookHref={workbook.href}
                  onOpenWorkbook={() => onOpenWorkbook(workbook)}
                  expandedDirs={expandedDirs}
                  onToggleDir={onToggleDir}
                />
              ) : (
                <p
                  className={cn(
                    'ml-3 px-2 py-1 pl-6 text-muted-foreground',
                    SHEETS_ROW_TYPO,
                  )}
                >
                  Loading
                </p>
              )
            ) : null}
          </li>
        );
      })}
    </>
  );
}

export function SheetsTreeView({
  workbooks,
  rootHref,
  currentPath,
  rootExpanded,
  onToggleRoot,
  expandedWorkbooks,
  onToggleWorkbook,
  expandedDirs,
  onToggleDir,
  onOpenWorkbook,
  emptyLabel = 'No workbooks yet',
  hideRoot = false,
  renamingSlug,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  workbooks: SheetsTreeWorkbookNode[];
  /** Root row links to the Sheets index. */
  rootHref: string;
  /**
   * Route the sidebar is on. A workbook keeps its selection styling as the last
   * one opened, but only claims to be the current page when the route is
   * really on it.
   */
  currentPath?: string;
  rootExpanded: boolean;
  onToggleRoot: () => void;
  expandedWorkbooks: string[];
  onToggleWorkbook: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenWorkbook: (workbook: SheetsTreeWorkbookNode) => void;
  emptyLabel?: string;
  /** Archived list: workbook rows only, no second `sheets` root. */
  hideRoot?: boolean;
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  const list = (
    <WorkbookList
      workbooks={workbooks}
      currentPath={currentPath}
      expandedWorkbooks={expandedWorkbooks}
      onToggleWorkbook={onToggleWorkbook}
      expandedDirs={expandedDirs}
      onToggleDir={onToggleDir}
      onOpenWorkbook={onOpenWorkbook}
      emptyLabel={emptyLabel}
      renamingSlug={renamingSlug}
      onStartRename={onStartRename}
      onRename={onRename}
      onCancelRename={onCancelRename}
      onArchive={onArchive}
    />
  );

  if (hideRoot) {
    return (
      <ul className="list-none space-y-0.5 p-0" data-testid="sheets-tree-archived">
        {list}
      </ul>
    );
  }

  const onGallery = isSheetsGalleryPath(currentPath, rootHref);

  return (
    <ul className="list-none space-y-0.5 p-0" data-testid="sheets-tree">
      <li>
        <Link
          href={rootHref}
          data-testid="sheets-tree-all"
          aria-current={onGallery ? 'page' : undefined}
          className={cn(
            ROW_CLASS,
            SHEETS_ROW_TYPO,
            onGallery
              ? 'bg-muted font-medium text-foreground'
              : 'text-muted-foreground',
          )}
        >
          <Table2 size={12} className="flex-shrink-0 text-muted-foreground" />
          <span className="truncate">{SHEETS_ALL_ROW_LABEL}</span>
        </Link>
      </li>
      <li>
        <div className="flex items-center">
          <Twisty
            expanded={rootExpanded}
            label={`${rootExpanded ? 'Collapse' : 'Expand'} ${SHEETS_TREE_ROOT_LABEL}`}
            onToggle={onToggleRoot}
          />
          <Link
            href={rootHref}
            data-testid="sheets-tree-root"
            className={cn(ROW_CLASS, SHEETS_ROW_TYPO, 'text-foreground')}
          >
            <Folder size={12} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{SHEETS_TREE_ROOT_LABEL}</span>
          </Link>
        </div>

        {rootExpanded ? <ul className="ml-3 list-none space-y-0.5 p-0">{list}</ul> : null}
      </li>
    </ul>
  );
}
