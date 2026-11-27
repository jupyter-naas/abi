'use client';

/**
 * Every item the workspace's modules bring of some kinds (Agents; Apps; Workflows and Pipelines),
 * offered or not by the policy picked in the Settings column (`?policy=`, "<W> access" by
 * default), and the save that enables or disables them, as Access › Modules reads and writes them:
 * the offer (`createOfferApi`), the modules IAM lets the caller give (`publishers`) and each one's
 * items (`resources`). A table of switches: each change is one save, and said (`notice`).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { itemName } from '@/components/access/offer/offer-model';
import { reloadWorkspaceResources } from '@/hooks/use-workspace-resources';
import {
  OFFER_KINDS,
  createOfferApi,
  type OfferApi,
  type OfferChange,
  type OfferKind,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import { isOrgTarget } from '@/lib/access-model/target';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import {
  catalogItems,
  catalogModules,
  enabledChanges,
  moduleItemKey,
  type CatalogListing,
  type ModuleItem,
} from './module-items-model';

const DEFAULT_OFFER_API = createOfferApi();
const DEFAULT_IAM_API = createIamAdminApi();
/** Items a page of the listing, as Access › Modules; its next pages are read too, up to `MAX_PAGES`. */
const ITEM_LIMIT = 200;
const MAX_PAGES = 10;

const message = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

/** Whether the state read is "<W> access", the workspace's offer (not another policy of it). */
const editsOffer = (state: OfferState | null) =>
  !state?.policy || !state.access_policy || state.policy.id === state.access_policy.id;

async function listItems(api: IamAdminApi, scope: string, kind: OfferKind, module: string) {
  const type = OFFER_KINDS.find((k) => k.kind === kind)!.type;
  const items: { name: string; label: string }[] = [];
  let cursor: string | null = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const found = await api.resources({ scope, service: 'module', type, module, cursor, limit: ITEM_LIMIT });
    for (const item of found.items) {
      const name = itemName(module, item.id);
      items.push({ name, label: item.label || name });
    }
    if (!found.next_cursor) break;
    cursor = found.next_cursor;
  }
  return items;
}

export type ModuleItems = {
  /** Every item of the kinds asked, by module. */
  items: ModuleItem[];
  /** By `moduleItemKey`. */
  byKey: ReadonlyMap<string, ModuleItem>;
  /** The policy read. */
  offer: OfferState | null;
  /** The items are read (or could not be). */
  ready: boolean;
  /** IAM lets the caller change the policy read. */
  editable: boolean;
  saving: boolean;
  error: string;
  /** What the last save did. */
  notice: string;
  /** One save of `changes`, then `done` said. */
  save: (changes: OfferChange[], done: string) => Promise<void>;
  /** Enable (`on`) or disable `targets` in one save, then `done(count)` said: how many changed. */
  setEnabled: (targets: readonly ModuleItem[], on: boolean, done: (count: number) => string) => Promise<void>;
};

export function useModuleItems({
  workspaceId,
  policyId = null,
  kinds,
  generation = 0,
  onSaved,
  offerApi = DEFAULT_OFFER_API,
  iamApi = DEFAULT_IAM_API,
}: {
  workspaceId: string | null | undefined;
  /** The policy picked in the Settings column; "<W> access" when null. */
  policyId?: string | null;
  kinds: readonly OfferKind[];
  /** Read again when it changes (the Settings' Reload). */
  generation?: number;
  /** After a save: the page reads its own list again (what the caller may use changed). */
  onSaved?: () => void;
  offerApi?: OfferApi;
  iamApi?: IamAdminApi;
}): ModuleItems {
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [listings, setListings] = useState<CatalogListing[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const kindsKey = kinds.join(',');

  useEffect(() => {
    let live = true;
    setOffer(null);
    setListings(null);
    setError('');
    setNotice('');
    if (!workspaceId) return;
    void (async () => {
      try {
        const read = await offerApi.read(workspaceId, policyId);
        const publishers = await iamApi.publishers(read.scope).catch(() => null);
        const wanted = catalogModules(publishers, read.offered, kindsKey.split(',') as OfferKind[]);
        const failed: string[] = [];
        const found = await Promise.all(
          wanted.map(async (module) => {
            try {
              return { ...module, items: await listItems(iamApi, read.scope, module.kind, module.module) };
            } catch (e) {
              failed.push(message(e, `Could not list the items of ${module.module}.`));
              return { ...module, items: [] };
            }
          }),
        );
        if (!live) return;
        setOffer(read);
        setListings(found);
        if (failed.length > 0) setError(failed[0]);
      } catch (e) {
        if (!live) return;
        setListings([]);
        setError(message(e, 'Could not read what this workspace offers.'));
      }
    })();
    return () => {
      live = false;
    };
  }, [offerApi, iamApi, workspaceId, policyId, kindsKey, generation]);

  const items = useMemo(() => (offer && listings ? catalogItems(listings, offer.offered) : []), [offer, listings]);
  const byKey = useMemo(() => new Map(items.map((item) => [moduleItemKey(item), item])), [items]);

  const save = useCallback(
    async (changes: OfferChange[], done: string) => {
      if (!workspaceId) return;
      if (changes.length === 0) {
        setNotice(done);
        return;
      }
      setSaving(true);
      setNotice('');
      try {
        const next = await offerApi.save(workspaceId, changes, policyId);
        setOffer(next);
        setError('');
        setNotice(done);
        // The nav and the pages under Features follow what is offered.
        if (editsOffer(next) && !isOrgTarget(workspaceId)) void reloadWorkspaceResources(workspaceId);
        onSaved?.();
      } catch (e) {
        setError(message(e, 'Could not save.'));
      } finally {
        setSaving(false);
      }
    },
    [offerApi, workspaceId, policyId, onSaved],
  );

  const setEnabled = useCallback(
    async (targets: readonly ModuleItem[], on: boolean, done: (count: number) => string) => {
      if (!offer) return;
      // Enabling needs the right to give the module here, unless the item is enabled already.
      const fit = on ? targets.filter((item) => item.offered || item.grantable) : targets;
      const changed = fit.filter((item) => item.offered !== on).length;
      await save(enabledChanges(offer.offered, items, fit, on), done(changed));
    },
    [offer, items, save],
  );

  return {
    items,
    byKey,
    offer,
    ready: listings !== null,
    editable: offer?.editable ?? false,
    saving,
    error,
    notice,
    save,
    setEnabled,
  };
}
