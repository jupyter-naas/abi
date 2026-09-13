'use client';

import { useEffect, useState } from 'react';
import { CheckCircle2, ChevronRight, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { DOCUMENTS_UPDATED_EVENT } from '@/stores/documents';
import { createPersistedOpenState } from '@/lib/persisted-open-state';

type DocumentVersionResponse = { version: string; commit_count: number };
type DocumentCommit = {
  sha: string;
  message: string;
  author: string;
  date: string | null;
  version: string;
};

// There is no version-validation feature yet (e.g. a QA agent sign-off), so
// the tag always reads as validated. Once one exists, thread a real
// `validated: boolean` through here and swap CheckCircle2 for CircleX.
const VERSION_VALIDATED = true;

const HISTORY_LIMIT = 20;

const openState = createPersistedOpenState('nexus.chat.documentInfoOpenBySlug');

function formatCommitTimestamp(date: string | null): string | null {
  if (!date) return null;
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return null;
  const pad = (n: number) => String(n).padStart(2, '0');
  const time = `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`;
  const day = `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`;
  return `${time} ${day}`;
}

/**
 * Document identity strip above the composer, Documents only: the document's
 * folder name plus a 0.x semver derived from its Conventional Commits
 * history (see the backend's `_semver_from_commits`). Same control as
 * `PresentationInfoBlock` on Slides. A clickable header like
 * Suggestions/Files that expands in place to the commit log behind that
 * version, always the last block in the stack, directly touching the
 * composer input box.
 */
export function DocumentInfoBlock({
  slug,
  title,
  workspaceId,
}: {
  slug: string;
  title: string;
  workspaceId: string | null | undefined;
}) {
  const [version, setVersion] = useState<string | null>(null);
  const [commits, setCommits] = useState<DocumentCommit[]>([]);
  const [open, setOpen] = useState(() => openState.load(slug));

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

  useEffect(() => {
    if (!workspaceId || !slug) return;
    let cancelled = false;
    const fetchVersion = async () => {
      try {
        const res = await authFetch(
          `/api/documents/projects/${encodeURIComponent(slug)}/version` +
            `?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as DocumentVersionResponse;
        if (!cancelled) setVersion(body.version);
      } catch {
        // Leave version as-is; the strip just omits it until this succeeds.
      }
    };
    const fetchHistory = async () => {
      try {
        const res = await authFetch(
          `/api/documents/projects/${encodeURIComponent(slug)}/history` +
            `?workspace_id=${encodeURIComponent(workspaceId)}&limit=${HISTORY_LIMIT}`,
        );
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as DocumentCommit[];
        if (!cancelled) setCommits(body);
      } catch {
        // Leave the last known history in place rather than guessing.
      }
    };
    setVersion(null);
    setCommits([]);
    void fetchVersion();
    void fetchHistory();
    const timers: number[] = [];
    const onUpdated = (event: Event) => {
      const updated = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      if (updated && updated !== slug) return;
      void fetchVersion();
      void fetchHistory();
      // The git backend's commit-log read can lag the write that triggered
      // this event by a beat; reconcile once more so the pill/log don't stay
      // on the pre-edit version.
      timers.push(
        window.setTimeout(() => {
          void fetchVersion();
          void fetchHistory();
        }, 1000),
      );
    };
    window.addEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
    return () => {
      cancelled = true;
      window.removeEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [workspaceId, slug]);

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
        <FileText size={12} className="shrink-0 text-muted-foreground" />
        <span
          className="chat-composer-header-toggle-label chat-composer-info-name"
          title={title}
        >
          {title}
        </span>
        {version && (
          <span
            className="chat-composer-header-toggle-label chat-composer-info-version-tag"
            title={VERSION_VALIDATED ? 'Version validated' : 'Version not validated'}
          >
            <CheckCircle2 size={10} className="shrink-0 text-emerald-500" />
            v{version}
          </span>
        )}
      </button>
      {open && commits.length > 0 && (
        <ul className="chat-slides-composer-list chat-composer-header-list" aria-label="Version history">
          {commits.map((commit) => {
            const message = commit.message.split('\n')[0] || commit.message;
            const timestamp = formatCommitTimestamp(commit.date);
            const hint = [timestamp, commit.author, `v${commit.version}`]
              .filter(Boolean)
              .join(' · ');
            return (
              <li key={commit.sha} className="chat-slides-composer-row is-static" title={commit.message}>
                <span className="chat-slides-composer-row-text">
                  <span className="chat-slides-composer-row-name">{message}</span>
                  {hint && <span className="chat-slides-composer-row-hint">{hint}</span>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
