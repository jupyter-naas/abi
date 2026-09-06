'use client';

import Link from 'next/link';
import { Presentation } from 'lucide-react';
import { slidesDeckHref, type SlidesDeckCard } from './slides-deck-card';
import { useSlidesStore } from '@/stores/slides';

/** Openable deck produced by Abi during a chat turn. */
export function SlidesDeckCardView({
  card,
  currentWorkspaceId,
}: {
  card: SlidesDeckCard;
  currentWorkspaceId: string;
}) {
  return (
    <Link
      href={slidesDeckHref(card, currentWorkspaceId)}
      data-testid="slides-deck-card"
      data-slug={card.slug}
      onClick={() => {
        // Open the deck Abi just built, not whatever was last selected.
        useSlidesStore.getState().setSelectedSlug(card.slug);
        useSlidesStore.getState().setSelectedTitle(card.title);
      }}
      className="mt-3 flex max-w-md items-center gap-3 rounded-lg border border-border bg-muted/40 p-3 no-underline transition-colors hover:bg-muted"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-background">
        <Presentation className="h-5 w-5 text-muted-foreground" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">
          {card.title}
        </span>
        <span className="block text-xs text-muted-foreground">
          Presentation. Open in Slides to view and export PPTX.
        </span>
      </span>
    </Link>
  );
}
