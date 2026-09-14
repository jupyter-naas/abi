'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { DOCUMENTS_UPDATED_EVENT } from '@/stores/documents';
import { type DocumentsProjectTree } from '@/components/shell/sidebar/documents-tree';
import { createPersistedOpenState } from '@/lib/persisted-open-state';
import { sectionsComposerFiles } from './documents-composer-model';

const openState = createPersistedOpenState('nexus.chat.documentsFilesOpenBySlug');

type DocumentDiffFile = { path: string };
type DocumentDiffResponse = { base: string; head: string; files: DocumentDiffFile[] };

/**
 * Document-scoped "Files" container above the composer: same control as
 * Slides `FilesBlock`. Expands to files changed since this document was
 * opened (git diff against the branch tip seen on mount). Renders nothing
 * while that diff is empty. Sits between Suggestions and DocumentInfoBlock.
 */
export function DocumentsFilesBlock({
  slug,
  path,
  workspaceId,
}: {
  slug: string;
  path: string;
  workspaceId: string | null | undefined;
}) {
  const [open, setOpen] = useState(() => openState.load(slug));
  const [tree, setTree] = useState<DocumentsProjectTree | null>(null);
  const [changedPaths, setChangedPaths] = useState<Set<string> | null>(null);
  const baselineShaRef = useRef<string | null>(null);
  const files = useMemo(() => sectionsComposerFiles(tree, path), [tree, path]);
  const changedFiles = useMemo(
    () => (changedPaths ? files.filter((file) => changedPaths.has(file.path)) : []),
    [files, changedPaths],
  );

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
        `/api/documents/projects/${encodeURIComponent(slug)}/tree` +
          `?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) return;
      setTree((await res.json()) as DocumentsProjectTree);
    } catch {
      // Keep the open-document fallback. Do not invent a file list.
    }
  }, [workspaceId, slug]);

  const fetchDiff = useCallback(async () => {
    const base = baselineShaRef.current;
    if (!workspaceId || !slug || !base) return;
    try {
      const res = await authFetch(
        `/api/documents/projects/${encodeURIComponent(slug)}/history/diff` +
          `?workspace_id=${encodeURIComponent(workspaceId)}&base=${encodeURIComponent(base)}`,
      );
      if (!res.ok) return;
      const body = (await res.json()) as DocumentDiffResponse;
      setChangedPaths(new Set(body.files.map((file) => file.path)));
    } catch {
      // Leave the last known diff in place rather than guessing.
    }
  }, [workspaceId, slug]);

  const establishBaseline = useCallback(async () => {
    if (!workspaceId || !slug) return;
    try {
      const res = await authFetch(
        `/api/documents/projects/${encodeURIComponent(slug)}/history` +
          `?workspace_id=${encodeURIComponent(workspaceId)}&limit=1`,
      );
      if (!res.ok) return;
      const commits = (await res.json()) as { sha: string }[];
      baselineShaRef.current = commits[0]?.sha ?? null;
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
    const timers: number[] = [];
    const onUpdated = (event: Event) => {
      const updated = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      if (updated && updated !== slug) return;
      void fetchTree();
      void fetchDiff();
      timers.push(window.setTimeout(() => void fetchDiff(), 700));
      timers.push(window.setTimeout(() => void fetchDiff(), 2000));
    };
    window.addEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
    return () => {
      window.removeEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [fetchTree, fetchDiff, slug]);

  if (changedFiles.length === 0) return null;

  return (
    <div className="chat-composer-header-block border-x border-b border-border/50 first:rounded-t-2xl first:border-t">
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
        <ul className="chat-slides-composer-list chat-composer-header-list" aria-label="Changed document files">
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
