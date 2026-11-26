'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import {
  OFFER_KINDS,
  WHOLE_MODULE,
  createOfferApi,
  graphsSettingsHref,
  graphsSummaryLines,
  modelsAfter,
  mapsSettingsHref,
  mapsSummaryLines,
  type FileMode,
  type FileRow,
  type ModelsPart,
  type OfferApi,
  type OfferKind,
  type OfferState,
  type OntologyRow,
} from '@/lib/access-model/workspace-offer';
import { workspaceGroupName } from '@/lib/access-model/levels';
import { FEATURE_SCOPES, WEB_ENGINES, webEngineScopeId } from '@/lib/search-scopes';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type { PublishersView } from '@/lib/iam-admin/types';
import {
  createFeatureAccessApi,
  type FeatureAccessApi,
} from '@/app/workspace/[workspaceId]/settings/features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '@/app/workspace/[workspaceId]/settings/features/feature-access-model';
import {
  draftKey,
  featureChanges,
  isOffered,
  itemName,
  modulesOf,
  offerChanges,
  wholeModule,
} from './offer-model';
import './offer.css';

const DEFAULT_OFFER_API = createOfferApi();

/** The sources of the search, in the search page's order: its features, then the web engines. */
const SEARCH_SOURCE_ROWS: { id: string; label: string }[] = [
  ...FEATURE_SCOPES.map((s) => ({ id: s.id, label: s.label })),
  ...WEB_ENGINES.map((e) => ({ id: webEngineScopeId(e.id), label: `Web · ${e.label}` })),
];
const DEFAULT_FEATURE_API = createFeatureAccessApi();

/** The feature that is Workspace Files, shown in the Files section. */
const FILES_FEATURE = 'files';
const FILE_MODE_LABELS: Record<FileMode, string> = { off: 'Off', read: 'Read', write: 'Read and write' };
const ITEM_LIMIT = 200;

/** How long a read of the offer, its features or its modules is waited for. */
const READ_TIMEOUT_MS = 20_000;

/** ``read``'s answer, or a failure once it took longer than ``READ_TIMEOUT_MS``. */
function answered<T>(read: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('the platform did not answer in time')), READ_TIMEOUT_MS);
    read.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (e: unknown) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}

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
  /** Told after each switch is saved: "<W> access" has a new revision. */
  onChanged?: () => void;
};

