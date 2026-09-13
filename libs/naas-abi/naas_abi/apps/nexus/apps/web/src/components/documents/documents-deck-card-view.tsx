'use client';

import Link from 'next/link';
import { FileText } from 'lucide-react';
import { sectionsDocumentHref, type DocumentsCard } from './documents-card';
import { useDocumentsStore } from '@/stores/documents';

/** Openable document produced by Abi during a chat turn. */
export function DocumentsCardView({
  card,
  currentWorkspaceId,
}: {
  card: DocumentsCard;
  currentWorkspaceId: string;
}) {
  return (
    <Link
      href={sectionsDocumentHref(card, currentWorkspaceId)}
      data-testid="documents-card"
      data-slug={card.slug}
      onClick={() => {
        // Open the document Abi just built, not whatever was last selected.
        useDocumentsStore.getState().setSelectedSlug(card.slug);
        useDocumentsStore.getState().setSelectedTitle(card.title);
      }}
      className="mt-3 flex max-w-md items-center gap-3 rounded-lg border border-border bg-muted/40 p-3 no-underline transition-colors hover:bg-muted"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-background">
        <FileText className="h-5 w-5 text-muted-foreground" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">
          {card.title}
        </span>
        <span className="block text-xs text-muted-foreground">
          Document. Open in Documents to view and export PDF.
        </span>
      </span>
    </Link>
  );
}
