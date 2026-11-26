/**
 * Settings › Access › Modules: what the workspace offers of each module, one row per module and
 * kind (its agents, apps, workflows or pipelines), as the Users table shows it. Pure: the view is
 * `modules.tsx`; the offer is "<W> access" (`GET /api/workspaces/{id}/offer`), each change one
 * write of it as the caller (`PUT …/offer`).
 */
import { modulesOf } from '@/components/access/offer/offer-model';
import {
  OFFER_KINDS,
  WHOLE_MODULE,
  type OfferKind,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import type { PublishersView } from '@/lib/iam-admin/types';

export type ModuleOffer = 'whole' | 'items' | 'none';
export const MODULE_OFFER_LABELS: Record<ModuleOffer, string> = {
  whole: 'Whole module',
  items: 'Item by item',
  none: 'Not offered',
};

export type ModuleRow = {
  /** `${kind}|${module}`. */
  key: string;
  module: string;
  kind: OfferKind;
  kindLabel: string;
  offer: ModuleOffer;
  /** The items offered by name (not with the whole module). */
  items: string[];
  /** IAM lets the caller give something of it here. */
  grantable: boolean;
};

const KIND_LABELS = Object.fromEntries(OFFER_KINDS.map((k) => [k.kind, k.label])) as Record<OfferKind, string>;

/** One row per module and kind: those IAM lets the caller give here, and those already offered. */
export function moduleRows(publishers: PublishersView | null, offered: OfferState['offered']): ModuleRow[] {
  return modulesOf(publishers, offered).flatMap(({ module, kinds, grantable }) =>
    kinds.map((kind) => {
      const listed = (offered[kind] ?? []).filter((item) => item.module === module);
      const whole = listed.some((item) => item.name === WHOLE_MODULE);
      const items = listed.filter((item) => item.name !== WHOLE_MODULE).map((item) => item.name).sort();
      return {
        key: `${kind}|${module}`,
        module,
        kind,
        kindLabel: KIND_LABELS[kind],
        offer: whole ? 'whole' : items.length ? 'items' : 'none',
        items,
        grantable,
      } satisfies ModuleRow;
    })
  );
}

export type ModuleColumnId = 'module' | 'kind' | 'offer';
export const MODULE_COLUMNS: { id: ModuleColumnId; label: string }[] = [
  { id: 'module', label: 'Module' },
  { id: 'kind', label: 'Contents' },
  { id: 'offer', label: 'Offered' },
];

export function moduleCellValues(row: ModuleRow, column: ModuleColumnId): string[] {
  if (column === 'module') return [row.module];
  if (column === 'kind') return [row.kindLabel];
  return [MODULE_OFFER_LABELS[row.offer]];
}

export function moduleSearchTexts(row: ModuleRow): string[] {
  return [row.module, row.kindLabel, MODULE_OFFER_LABELS[row.offer], ...row.items];
}

/** "Whole module", "2 items: Coach, Recruiter", "Not offered". */
export function offerSummary(row: ModuleRow): string {
  if (row.offer !== 'items') return MODULE_OFFER_LABELS[row.offer];
  return `${row.items.length} item${row.items.length === 1 ? '' : 's'}: ${row.items.join(', ')}`;
}

export const MODULE_EXPORT_HEADERS = ['Module', 'Contents', 'Offered', 'Items'];
export function moduleExportRow(row: ModuleRow): string[] {
  return [row.module, row.kindLabel, MODULE_OFFER_LABELS[row.offer], row.items.join('; ')];
}
