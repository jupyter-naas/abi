'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { SLIDES_DECK_UPDATED_EVENT } from '@/stores/slides';
import { type SlidesProjectTree } from '@/components/shell/sidebar/slides-tree';
import { createPersistedOpenState } from '@/lib/persisted-open-state';
import { slidesComposerFiles } from './slides-composer-model';

const openState = createPersistedOpenState('nexus.chat.filesOpenBySlug');

type DeckDiffFile = { path: string };
type DeckDiffResponse = { base: string; head: string; files: DeckDiffFile[] };

/**
 * Deck-scoped "Files" container above the composer: a single clickable
 * header that expands in place to reveal the files *changed since this deck
 * was opened* — a git diff against the branch tip seen on mount, not the
 * whole project tree. Renders nothing while that diff is empty (unknown
 * baseline included), rather than showing a "0 Files" row.
 */
export function FilesBlock({
  slug,
  path,
  workspaceId,
}: {
  slug: string;
  path: string;
  workspaceId: string | null | undefined;
}) {
  const [open, setOpen] = useState(() => openState.load(slug));
  const [tree, setTree] = useState<SlidesProjectTree | null>(null);
  const [changedPaths, setChangedPaths] = useState<Set<string> | null>(null);
  const baselineShaRef = useRef<string | null>(null);
  const files = useMemo(() => slidesComposerFiles(tree, path), [tree, path]);
  const changedFiles = useMemo(
    () => (changedPaths ? files.filter((file) => changedPaths.has(file.path)) : []),
    [files, changedPaths],
  );

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

  const fetchDiff = useCallback(async () => {
    const base = baselineShaRef.current;
    if (!workspaceId || !slug || !base) return;
    try {
      const res = await authFetch(
        `/api/slides/projects/${encodeURIComponent(slug)}/history/diff` +
          `?workspace_id=${encodeURIComponent(workspaceId)}&base=${encodeURIComponent(base)}`,
      );
      if (!res.ok) return;
      const body = (await res.json()) as DeckDiffResponse;
      setChangedPaths(new Set(body.files.map((file) => file.path)));
    } catch {
      // Leave the last known diff in place rather than guessing.
    }
  }, [workspaceId, slug]);

  const establishBaseline = useCallback(async () => {
    if (!workspaceId || !slug) return;
    try {
      const res = await authFetch(
        `/api/slides/projects/${encodeURIComponent(slug)}/history` +
          `?workspace_id=${encodeURIComponent(workspaceId)}&limit=1`,
      );
      if (!res.ok) return;
      const commits = (await res.json()) as { sha: string }[];
      baselineShaRef.current = commits[0]?.sha ?? null;
      // Nothing has committed since we just captured the tip: 0 changed files.
      setChangedPaths(new Set());
    } catch {
      // Leave changedPaths null; the header shows 0 until this succeeds.
    }
  }, [workspaceId, slug]);

  useEffect(() => {
    setTree(null);
    baselineShaRef.current = null;
    setChangedPaths(null);
    void fetchTree();
    void establishBaseline();
  }, [fetchTree, establishBaseline, slug]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const updated = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      if (updated && updated !== slug) return;
      void fetchTree();
      void fetchDiff();
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchTree, fetchDiff, slug]);

  if (changedFiles.length === 0) return null;

  return (
    <div className="chat-composer-header-block border-x border-b border-border/50">
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
        <span className="chat-composer-header-toggle-label">{changedFiles.length} Files</span>
      </button>
      {open && (
        <ul className="chat-slides-composer-list chat-composer-header-list" aria-label="Changed deck files">
          {changedFiles.map((file) => (
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
      )}
    </div>
  );
}
