/**
 * The workspace offer editor's model (`offer-editor.tsx`): what "<W> access" offers, the
 * toggles changed and not saved yet, and the changes a save sends. Pure.
 */
import {
  OFFER_KINDS,
  WHOLE_MODULE,
  type OfferChange,
  type OfferKind,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import type { PublishersView } from '@/lib/iam-admin/types';

/** A toggle changed, not saved: `${kind}|${module}|${name}` → offered. */
export type OfferDrafts = Record<string, boolean>;

export const draftKey = (kind: OfferKind, module: string, name: string) => `${kind}|${module}|${name}`;

function listed(offered: OfferState['offered'], kind: OfferKind, module: string, name: string): boolean {
  return (offered[kind] ?? []).some((item) => item.module === module && item.name === name);
}

/** Whether ``(module, name)`` is listed itself, the draft first. */
function explicit(offered: OfferState['offered'], kind: OfferKind, module: string, name: string, drafts: OfferDrafts): boolean {
  const draft = drafts[draftKey(kind, module, name)];
  return draft ?? listed(offered, kind, module, name);
}

/** Whether the module is offered whole (`<module>/*`). */
export function wholeModule(offered: OfferState['offered'], kind: OfferKind, module: string, drafts: OfferDrafts = {}): boolean {
  return explicit(offered, kind, module, WHOLE_MODULE, drafts);
}

/** Whether an item is offered: by its name, or with its whole module. */
export function isOffered(
  offered: OfferState['offered'],
  kind: OfferKind,
  module: string,
  name: string,
  drafts: OfferDrafts = {},
): boolean {
  return wholeModule(offered, kind, module, drafts) || explicit(offered, kind, module, name, drafts);
}

/** The changes a save sends: each toggle whose draft differs from what is listed. */
export function offerChanges(offered: OfferState['offered'], drafts: OfferDrafts): OfferChange[] {
  return Object.entries(drafts).flatMap(([key, value]) => {
    const [kind, module, name] = key.split('|') as [OfferKind, string, string];
    return listed(offered, kind, module, name) === value ? [] : [{ kind, module, name, offered: value }];
  });
}

/** A listed resource's id (`<module>/<name>`) as the offer names it. */
export function itemName(module: string, id: string): string {
  return id.startsWith(`${module}/`) ? id.slice(module.length + 1) : id;
}

export type OfferModule = {
  module: string;
  /** The kinds it has, as IAM publishes them (or as it is offered). */
  kinds: OfferKind[];
  /** IAM lets the caller give something of it here (`/publishers`). */
  grantable: boolean;
};

const KIND_OF_TYPE: Record<string, OfferKind> = Object.fromEntries(OFFER_KINDS.map((k) => [k.type, k.kind]));
const KIND_ORDER = OFFER_KINDS.map((k) => k.kind);

/** The modules of the editor, by name: those IAM lets the caller grant here (the module
 *  publishers' agent, app, workflow and pipeline types), and those already offered (to be taken
 *  back, even if the caller may grant nothing of them). */
export function modulesOf(publishers: PublishersView | null, offered: OfferState['offered']): OfferModule[] {
  const found = new Map<string, OfferModule>();
  for (const publisher of publishers?.publishers ?? []) {
    if (publisher.kind !== 'module') continue;
    const kinds = publisher.types
      .filter((t) => t.service === 'module' && KIND_OF_TYPE[t.type])
      .map((t) => KIND_OF_TYPE[t.type]);
    if (kinds.length) found.set(publisher.id, { module: publisher.id, kinds, grantable: true });
  }
  for (const kind of KIND_ORDER) {
    for (const item of offered[kind] ?? []) {
      const seen = found.get(item.module) ?? { module: item.module, kinds: [], grantable: false };
      if (!seen.kinds.includes(kind)) seen.kinds.push(kind);
      found.set(item.module, seen);
    }
  }
  return [...found.values()]
    .map((m) => ({ ...m, kinds: KIND_ORDER.filter((k) => m.kinds.includes(k)) }))
    .sort((a, b) => a.module.localeCompare(b.module));
}

/** A feature row as General answers it: offered to the workspace (Everyone) or not. */
export type FeatureToggleRow = { key: string; choice: 'everyone' | 'only' | 'nobody' };
export type FeatureToggleChange = { feature: string; choice: 'everyone' | 'nobody' };

/** The feature changes a save sends: on is Everyone, off is Nobody. */
export function featureChanges(rows: FeatureToggleRow[], drafts: Record<string, boolean>): FeatureToggleChange[] {
  return rows.flatMap((row) => {
    const draft = drafts[row.key];
    if (draft === undefined || draft === (row.choice === 'everyone')) return [];
    return [{ feature: row.key, choice: draft ? 'everyone' : 'nobody' }];
  });
}

/** How many toggles a save would send. */
export function unsavedCount(
  offered: OfferState['offered'],
  drafts: OfferDrafts,
  features: FeatureToggleRow[],
  featureDrafts: Record<string, boolean>,
): number {
  return offerChanges(offered, drafts).length + featureChanges(features, featureDrafts).length;
}

/** The listed items, and those offered by name that the listing missed (so they can be taken
 *  back), by label. */
export function itemsWithOffered(
  listed: { name: string; label: string }[],
  offered: { module: string; name: string }[],
  module: string,
): { name: string; label: string }[] {
  const found = new Map(listed.map((i) => [i.name, i]));
  for (const item of offered) {
    if (item.module === module && item.name !== WHOLE_MODULE && !found.has(item.name)) {
      found.set(item.name, { name: item.name, label: item.name });
    }
  }
  return [...found.values()].sort((a, b) => a.label.localeCompare(b.label));
}
