import { FileText, Presentation, Table2, type LucideIcon } from 'lucide-react';

/**
 * Documents, Sheets and Slides are one product in three kinds: a git project per item,
 * one HTML file the pane edits, a gallery, a sidebar tree. Everything that differs
 * between them is here; the shared tree, gallery, menu, status bar and cover read it.
 */
export type OfficeKindId = 'documents' | 'sheets' | 'slides';

/** Template colours a cover falls back to before the item's HTML loads. */
export type OfficeTemplatePreview = {
  preview_bg: string;
  preview_panel: string;
  preview_accent: string;
  preview_ink: string;
};

export type OfficeKind = {
  /** Route segment (`/workspace/{id}/documents`), API base (`/api/documents`) and test id prefix of the tree. */
  id: OfficeKindId;
  /** Test id prefix the gallery, menus and rename fields have always used. */
  testIdPrefix: 'sections' | 'sheets' | 'slides';
  /** One item, lower case: what the status bar calls it, and its API path under `/projects/{slug}/`. */
  noun: 'document' | 'workbook' | 'deck';
  /** The file the pane edits; it routes to the item from the tree. */
  fileName: string;
  /** Test id of an item row in the sidebar tree. */
  itemTestId: string;
  icon: LucideIcon;
  /** The sidebar's root folder: the real directory the items live in. */
  treeRootLabel: string;
  allRowLabel: string;
  emptyLabel: string;
  archivedEmptyLabel: string;
  /** Gallery strip heading. */
  startLabel: string;
  /** Cover and template card shape: a letter page or a 16:9 stage. */
  aspectClass: string;
  /** Test id of one in-memory thumb (section, sheet tab, slide). */
  partThumbTestId: string;
  /** The seed field listing a template's parts (sections, sheet tabs, slides). */
  templateParts: 'sections' | 'sheets' | 'slides';
  /** Chat card that opens an item Abi built. */
  card: { testId: string; blurb: string };
};

export const DOCUMENTS_KIND: OfficeKind = {
  id: 'documents',
  testIdPrefix: 'sections',
  noun: 'document',
  fileName: 'document.html',
  itemTestId: 'documents-tree-document',
  icon: FileText,
  treeRootLabel: 'documents',
  allRowLabel: 'All documents',
  emptyLabel: 'No documents yet',
  archivedEmptyLabel: 'No archived documents',
  startLabel: 'Start a new document',
  aspectClass: 'aspect-[8.5/11]',
  partThumbTestId: 'sections-section-thumb',
  templateParts: 'sections',
  card: { testId: 'documents-card', blurb: 'Document. Open in Documents to view and export PDF.' },
};

export const SHEETS_KIND: OfficeKind = {
  id: 'sheets',
  testIdPrefix: 'sheets',
  noun: 'workbook',
  fileName: 'workbook.html',
  itemTestId: 'sheets-tree-workbook',
  icon: Table2,
  treeRootLabel: 'sheets',
  allRowLabel: 'All sheets',
  emptyLabel: 'No workbooks yet',
  archivedEmptyLabel: 'No archived workbooks',
  startLabel: 'Start a new workbook',
  aspectClass: 'aspect-video',
  partThumbTestId: 'sheets-tab-thumb',
  templateParts: 'sheets',
  card: { testId: 'sheets-workbook-card', blurb: 'Workbook. Open in Sheets to edit tabs and export XLSX.' },
};

export const SLIDES_KIND: OfficeKind = {
  id: 'slides',
  testIdPrefix: 'slides',
  noun: 'deck',
  fileName: 'deck.html',
  itemTestId: 'slides-tree-deck',
  icon: Presentation,
  treeRootLabel: 'slides',
  allRowLabel: 'All slides',
  emptyLabel: 'No presentations yet',
  archivedEmptyLabel: 'No archived presentations',
  startLabel: 'Start a new presentation',
  aspectClass: 'aspect-video',
  partThumbTestId: 'slides-slide-thumb',
  templateParts: 'slides',
  card: { testId: 'slides-deck-card', blurb: 'Presentation. Open in Slides to view and export PPTX.' },
};

export const OFFICE_KINDS = [DOCUMENTS_KIND, SHEETS_KIND, SLIDES_KIND] as const;

/** In-app route of one item. */
export function officeItemHref(kind: Pick<OfficeKind, 'id'>, workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/${kind.id}/${encodeURIComponent(slug)}`;
}
