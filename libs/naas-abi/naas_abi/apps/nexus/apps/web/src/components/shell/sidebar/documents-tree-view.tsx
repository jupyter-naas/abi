'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, File, FileCode2, Folder, Image as ImageIcon, Presentation } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DocumentsProjectOverflowMenu } from '@/components/documents/documents-project-menu';
import { shellTokens } from '../tokens';
import {
  SLIDES_ALL_ROW_LABEL,
  SLIDES_DECK_FILE_NAME,
  SLIDES_TREE_ROOT_LABEL,
  isSectionsGalleryPath,
  type SectionsTreeDocumentNode,
  type SectionsTreeFileNode,
} from './documents-tree';

/**
 * The Documents sidebar tree.
 *
 * Nested disclosure lists rather than `role="tree"`: every row here is already
 * a real link or button, so Tab reaches all of them and Enter activates them.
 * Claiming `role="tree"` would promise one tab stop plus roving focus, which
 * this does not implement, and a false role is worse than no role.
 *
 * Documents are anchors, so cmd-click and middle-click open a document in a new tab
 * while a plain click stays inside the workspace shell.
 */

const ROW_CLASS =
  'flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1 no-underline transition-colors hover:bg-workspace-accent-10';

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

function FileIcon({ node }: { node: SectionsTreeFileNode }) {
  if (node.type === 'dir') {
    return <Folder size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  if (node.name === SLIDES_DECK_FILE_NAME) {
    return <FileCode2 size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  if (/\.(png|jpe?g|gif|svg|webp)$/i.test(node.name)) {
    return <ImageIcon size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  return <File size={11} className="flex-shrink-0 text-muted-foreground" />;
}

function DocumentRow({
  document,
  currentPath,
  expanded,
  onToggleDocument,
  onOpenDocument,
  renaming,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  document: SectionsTreeDocumentNode;
  currentPath?: string;
  expanded: boolean;
  onToggleDocument: (slug: string) => void;
  onOpenDocument: (document: SectionsTreeDocumentNode) => void;
  renaming?: boolean;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(document.label);
  const canAct = Boolean(onStartRename && onRename && onArchive);

  const submitRename = () => {
    const next = editValue.trim();
    if (next && next !== document.label) onRename?.(document.slug, next);
    onCancelRename?.();
  };

  return (
    <div
      className={`sections-overflow-host flex items-center${showMenu ? ' is-menu-open' : ''}`}
      onContextMenu={(event) => {
        if (!canAct || renaming) return;
        event.preventDefault();
        setShowMenu(true);
      }}
    >
      <Twisty
        expanded={expanded}
        label={`${expanded ? 'Collapse' : 'Expand'} ${document.label}`}
        onToggle={() => onToggleDocument(document.slug)}
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
            data-testid="sections-rename-input"
          />
        </div>
      ) : (
        <>
          <Link
            href={document.href}
            onClick={() => onOpenDocument(document)}
            title={document.label}
            aria-current={document.href === currentPath ? 'page' : undefined}
            data-testid="documents-tree-document"
            data-slug={document.slug}
            className={cn(
              ROW_CLASS,
              shellTokens.sidebar.listRow,
              document.active
                ? 'bg-workspace-accent-15 font-medium text-workspace-accent'
                : 'text-foreground',
            )}
          >
            <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{document.label}</span>
          </Link>
          {canAct ? (
            <DocumentsProjectOverflowMenu
              open={showMenu}
              onOpenChange={setShowMenu}
              onRename={() => {
                setEditValue(document.label);
                onStartRename?.(document.slug);
              }}
              onArchive={() => onArchive?.(document.slug)}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function FileRows({
  nodes,
  documentHref,
  onOpenDocument,
  expandedDirs,
  onToggleDir,
}: {
  nodes: SectionsTreeFileNode[];
  documentHref: string;
  onOpenDocument: () => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
}) {
  return (
    <ul className="ml-3 list-none space-y-0.5 p-0">
      {nodes.map((node) => {
        const expandable = node.type === 'dir' && node.children.length > 0;
        const expanded = expandable && expandedDirs.includes(node.path);
        // document.html is the file the Documents pane edits, so it routes to the
        // document. project.json and assets have no viewer, so they stay inert
        // instead of pretending to be clickable.
        const isDocumentFile = node.type === 'file' && node.name === SLIDES_DECK_FILE_NAME;
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
              {isDocumentFile ? (
                <Link
                  href={documentHref}
                  onClick={onOpenDocument}
                  title={node.path}
                  data-testid="documents-tree-file"
                  className={cn(
                    ROW_CLASS,
                    shellTokens.sidebar.listRow,
                    node.open ? 'text-workspace-accent' : 'text-foreground',
                  )}
                >
                  <FileIcon node={node} />
                  <span className="truncate">{node.name}</span>
                </Link>
              ) : (
                <span
                  title={node.path}
                  data-testid="documents-tree-file"
                  className={cn(
                    'flex min-w-0 flex-1 items-center gap-2 px-2 py-1 text-muted-foreground',
                    shellTokens.sidebar.listRow,
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
                documentHref={documentHref}
                onOpenDocument={onOpenDocument}
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

function DocumentList({
  documents,
  currentPath,
  expandedDocuments,
  onToggleDocument,
  expandedDirs,
  onToggleDir,
  onOpenDocument,
  emptyLabel,
  renamingSlug,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  documents: SectionsTreeDocumentNode[];
  currentPath?: string;
  expandedDocuments: string[];
  onToggleDocument: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenDocument: (document: SectionsTreeDocumentNode) => void;
  emptyLabel: string;
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  if (documents.length === 0) {
    return (
      <li>
        <p className={cn('px-2 py-1 text-muted-foreground', shellTokens.sidebar.listRow)}>
          {emptyLabel}
        </p>
      </li>
    );
  }
  return (
    <>
      {documents.map((document) => {
        const expanded = expandedDocuments.includes(document.slug);
        return (
          <li key={document.slug}>
            <DocumentRow
              document={document}
              currentPath={currentPath}
              expanded={expanded}
              onToggleDocument={onToggleDocument}
              onOpenDocument={onOpenDocument}
              renaming={renamingSlug === document.slug}
              onStartRename={onStartRename}
              onRename={onRename}
              onCancelRename={onCancelRename}
              onArchive={onArchive}
            />
            {expanded ? (
              document.filesLoaded ? (
                <FileRows
                  nodes={document.files}
                  documentHref={document.href}
                  onOpenDocument={() => onOpenDocument(document)}
                  expandedDirs={expandedDirs}
                  onToggleDir={onToggleDir}
                />
              ) : (
                <p
                  className={cn(
                    'ml-3 px-2 py-1 pl-6 text-muted-foreground',
                    shellTokens.sidebar.listRow,
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

export function SectionsTreeView({
  documents,
  rootHref,
  currentPath,
  rootExpanded,
  onToggleRoot,
  expandedDocuments,
  onToggleDocument,
  expandedDirs,
  onToggleDir,
  onOpenDocument,
  emptyLabel = 'No documents yet',
  hideRoot = false,
  renamingSlug,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  documents: SectionsTreeDocumentNode[];
  /** Root row links to the Documents index. */
  rootHref: string;
  /**
   * Route the sidebar is on. A document keeps its selection styling as the last
   * one opened, but only claims to be the current page when the route is
   * really on it.
   */
  currentPath?: string;
  rootExpanded: boolean;
  onToggleRoot: () => void;
  expandedDocuments: string[];
  onToggleDocument: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenDocument: (document: SectionsTreeDocumentNode) => void;
  emptyLabel?: string;
  /** Archived list: document rows only, no second `sections` root. */
  hideRoot?: boolean;
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  const list = (
    <DocumentList
      documents={documents}
      currentPath={currentPath}
      expandedDocuments={expandedDocuments}
      onToggleDocument={onToggleDocument}
      expandedDirs={expandedDirs}
      onToggleDir={onToggleDir}
      onOpenDocument={onOpenDocument}
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
      <ul className="list-none space-y-0.5 p-0" data-testid="documents-tree-archived">
        {list}
      </ul>
    );
  }

  const onGallery = isSectionsGalleryPath(currentPath, rootHref);

  return (
    <ul className="list-none space-y-0.5 p-0" data-testid="documents-tree">
      <li>
        <Link
          href={rootHref}
          data-testid="documents-tree-all"
          aria-current={onGallery ? 'page' : undefined}
          className={cn(
            ROW_CLASS,
            shellTokens.sidebar.listRow,
            onGallery
              ? 'bg-muted font-medium text-foreground'
              : 'text-muted-foreground',
          )}
        >
          <Presentation size={12} className="flex-shrink-0 text-muted-foreground" />
          <span className="truncate">{SLIDES_ALL_ROW_LABEL}</span>
        </Link>
      </li>
      <li>
        <div className="flex items-center">
          <Twisty
            expanded={rootExpanded}
            label={`${rootExpanded ? 'Collapse' : 'Expand'} ${SLIDES_TREE_ROOT_LABEL}`}
            onToggle={onToggleRoot}
          />
          <Link
            href={rootHref}
            data-testid="documents-tree-root"
            className={cn(ROW_CLASS, shellTokens.sidebar.listRow, 'text-foreground')}
          >
            <Folder size={12} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{SLIDES_TREE_ROOT_LABEL}</span>
          </Link>
        </div>

        {rootExpanded ? <ul className="ml-3 list-none space-y-0.5 p-0">{list}</ul> : null}
      </li>
    </ul>
  );
}
