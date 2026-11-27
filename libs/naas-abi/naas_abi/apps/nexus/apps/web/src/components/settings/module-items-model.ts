/**
 * The items the workspace's modules bring to a page under Features (Agents, Apps, Workflows),
 * offered or not, as Access › Modules lists them: the modules IAM lets the caller give here, and
 * those already offered, each one's items as IAM lists them. Each is enabled when the policy
 * picked offers it (by name, or with its whole module). Pure: the hook is `use-module-items.ts`.
 */
import {
  draftKey,
  isOffered,
  itemsWithOffered,
  modulesOf,
  offerChanges,
  wholeModule,
  type OfferDrafts,
} from '@/components/access/offer/offer-model';
import { WHOLE_MODULE, type OfferChange, type OfferKind, type OfferState } from '@/lib/access-model/workspace-offer';
import type { PublishersView } from '@/lib/iam-admin/types';

/** An item of a module: an agent, an app, a workflow or a pipeline. */
export type ModuleItem = {
  kind: OfferKind;
  module: string;
  /** The name the offer gives it. */
  name: string;
  label: string;
  /** Offered by the policy picked: by name, or with its whole module. */
  offered: boolean;
  /** IAM lets the caller give its module here (else it may only be taken back). */
  grantable: boolean;
};

/** A module's kind to list the items of. */
export type CatalogModule = { kind: OfferKind; module: string; grantable: boolean };

/** A module's kind and the items IAM lists of it. */
export type CatalogListing = CatalogModule & { items: { name: string; label: string }[] };

/** `${kind}|${module}|${name}`: a row's key for a batch change. */
export const moduleItemKey = (item: Pick<ModuleItem, 'kind' | 'module' | 'name'>) =>
  draftKey(item.kind, item.module, item.name);

/** What the Enabled column says of an item. */
export const enabledLabel = (item: Pick<ModuleItem, 'offered'> | null): 'Enabled' | 'Disabled' =>
  !item || item.offered ? 'Enabled' : 'Disabled';

/** The modules (and kinds among `kinds`) whose items a page lists, by module. */
export function catalogModules(
  publishers: PublishersView | null,
  offered: OfferState['offered'],
  kinds: readonly OfferKind[],
): CatalogModule[] {
  return modulesOf(publishers, offered).flatMap(({ module, kinds: has, grantable }) =>
    has.filter((kind) => kinds.includes(kind)).map((kind) => ({ kind, module, grantable })),
  );
}

/** Every item listed, and those offered by name the listing missed, each enabled or not. */
export function catalogItems(listings: readonly CatalogListing[], offered: OfferState['offered']): ModuleItem[] {
  return listings.flatMap(({ kind, module, grantable, items }) =>
    itemsWithOffered(items, offered[kind] ?? [], module).map((item) => ({
      kind,
      module,
      name: item.name,
      label: item.label,
      offered: isOffered(offered, kind, module, item.name),
      grantable,
    })),
  );
}

/**
 * The changes that enable (`on`) or disable `targets`, in one save. An item of a module offered
 * whole is enabled: disabling it turns that module (that kind) into item by item, its whole entry
 * taken back and every other item of it (`catalog`) offered by name. What is already so is left out.
 */
export function enabledChanges(
  offered: OfferState['offered'],
  catalog: readonly ModuleItem[],
  targets: readonly ModuleItem[],
  on: boolean,
): OfferChange[] {
  const drafts: OfferDrafts = {};
  if (!on) {
    const off = new Set(targets.map(moduleItemKey));
    for (const target of targets) {
      const whole = draftKey(target.kind, target.module, WHOLE_MODULE);
      if (whole in drafts || !wholeModule(offered, target.kind, target.module)) continue;
      drafts[whole] = false;
      for (const other of catalog) {
        if (other.kind === target.kind && other.module === target.module && !off.has(moduleItemKey(other))) {
          drafts[moduleItemKey(other)] = true;
        }
      }
    }
  }
  for (const target of targets) {
    if (on && isOffered(offered, target.kind, target.module, target.name)) continue;
    drafts[moduleItemKey(target)] = on;
  }
  return offerChanges(offered, drafts);
}
