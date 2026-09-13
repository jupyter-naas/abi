'use client';

import Link from 'next/link';
import { Table2 } from 'lucide-react';
import { sheetsWorkbookHref, type SheetsWorkbookCard } from './sheets-deck-card';
import { useSheetsStore } from '@/stores/sheets';

/** Openable workbook produced by Abi during a chat turn. */
export function SheetsWorkbookCardView({
  card,
  currentWorkspaceId,
}: {
  card: SheetsWorkbookCard;
  currentWorkspaceId: string;
}) {
  return (
    <Link
      href={sheetsWorkbookHref(card, currentWorkspaceId)}
      data-testid="sheets-workbook-card"
      data-slug={card.slug}
      onClick={() => {
        // Open the workbook Abi just built, not whatever was last selected.
        useSheetsStore.getState().setSelectedSlug(card.slug);
        useSheetsStore.getState().setSelectedTitle(card.title);
      }}
      className="mt-3 flex max-w-md items-center gap-3 rounded-lg border border-border bg-muted/40 p-3 no-underline transition-colors hover:bg-muted"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-background">
        <Table2 className="h-5 w-5 text-muted-foreground" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">
          {card.title}
        </span>
        <span className="block text-xs text-muted-foreground">
          Workbook. Open in Sheets to edit tabs and export XLSX.
        </span>
      </span>
    </Link>
  );
}
