'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { SLIDES_DECK_UPDATED_EVENT } from '@/stores/slides';
import { type SlidesProjectTree } from '@/components/shell/sidebar/slides-tree';
import { createPersistedOpenState } from '@/lib/persisted-open-state';
import { slidesComposerFiles } from './slides-composer-model';

const openState = createPersistedOpenState('nexus.chat.filesOpenBySlug');

/**
 * Deck-scoped "Files" container above the composer: a single clickable
 * header that expands in place to reveal the deck's file list. Can stack
 * with `SuggestionsBlock` (Files below Suggestions) and sits flush on the
 * composer input box below the stack — shared border, no gap — via
 * `.chat-composer-header-block` in chat-agent-selector.css.
 */
export function FilesBlock({
  slug,
  path,
  workspaceId,
  topmost = false,
}: {
  slug: string;
  path: string;
  workspaceId: string | null | undefined;
  /** Whether this is the first block in the stack (gets the top border/radius). */
  topmost?: boolean;
}) {
  const [open, setOpen] = useState(() => openState.load(slug));
  const [tree, setTree] = useState<SlidesProjectTree | null>(null);
  const files = useMemo(() => slidesComposerFiles(tree, path), [tree, path]);

  // Restore the remembered state whenever the deck underneath it changes.
  useEffect(() => {
    setOpen(openState.load(slug));
  }, [slug]);

  const toggleOpen = () => {
    setOpen((value) => {
      const next = !value;
      openState.save(slug, next);
      return next;
    });
  };

  const fetchTree = useCallback(async () => {
    if (!workspaceId || !slug) return;
    try {
      const res = await authFetch(
        `/api/slides/projects/${encodeURIComponent(slug)}/tree` +
          `?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) return;
      setTree((await res.json()) as SlidesProjectTree);
    } catch {
      // Keep the open-deck fallback. Do not invent a file list.
    }
  }, [workspaceId, slug]);

  useEffect(() => {
    setTree(null);
    void fetchTree();
  }, [fetchTree, slug]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const updated = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      if (updated && updated !== slug) return;
      void fetchTree();
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchTree, slug]);

  return (
    <div
      className={cn(
        'chat-composer-header-block border-x border-b border-border/50',
        topmost && 'rounded-t-2xl border-t',
      )}
    >
      <button
        type="button"
        className="chat-composer-header-toggle"
        aria-expanded={open}
        onClick={toggleOpen}
      >
        <ChevronRight
          size={12}
          className={cn('chat-composer-header-toggle-chevron shrink-0', open && 'is-open')}
        />
        <span className="chat-composer-header-toggle-label">{files.length} Files</span>
      </button>
      {open &&
        (files.length > 0 ? (
          <ul className="chat-slides-composer-list chat-composer-header-list" aria-label="Deck files">
            {files.map((file) => (
              <li
                key={file.path}
                className={cn('chat-slides-composer-row is-static', file.open && 'is-open')}
                title={file.path}
              >
                <span className="chat-slides-composer-row-text">
                  <span className="chat-slides-composer-row-name">{file.name}</span>
                  <span className="chat-slides-composer-row-hint">{file.path}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="chat-slides-composer-empty">No files listed for this deck</p>
        ))}
    </div>
  );
}
