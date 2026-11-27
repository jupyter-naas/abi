'use client';

import Link from 'next/link';
import { officeCardHref, type OfficeCard } from './office-card';
import type { OfficeKind } from './office-kinds';

/** Openable document, workbook or deck produced by Abi during a chat turn. */
export function OfficeCardView({
  kind,
  card,
  currentWorkspaceId,
  store,
}: {
  kind: Pick<OfficeKind, 'id' | 'icon' | 'card'>;
  card: OfficeCard;
  currentWorkspaceId: string;
  /** The kind's store: opening selects the item Abi just built, not whatever was last selected. */
  store: {
    getState: () => {
      setSelectedSlug: (slug: string | null) => void;
      setSelectedTitle: (title: string | null) => void;
    };
  };
}) {
  const Icon = kind.icon;
  return (
    <Link
      href={officeCardHref(kind.id, card, currentWorkspaceId)}
      data-testid={kind.card.testId}
      data-slug={card.slug}
      onClick={() => {
        store.getState().setSelectedSlug(card.slug);
        store.getState().setSelectedTitle(card.title);
      }}
      className="mt-3 flex max-w-md items-center gap-3 rounded-lg border border-border bg-muted/40 p-3 no-underline transition-colors hover:bg-muted"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-background">
        <Icon className="h-5 w-5 text-muted-foreground" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{card.title}</span>
        <span className="block text-xs text-muted-foreground">{kind.card.blurb}</span>
      </span>
    </Link>
  );
}
