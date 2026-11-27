/**
 * Settings › Access › Modules: what the workspace offers of each module, one row per module (its
 * contents, agents, apps, workflows or pipelines, unfolded under it, each kind then item by item),
 * as the Users table shows it. Pure: the view is
 * `modules.tsx`; the offer is "<W> access" (`GET /api/workspaces/{id}/offer`), each change one
 * write of it as the caller (`PUT …/offer`).
 */
import { draftKey, modulesOf } from '@/components/access/offer/offer-model';
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

// -- one row per module ----------------------------------------------------------------------

export type ModuleGroupOffer = 'whole' | 'partial' | 'none';
export const MODULE_GROUP_LABELS: Record<ModuleGroupOffer, string> = {
  whole: 'Whole module',
  partial: 'In part',
  none: 'Not offered',
};

/** A module and its contents: one row of the table, its kinds unfolded under it. */
export type ModuleGroup = {
  /** The module. */
  key: string;
  module: string;
  kinds: ModuleRow[];
  /** Every kind offered whole, some of it, or nothing. */
  offer: ModuleGroupOffer;
  /** IAM lets the caller give something of it here. */
  grantable: boolean;
};

export function moduleGroups(publishers: PublishersView | null, offered: OfferState['offered']): ModuleGroup[] {
  const groups = new Map<string, ModuleGroup>();
  for (const row of moduleRows(publishers, offered)) {
    const group = groups.get(row.module) ?? { key: row.module, module: row.module, kinds: [], offer: 'none', grantable: false };
    group.kinds.push(row);
    group.grantable = group.grantable || row.grantable;
    groups.set(row.module, group);
  }
  for (const group of groups.values()) {
    group.offer = group.kinds.every((k) => k.offer === 'whole')
      ? 'whole'
      : group.kinds.some((k) => k.offer !== 'none')
        ? 'partial'
        : 'none';
  }
  return [...groups.values()];
}

/** "Whole module", "Agents: whole · Apps: 2 items", "Not offered". */
export function groupSummary(group: ModuleGroup): string {
  if (group.offer !== 'partial') return MODULE_GROUP_LABELS[group.offer];
  return group.kinds
    .filter((k) => k.offer !== 'none')
    .map((k) => `${k.kindLabel}: ${k.offer === 'whole' ? 'whole' : `${k.items.length} item${k.items.length === 1 ? '' : 's'}`}`)
    .join(' · ');
}

/** What the module's switch writes: every kind whole (on), or nothing of it left (off). */
export function moduleDrafts(group: ModuleGroup, on: boolean): Record<string, boolean> {
  const drafts: Record<string, boolean> = {};
  for (const kind of group.kinds) {
    drafts[draftKey(kind.kind, group.module, WHOLE_MODULE)] = on;
    if (!on) for (const item of kind.items) drafts[draftKey(kind.kind, group.module, item)] = false;
  }
  return drafts;
}

export function groupCellValues(group: ModuleGroup, column: ModuleColumnId): string[] {
  if (column === 'module') return [group.module];
  if (column === 'kind') return group.kinds.map((k) => k.kindLabel);
  return [MODULE_GROUP_LABELS[group.offer]];
}

export function groupSearchTexts(group: ModuleGroup): string[] {
  return [group.module, MODULE_GROUP_LABELS[group.offer], ...group.kinds.flatMap(moduleSearchTexts)];
}
