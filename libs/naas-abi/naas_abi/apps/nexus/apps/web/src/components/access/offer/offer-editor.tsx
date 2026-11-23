'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import {
  OFFER_KINDS,
  WHOLE_MODULE,
  createOfferApi,
  type OfferApi,
  type OfferKind,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import { workspaceGroupName } from '@/lib/access-model/levels';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type { PublishersView } from '@/lib/iam-admin/types';
import {
  createFeatureAccessApi,
  type FeatureAccessApi,
} from '@/app/workspace/[workspaceId]/settings/general/feature-access-api';
import type { FeatureAccessState } from '@/app/workspace/[workspaceId]/settings/general/feature-access-model';
import {
  draftKey,
  featureChanges,
  isOffered,
  itemName,
  modulesOf,
  offerChanges,
  unsavedCount,
  wholeModule,
  type OfferDrafts,
} from './offer-model';
import './offer.css';

const DEFAULT_OFFER_API = createOfferApi();
const DEFAULT_FEATURE_API = createFeatureAccessApi();
const ITEM_LIMIT = 200;

const message = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

type Items = { status: 'loading' } | { status: 'ready'; listed: boolean; items: { name: string; label: string }[] } | { status: 'failed'; error: string };

/** An on/off toggle: a button with the switch role, its state in `aria-checked`. */
export function OfferSwitch({
  label,
  on,
  disabled,
  onChange,
}: {
  label: string;
  on: boolean;
  disabled?: boolean;
  onChange: (on: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      title={label}
      disabled={disabled}
      className="access-offer-switch"
      data-on={on ? '' : undefined}
      onClick={() => onChange(!on)}
    >
      <span className="access-offer-switch-knob" />
    </button>
  );
}

export type WorkspaceOfferEditorProps = {
  workspaceId: string;
  /** The workspace's container: where IAM says what the caller may give (`/publishers`). */
  scope: string;
  /** Only this policy's page shows it: the editor stays empty when "<W> access" is another. */
  policyId?: string;
  /** The workspace's name, for the words. */
  workspaceName?: string;
  api: IamAdminApi;
  offerApi?: OfferApi;
  featureApi?: FeatureAccessApi;
  nonce?: number;
};

/**
 * "<W> access" as the workspace's offer: its features, then its agents, apps, workflows and
 * pipelines by module, each a toggle (a module offered whole, or item by item). Everyone in
 * "<W> workspace" reaches what is on; their level decides what they do with it. Saved in one
 * write of "<W> access" as the caller (`PUT /offer`) and, for features, General's
 * (`PUT /feature-access`, Everyone or Nobody). IAM says what may change: the policy's
 * `editable`, a feature row's `editable`, and the modules it lets the caller give here.
 */
export function WorkspaceOfferEditor({
  workspaceId,
  scope,
  policyId,
  workspaceName,
  api,
  offerApi = DEFAULT_OFFER_API,
  featureApi = DEFAULT_FEATURE_API,
  nonce = 0,
}: WorkspaceOfferEditorProps) {
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [features, setFeatures] = useState<FeatureAccessState | null>(null);
  const [publishers, setPublishers] = useState<PublishersView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<OfferDrafts>({});
  const [featureDrafts, setFeatureDrafts] = useState<Record<string, boolean>>({});
  const [featureErrors, setFeatureErrors] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [items, setItems] = useState<Record<string, Items>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const [readOffer, readFeatures, readPublishers] = await Promise.all([
        offerApi.read(workspaceId),
        featureApi.read(workspaceId).catch(() => null),
        api.publishers(scope).catch(() => null),
      ]);
      setOffer(readOffer);
      setFeatures(readFeatures);
      setPublishers(readPublishers);
      setError(null);
    } catch (e) {
      setError(message(e, 'Could not read what this workspace offers.'));
    }
  }, [api, featureApi, offerApi, scope, workspaceId]);

  useEffect(() => {
    setDrafts({});
    setFeatureDrafts({});
    void load();
  }, [load, nonce]);

  const modules = useMemo(() => (offer ? modulesOf(publishers, offer.offered) : []), [offer, publishers]);
  const featureRows = useMemo(
    () => [...(features?.features ?? [])].sort((a, b) => a.label.localeCompare(b.label)),
    [features],
  );

  const loadItems = useCallback(
    async (kind: OfferKind, module: string) => {
      const key = `${kind}|${module}`;
      setItems((current) => ({ ...current, [key]: { status: 'loading' } }));
      const type = OFFER_KINDS.find((k) => k.kind === kind)!.type;
      try {
        const page = await api.resources({ scope, service: 'module', type, module, limit: ITEM_LIMIT });
        setItems((current) => ({
          ...current,
          [key]: {
            status: 'ready',
            listed: page.listed,
            items: page.items.map((item) => ({ name: itemName(module, item.id), label: item.label || itemName(module, item.id) })),
          },
        }));
      } catch (e) {
        setItems((current) => ({ ...current, [key]: { status: 'failed', error: message(e, 'Could not list them.') } }));
      }
    },
    [api, scope],
  );

  if (error && !offer) return <p className="access-policy-error" role="alert">{error}</p>;
  if (!offer) return <p className="access-empty">Loading the workspace’s offer…</p>;
  if (policyId && offer.access_policy?.id !== policyId) return null;

  const editable = offer.editable;
  const pending = unsavedCount(offer.offered, drafts, featureRows, featureDrafts);
  const who = workspaceGroupName(workspaceName || 'this workspace');

  const toggleOpen = (kind: OfferKind, module: string) => {
    const key = `${kind}|${module}`;
    const next = !open[key];
    setOpen((current) => ({ ...current, [key]: next }));
    if (next && !items[key]) void loadItems(kind, module);
  };

  const setDraft = (kind: OfferKind, module: string, name: string, on: boolean) => {
    setSaved(false);
    setDrafts((current) => ({ ...current, [draftKey(kind, module, name)]: on }));
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const changes = offerChanges(offer.offered, drafts);
      const toFeatures = featureChanges(featureRows, featureDrafts);
      if (changes.length) {
        setOffer(await offerApi.save(workspaceId, changes));
        setDrafts({});
      }
      if (toFeatures.length) {
        const next = await featureApi.save(workspaceId, toFeatures);
        const refused = next.errors ?? {};
        setFeatures(next);
        setFeatureErrors(refused);
        setFeatureDrafts((current) => Object.fromEntries(Object.entries(current).filter(([key]) => refused[key])));
      }
      setSaved(true);
    } catch (e) {
      setError(message(e, 'Could not save the offer.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="access-offer" aria-label="Workspace offer" data-offer={offer.workspace_id}>
      <header className="access-offer-header">
        <h3 className="access-policy-title">What this workspace offers</h3>
        <p className="access-policy-muted">
          Everyone in {who} reaches what is on here; their level (Viewer, Member, Workspace admin) decides what
          they may do with it. It is also the workspace’s ceiling: nothing given here reaches beyond it. A module
          added to the platform is offered nowhere until it is turned on here.
        </p>
        {!editable && (
          <p className="access-policy-muted" data-offer-readonly="">
            {offer.access_policy
              ? `Read-only: IAM does not let you change ${offer.access_policy.name}.`
              : 'This workspace has no access policy yet.'}
          </p>
        )}
      </header>
      {error && <p className="access-policy-error" role="alert">{error}</p>}

      <div className="access-offer-section" data-offer-section="features">
        <h4 className="access-offer-heading">Features</h4>
        {features === null ? (
          <p className="access-policy-muted">You may not read the features of this workspace.</p>
        ) : featureRows.length === 0 ? (
          <p className="access-policy-muted">No feature is enabled on this deployment.</p>
        ) : (
          <ul className="access-offer-list">
            {featureRows.map((row) => {
              const on = featureDrafts[row.key] ?? row.choice === 'everyone';
              const disabled = !row.editable || saving || (!row.offered && !on);
              return (
                <li key={row.key} className="access-offer-row" data-offer-feature={row.key}>
                  <OfferSwitch
                    label={`Offer ${row.label}`}
                    on={on}
                    disabled={disabled}
                    onChange={(next) => {
                      setSaved(false);
                      setFeatureDrafts((current) => ({ ...current, [row.key]: next }));
                    }}
                  />
                  <span className="access-offer-name">{row.label}</span>
                  {!row.offered && <span className="access-offer-note">Not offered by the organization</span>}
                  {row.offered && !row.editable && row.reason && <span className="access-offer-note">{row.reason}</span>}
                  {featureErrors[row.key] && (
                    <span className="access-policy-error" role="alert">
                      {featureErrors[row.key]}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {OFFER_KINDS.map(({ kind, label }) => {
        const ofKind = modules.filter((m) => m.kinds.includes(kind));
        return (
          <div key={kind} className="access-offer-section" data-offer-section={kind}>
            <h4 className="access-offer-heading">{label}</h4>
            {ofKind.length === 0 ? (
              <p className="access-policy-muted">No module has {label.toLowerCase()} you may offer here.</p>
            ) : (
              <ul className="access-offer-list">
                {ofKind.map(({ module, grantable }) => {
                  const whole = wholeModule(offer.offered, kind, module, drafts);
                  const key = `${kind}|${module}`;
                  const shown = items[key];
                  return (
                    <li key={module} className="access-offer-module" data-offer-module={module}>
                      <div className="access-offer-row">
                        <OfferSwitch
                          label={`Offer every ${label.toLowerCase().replace(/s$/, '')} of ${module}`}
                          on={whole}
                          disabled={!editable || saving || (!grantable && !whole)}
                          onChange={(next) => setDraft(kind, module, WHOLE_MODULE, next)}
                        />
                        <span className="access-offer-name">{module}</span>
                        <span className="access-offer-note">{whole ? 'Whole module' : 'Item by item'}</span>
                        <button
                          type="button"
                          className="access-offer-expand"
                          aria-expanded={!!open[key]}
                          onClick={() => toggleOpen(kind, module)}
                        >
                          {open[key] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          {label} of {module}
                        </button>
                      </div>
                      {open[key] && (
                        <ul className="access-offer-items" aria-label={`${label} of ${module}`}>
                          {!shown || shown.status === 'loading' ? (
                            <li className="access-policy-muted">Loading…</li>
                          ) : shown.status === 'failed' ? (
                            <li className="access-policy-error">{shown.error}</li>
                          ) : (
                            <>
                              {itemsWithOffered(shown.items, offer.offered[kind], module).map((item) => (
                                <li key={item.name} className="access-offer-row" data-offer-item={`${module}/${item.name}`}>
                                  <OfferSwitch
                                    label={`Offer ${item.label}`}
                                    on={isOffered(offer.offered, kind, module, item.name, drafts)}
                                    disabled={!editable || saving || whole}
                                    onChange={(next) => setDraft(kind, module, item.name, next)}
                                  />
                                  <span className="access-offer-name">{item.label}</span>
                                </li>
                              ))}
                              {!shown.listed && (
                                <li className="access-policy-muted">Its items are not listed: offer the whole module.</li>
                              )}
                            </>
                          )}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}

      <footer className="access-offer-footer">
        <span className="access-policy-muted" role="status">
          {pending === 0 ? (saved ? 'Saved' : 'No unsaved change') : `${pending} unsaved change${pending === 1 ? '' : 's'}`}
        </span>
        <button
          type="button"
          className="platform-users-button"
          disabled={saving || pending === 0}
          onClick={() => {
            setDrafts({});
            setFeatureDrafts({});
            setFeatureErrors({});
          }}
        >
          Discard
        </button>
        <button
          type="button"
          className="platform-users-button platform-users-button-primary"
          data-action="save-offer"
          disabled={saving || pending === 0}
          onClick={() => void save()}
        >
          {saving ? 'Saving…' : 'Save offer'}
        </button>
      </footer>
    </section>
  );
}

/** The listed items, and those offered by name that the listing missed (so they can be taken
 *  back), by label. */
function itemsWithOffered(
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