/**
 * "<W> access" as the workspace's offer (its policy page › Configuration): its features, then
 * its agents, apps, workflows and pipelines by module, each a toggle (a module offered whole, or
 * item by item). Everyone in "<W> workspace" reaches what is on; their level decides what they
 * do with it. Each toggle is saved at once, as the caller: a write of "<W> access" (`PUT
 * /offer`) or, for a feature, General's (`PUT /feature-access`, Everyone or Nobody), which
 * writes the same policy. IAM says what may change: the policy's `editable`, a feature row's
 * `editable`, and the modules it lets the caller give here.
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
  onChanged,
}: WorkspaceOfferEditorProps) {
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [features, setFeatures] = useState<FeatureAccessState | null>(null);
  const [publishers, setPublishers] = useState<PublishersView | null>(null);
  // Why the features are not shown: a refusal (theirs to see) or a failure (said, with Retry).
  const [featuresFailure, setFeaturesFailure] = useState<{ refused: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [featureErrors, setFeatureErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [items, setItems] = useState<Record<string, Items>>({});
  const [saving, setSaving] = useState(false);

  const loadFeatures = useCallback(async () => {
    setFeaturesFailure(null);
    try {
      setFeatures(await answered(featureApi.read(workspaceId)));
    } catch (e) {
      setFeatures(null);
      const refused = (e as { status?: number }).status === 403;
      setFeaturesFailure({
        refused,
        message: refused
          ? 'You may not read the features of this workspace.'
          : `The features could not be read: ${message(e, 'the platform did not answer')}.`,
      });
    }
  }, [featureApi, workspaceId]);

  // The offer shows as soon as it is read; its features and its modules' names follow (each
  // waited for at most READ_TIMEOUT_MS), never holding it back (UX-24).
  const load = useCallback(async () => {
    const rest = Promise.allSettled([
      loadFeatures(),
      answered(api.publishers(scope)).then(setPublishers, () => setPublishers(null)),
    ]);
    try {
      setOffer(await answered(offerApi.read(workspaceId)));
      setError(null);
    } catch (e) {
      setError(message(e, 'Could not read what this workspace offers.'));
    }
    await rest;
  }, [api, loadFeatures, offerApi, scope, workspaceId]);

  useEffect(() => {
    setNotice(null);
    void load();
  }, [load, nonce]);

  const modules = useMemo(() => (offer ? modulesOf(publishers, offer.offered) : []), [offer, publishers]);
  const allFeatureRows = useMemo(
    () => [...(features?.features ?? [])].sort((a, b) => a.label.localeCompare(b.label)),
    [features],
  );
  const featureRows = useMemo(() => allFeatureRows.filter((row) => row.key !== FILES_FEATURE), [allFeatureRows]);
  const workspaceFiles = useMemo(() => allFeatureRows.find((row) => row.key === FILES_FEATURE) ?? null, [allFeatureRows]);

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

  if (error && !offer)
    return (
      <p className="access-policy-error" role="alert">
        {error}{' '}
        <button type="button" className="access-policy-button" onClick={() => void load()}>
          Retry
        </button>
      </p>
    );
  if (!offer) return <p className="access-empty">Loading the workspace’s offer…</p>;
  if (policyId && offer.access_policy?.id !== policyId) return null;

  const editable = offer.editable;
  const who = workspaceGroupName(workspaceName || 'this workspace');

  const toggleOpen = (kind: OfferKind, module: string) => {
    const key = `${kind}|${module}`;
    const next = !open[key];
    setOpen((current) => ({ ...current, [key]: next }));
    if (next && !items[key]) void loadItems(kind, module);
  };

  // Each toggle is saved at once; the switches wait for the answer.
  const saveNow = async (write: () => Promise<boolean>, done: string) => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      if (await write()) {
        setNotice(done);
        onChanged?.();
      }
    } catch (e) {
      setError(message(e, 'Could not save the offer.'));
    } finally {
      setSaving(false);
    }
  };

  const toggleItem = (kind: OfferKind, module: string, name: string, label: string, on: boolean) =>
    void saveNow(async () => {
      const changes = offerChanges(offer.offered, { [draftKey(kind, module, name)]: on });
      if (changes.length === 0) return false;
      setOffer(await offerApi.save(workspaceId, changes));
      return true;
    }, `${label} ${on ? 'added to' : 'removed from'} the offer.`);

  const toggleSource = (id: string, label: string, on: boolean) =>
    void saveNow(async () => {
      if ((offer.offered.search_sources ?? []).includes(id) === on) return false;
      setOffer(await offerApi.saveSearchSources(workspaceId, { [id]: on }));
      return true;
    }, `${label} ${on ? 'added to' : 'removed from'} the offer.`);

  const toggleFeature = (key: string, label: string, on: boolean) =>
    void saveNow(async () => {
      const changes = featureChanges(allFeatureRows, { [key]: on });
      if (changes.length === 0) return false;
      const next = await featureApi.save(workspaceId, changes);
      const refused = next.errors ?? {};
      setFeatures(next);
      setFeatureErrors(refused);
      return !refused[key];
    }, `${label} ${on ? 'added to' : 'removed from'} the offer.`);

  const chooseFileMode = (row: FileRow, mode: FileMode) =>
    void saveNow(async () => {
      if (mode === row.mode) return false;
      setOffer(await offerApi.saveFiles(workspaceId, { [row.key]: mode }));
      return true;
    }, `${row.label}: ${FILE_MODE_LABELS[mode]}.`);

  const changeModels = (
    part: ModelsPart,
    change: Parameters<typeof modelsAfter>[1],
    done: string,
  ) =>
    void saveNow(async () => {
      const next = modelsAfter(part, change);
      setOffer(await offerApi.saveModels(workspaceId, next.models, next.default));
      return true;
    }, done);

  const modelsSection = (part: ModelsPart) => {
    const choices = [...new Set([...part.available, ...(part.every ? [] : part.offered)])].sort();
    return (
      <div className="access-offer-section" data-offer-section="models">
        <h4 className="access-offer-heading">Models</h4>
        <p className="access-policy-muted">
          The chat models used here, within each person’s model set. An agent built on another model runs on the
          default; one with a provider of its own on another model is refused.
        </p>
        <ul className="access-offer-list">
          <li className="access-offer-row" data-offer-models-every="">
            <OfferSwitch
              label="Every model"
              on={part.every}
              disabled={!editable || saving || (part.every && choices.length === 0)}
              onChange={(on) =>
                changeModels(part, { every: on }, on ? 'Every model is used here.' : 'Limited to some models.')
              }
            />
            <span className="access-offer-name">Every model</span>
          </li>
          {!part.every &&
            choices.map((model) => {
              const on = part.offered.includes(model);
              const last = on && part.offered.length === 1;
              return (
                <li key={model} className="access-offer-row" data-offer-model={model}>
                  <OfferSwitch
                    label={`Use ${model}`}
                    on={on}
                    disabled={!editable || saving || last}
                    onChange={(next) =>
                      changeModels(part, { model, on: next }, `${model} ${next ? 'added to' : 'removed from'} the models.`)
                    }
                  />
                  <span className="access-offer-name">{model}</span>
                  {last && <span className="access-offer-note">The last model: use every model instead</span>}
                </li>
              );
            })}
        </ul>
        {!part.every && (
          <label className="access-offer-row" data-offer-models-default="">
            <span className="access-offer-name">Default model</span>
            <select
              className="access-offer-select"
              aria-label="Default model"
              value={part.default ?? ''}
              disabled={!editable || saving}
              onChange={(e) => changeModels(part, { default: e.target.value }, `${e.target.value} is the default model.`)}
            >
              {part.offered.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    );
  };

  const toggleOntology = (row: OntologyRow, on: boolean) =>
    void saveNow(async () => {
      if (row.offered === on) return false;
      setOffer(await offerApi.saveOntologies(workspaceId, { [row.id]: on }));
      return true;
    }, `${row.label} ${on ? 'added to' : 'removed from'} the offer.`);

  const featureRow = (row: FeatureRow, label = row.label) => {
    const on = row.choice === 'everyone';
    const disabled = !row.editable || saving || (!row.offered && !on);
    return (
      <li key={row.key} className="access-offer-row" data-offer-feature={row.key}>
        <OfferSwitch label={`Offer ${label}`} on={on} disabled={disabled} onChange={(next) => toggleFeature(row.key, label, next)} />
        <span className="access-offer-name">{label}</span>
        {!row.offered && <span className="access-offer-note">Not offered by the organization</span>}
        {row.offered && !row.editable && row.reason && <span className="access-offer-note">{row.reason}</span>}
        {featureErrors[row.key] && (
          <span className="access-policy-error" role="alert">
            {featureErrors[row.key]}
          </span>
        )}
      </li>
    );
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
      {notice && (
        <p className="access-policy-notice" role="status" data-offer-notice="">
          {notice}
        </p>
      )}

      <div className="access-offer-section" data-offer-section="features">
        <h4 className="access-offer-heading">Features</h4>
        {features === null ? (
          featuresFailure === null ? (
            <p className="access-policy-muted">Loading the features…</p>
          ) : featuresFailure.refused ? (
            <p className="access-policy-muted">{featuresFailure.message}</p>
          ) : (
            <p className="access-policy-error" role="alert">
              {featuresFailure.message}{' '}
              <button type="button" className="access-policy-button" onClick={() => void loadFeatures()}>
                Retry
              </button>
            </p>
          )
        ) : featureRows.length === 0 ? (
          <p className="access-policy-muted">No feature is enabled on this deployment.</p>
        ) : (
          <ul className="access-offer-list">{featureRows.map((row) => featureRow(row))}</ul>
        )}
      </div>

      <div className="access-offer-section" data-offer-section="files">
        <h4 className="access-offer-heading">Files</h4>
        <p className="access-policy-muted">
          What the people of this workspace open beside its own files. Read and write lets a Member write; a Viewer
          still only reads.
        </p>
        <ul className="access-offer-list">
          {workspaceFiles && featureRow(workspaceFiles, 'Workspace Files')}
          {(offer.files ?? []).map((row) => (
            <li key={row.key} className="access-offer-row" data-offer-file={row.key}>
              <select
                className="access-offer-select"
                aria-label={row.label}
                value={row.mode}
                disabled={!row.editable || saving}
                onChange={(e) => chooseFileMode(row, e.target.value as FileMode)}
              >
                {row.modes.map((mode) => (
                  <option key={mode} value={mode} disabled={!row.choices.includes(mode)}>
                    {FILE_MODE_LABELS[mode]}
                  </option>
                ))}
              </select>
              <span className="access-offer-name">{row.label}</span>
              {!row.editable && row.reason && <span className="access-offer-note">{row.reason}</span>}
            </li>
          ))}
        </ul>
        {offer.my_files && (
          <p className="access-policy-muted" data-offer-my-files="">
            {`My Files: every Member writes theirs; Viewers ${
              offer.my_files.viewers === 'read' ? 'read theirs' : 'have none'
            } (a setting of the deployment).`}
          </p>
        )}
      </div>

      {offer.graphs && (
        <div className="access-offer-section" data-offer-section="graphs">
          <h4 className="access-offer-heading">Graphs</h4>
          <p className="access-policy-muted">
            The graphs of other workspaces or of the platform its people read, or write (a Viewer still only reads), and
            what it closes of its own.
          </p>
          <ul className="access-offer-list" data-offer-graphs="">
            {graphsSummaryLines(offer.graphs).map((line) => (
              <li key={line} className="access-offer-row">
                <span className="access-offer-name">{line}</span>
              </li>
            ))}
          </ul>
          <a className="access-policy-link" href={graphsSettingsHref(workspaceId)}>
            Change them in Settings › Graphs
          </a>
        </div>
      )}

      {offer.models && modelsSection(offer.models)}
      {offer.maps && (
        <div className="access-offer-section" data-offer-section="maps">
          <h4 className="access-offer-heading">Maps</h4>
          <p className="access-policy-muted">
            The feeds and basemaps of the platform its people read on its map, and those other workspaces share with
            it. Its admins still hide any of them in the workspace.
          </p>
          <ul className="access-offer-list" data-offer-maps="">
            {mapsSummaryLines(offer.maps).map((line) => (
              <li key={line} className="access-offer-row">
                <span className="access-offer-name">{line}</span>
              </li>
            ))}
          </ul>
          <a className="access-policy-link" href={mapsSettingsHref(workspaceId)}>
            Change them in Settings › Maps
          </a>
        </div>
      )}

      {offer.ontologies && (
        <div className="access-offer-section" data-offer-section="ontologies">
          <h4 className="access-offer-heading">Ontologies</h4>
          <p className="access-policy-muted">
            The ontology files its people read here, as in Settings › Ontologies. An administrator of its organization
            adds one; a workspace admin may take one back.
          </p>
          {offer.ontologies.error ? (
            <p className="access-policy-error" role="alert">
              {offer.ontologies.error}
            </p>
          ) : offer.ontologies.rows.length === 0 ? (
            <p className="access-policy-muted">No ontology file is listed on this deployment.</p>
          ) : (
            <ul className="access-offer-list">
              {offer.ontologies.rows.map((row) => (
                <li key={row.id} className="access-offer-row" data-offer-ontology={row.id}>
                  <OfferSwitch
                    label={`Offer ${row.label}`}
                    on={row.offered}
                    disabled={!editable || !row.editable || saving}
                    onChange={(next) => toggleOntology(row, next)}
                  />
                  <span className="access-offer-name">{row.label}</span>
                  {row.module && <span className="access-offer-note">{row.module}</span>}
                  {!row.available && <span className="access-offer-note">Unavailable in the current catalog</span>}
                  {!row.editable && row.reason && <span className="access-offer-note">{row.reason}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="access-offer-section" data-offer-section="search-sources">
        <h4 className="access-offer-heading">Search sources</h4>
        <p className="access-policy-muted">
          What the search reads here. A web engine sends the query outside the platform.
        </p>
        <ul className="access-offer-list">
          {SEARCH_SOURCE_ROWS.map(({ id, label }) => {
            const on = (offer.offered.search_sources ?? []).includes(id);
            return (
              <li key={id} className="access-offer-row" data-offer-source={id}>
                <OfferSwitch
                  label={`Offer ${label} to the search`}
                  on={on}
                  disabled={!editable || saving}
                  onChange={(next) => toggleSource(id, label, next)}
                />
                <span className="access-offer-name">{label}</span>
              </li>
            );
          })}
        </ul>
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
                  const whole = wholeModule(offer.offered, kind, module, {});
                  const key = `${kind}|${module}`;
                  const shown = items[key];
                  return (
                    <li key={module} className="access-offer-module" data-offer-module={module}>
                      <div className="access-offer-row">
                        <OfferSwitch
                          label={`Offer every ${label.toLowerCase().replace(/s$/, '')} of ${module}`}
                          on={whole}
                          disabled={!editable || saving || (!grantable && !whole)}
                          onChange={(next) => toggleItem(kind, module, WHOLE_MODULE, `Every ${label.toLowerCase().replace(/s$/, '')} of ${module}`, next)}
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
                                    on={isOffered(offer.offered, kind, module, item.name, {})}
                                    disabled={!editable || saving || whole}
                                    onChange={(next) => toggleItem(kind, module, item.name, item.label, next)}
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
