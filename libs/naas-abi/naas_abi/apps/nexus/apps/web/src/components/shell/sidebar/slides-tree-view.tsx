'use client';

import Link from 'next/link';
import { ChevronRight, File, FileCode2, Folder, Image as ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { shellTokens } from '../tokens';
import {
  SLIDES_DECK_FILE_NAME,
  SLIDES_TREE_ROOT_LABEL,
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
}) {
  return (
    <ul className="list-none space-y-0.5 p-0" data-testid="slides-tree">
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

        {rootExpanded ? (
          <ul className="ml-3 list-none space-y-0.5 p-0">
            {decks.length === 0 ? (
              <li>
                <p
                  className={cn('px-2 py-1 text-muted-foreground', shellTokens.sidebar.listRow)}
                >
                  {emptyLabel}
                </p>
              </li>
            ) : (
              decks.map((deck) => {
                const expanded = expandedDecks.includes(deck.slug);
                return (
                  <li key={deck.slug}>
                    <div className="flex items-center">
                      <Twisty
                        expanded={expanded}
                        label={`${expanded ? 'Collapse' : 'Expand'} ${deck.label}`}
                        onToggle={() => onToggleDeck(deck.slug)}
                      />
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
                    </div>
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
              })
            )}
          </ul>
        ) : null}
      </li>
    </ul>
  );
}
