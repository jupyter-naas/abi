'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, File, FileCode2, Folder, Image as ImageIcon, Presentation } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SlidesProjectOverflowMenu } from '@/components/slides/slides-project-menu';
import { shellTokens } from '../tokens';
import {
  SLIDES_ALL_ROW_LABEL,
  SLIDES_DECK_FILE_NAME,
  SLIDES_TREE_ROOT_LABEL,
  isSlidesGalleryPath,
  type SlidesTreeDeckNode,
  type SlidesTreeFileNode,
} from './slides-tree';

/**
 * The Slides sidebar tree.
 *
 * Nested disclosure lists rather than `role="tree"`: every row here is already
 * a real link or button, so Tab reaches all of them and Enter activates them.
 * Claiming `role="tree"` would promise one tab stop plus roving focus, which
 * this does not implement, and a false role is worse than no role.
 *
 * Decks are anchors, so cmd-click and middle-click open a deck in a new tab
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

function FileIcon({ node }: { node: SlidesTreeFileNode }) {
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

function DeckRow({
  deck,
  currentPath,
  expanded,
  onToggleDeck,
  onOpenDeck,
  renaming,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  deck: SlidesTreeDeckNode;
  currentPath?: string;
  expanded: boolean;
  onToggleDeck: (slug: string) => void;
  onOpenDeck: (deck: SlidesTreeDeckNode) => void;
  renaming?: boolean;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(deck.label);
  const canAct = Boolean(onStartRename && onRename && onArchive);

  const submitRename = () => {
    const next = editValue.trim();
    if (next && next !== deck.label) onRename?.(deck.slug, next);
    onCancelRename?.();
  };

  return (
    <div
      className={`slides-overflow-host flex items-center${showMenu ? ' is-menu-open' : ''}`}
      onContextMenu={(event) => {
        if (!canAct || renaming) return;
        event.preventDefault();
        setShowMenu(true);
      }}
    >
      <Twisty
        expanded={expanded}
        label={`${expanded ? 'Collapse' : 'Expand'} ${deck.label}`}
        onToggle={() => onToggleDeck(deck.slug)}
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
            data-testid="slides-rename-input"
          />
        </div>
      ) : (
        <>
          <Link
            href={deck.href}
            onClick={() => onOpenDeck(deck)}
            title={deck.label}
            aria-current={deck.href === currentPath ? 'page' : undefined}
            data-testid="slides-tree-deck"
            data-slug={deck.slug}
            className={cn(
              ROW_CLASS,
              shellTokens.sidebar.listRow,
              deck.active
                ? 'bg-workspace-accent-15 font-medium text-workspace-accent'
                : 'text-foreground',
            )}
          >
            <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{deck.label}</span>
          </Link>
          {canAct ? (
            <SlidesProjectOverflowMenu
              open={showMenu}
              onOpenChange={setShowMenu}
              onRename={() => {
                setEditValue(deck.label);
                onStartRename?.(deck.slug);
              }}
              onArchive={() => onArchive?.(deck.slug)}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function FileRows({
  nodes,
  deckHref,
  onOpenDeck,
  expandedDirs,
  onToggleDir,
}: {
  nodes: SlidesTreeFileNode[];
  deckHref: string;
  onOpenDeck: () => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
}) {
  return (
    <ul className="ml-3 list-none space-y-0.5 p-0">
      {nodes.map((node) => {
        const expandable = node.type === 'dir' && node.children.length > 0;
        const expanded = expandable && expandedDirs.includes(node.path);
        // deck.html is the file the Slides pane edits, so it routes to the
        // deck. project.json and assets have no viewer, so they stay inert
        // instead of pretending to be clickable.
        const isDeckFile = node.type === 'file' && node.name === SLIDES_DECK_FILE_NAME;
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
              {isDeckFile ? (
                <Link
                  href={deckHref}
                  onClick={onOpenDeck}
                  title={node.path}
                  data-testid="slides-tree-file"
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
                  data-testid="slides-tree-file"
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
                deckHref={deckHref}
                onOpenDeck={onOpenDeck}
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

function DeckList({
  decks,
  currentPath,
  expandedDecks,
  onToggleDeck,
  expandedDirs,
  onToggleDir,
  onOpenDeck,
  emptyLabel,
  renamingSlug,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  decks: SlidesTreeDeckNode[];
  currentPath?: string;
  expandedDecks: string[];
  onToggleDeck: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenDeck: (deck: SlidesTreeDeckNode) => void;
  emptyLabel: string;
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  if (decks.length === 0) {
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
      {decks.map((deck) => {
        const expanded = expandedDecks.includes(deck.slug);
        return (
          <li key={deck.slug}>
            <DeckRow
              deck={deck}
              currentPath={currentPath}
              expanded={expanded}
              onToggleDeck={onToggleDeck}
              onOpenDeck={onOpenDeck}
              renaming={renamingSlug === deck.slug}
              onStartRename={onStartRename}
              onRename={onRename}
              onCancelRename={onCancelRename}
              onArchive={onArchive}
            />
            {expanded ? (
              deck.filesLoaded ? (
                <FileRows
                  nodes={deck.files}
                  deckHref={deck.href}
                  onOpenDeck={() => onOpenDeck(deck)}
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

export function SlidesTreeView({
  decks,
  rootHref,
  currentPath,
  rootExpanded,
  onToggleRoot,
  expandedDecks,
  onToggleDeck,
  expandedDirs,
  onToggleDir,
  onOpenDeck,
  emptyLabel = 'No presentations yet',
  hideRoot = false,
  renamingSlug,
  onStartRename,
  onRename,
  onCancelRename,
  onArchive,
}: {
  decks: SlidesTreeDeckNode[];
  /** Root row links to the Slides index. */
  rootHref: string;
  /**
   * Route the sidebar is on. A deck keeps its selection styling as the last
   * one opened, but only claims to be the current page when the route is
   * really on it.
   */
  currentPath?: string;
  rootExpanded: boolean;
  onToggleRoot: () => void;
  expandedDecks: string[];
  onToggleDeck: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenDeck: (deck: SlidesTreeDeckNode) => void;
  emptyLabel?: string;
  /** Archived list: deck rows only, no second `slides` root. */
  hideRoot?: boolean;
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
}) {
  const list = (
    <DeckList
      decks={decks}
      currentPath={currentPath}
      expandedDecks={expandedDecks}
      onToggleDeck={onToggleDeck}
      expandedDirs={expandedDirs}
      onToggleDir={onToggleDir}
      onOpenDeck={onOpenDeck}
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
      <ul className="list-none space-y-0.5 p-0" data-testid="slides-tree-archived">
        {list}
      </ul>
    );
  }

  const onGallery = isSlidesGalleryPath(currentPath, rootHref);

  return (
    <ul className="list-none space-y-0.5 p-0" data-testid="slides-tree">
      <li>
        <Link
          href={rootHref}
          data-testid="slides-tree-all"
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
            data-testid="slides-tree-root"
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
