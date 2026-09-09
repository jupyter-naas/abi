'use client';

import { useEffect, useState } from 'react';
import { Presentation } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { SLIDES_DECK_UPDATED_EVENT } from '@/stores/slides';

type DeckVersionResponse = { version: string; commit_count: number };

/**
 * Deck identity strip above the composer, Slides only: the presentation's
 * folder name plus a 0.x semver derived from its Conventional Commits
 * history (see the backend's `_semver_from_commits`). Static info, not
 * collapsible like Suggestions/Files — always the first block in the stack
 * so it always owns the top border/radius.
 */
export function PresentationInfoBlock({
  slug,
  title,
  workspaceId,
}: {
  slug: string;
  title: string;
  workspaceId: string | null | undefined;
}) {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId || !slug) return;
    let cancelled = false;
    const fetchVersion = async () => {
      try {
        const res = await authFetch(
          `/api/slides/projects/${encodeURIComponent(slug)}/version` +
            `?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as DeckVersionResponse;
        if (!cancelled) setVersion(body.version);
      } catch {
        // Leave version as-is; the strip just omits it until this succeeds.
      }
    };
    setVersion(null);
    void fetchVersion();
    const onUpdated = (event: Event) => {
      const updated = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      if (updated && updated !== slug) return;
      void fetchVersion();
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => {
      cancelled = true;
      window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    };
  }, [workspaceId, slug]);

  return (
    <div className="chat-composer-header-block chat-composer-info-row rounded-t-2xl border-x border-t border-b border-border/50">
      <Presentation size={12} className="shrink-0 text-muted-foreground" />
      <span
        className="chat-composer-header-toggle-label chat-composer-info-text"
        title={version ? `${title} · v${version}` : title}
      >
        <span className="chat-composer-info-name">{title}</span>
        {version && <span className="chat-composer-info-version">v{version}</span>}
      </span>
    </div>
  );
}
