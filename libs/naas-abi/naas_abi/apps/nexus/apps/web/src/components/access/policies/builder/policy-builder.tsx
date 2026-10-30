'use client';

import { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Plus, X } from 'lucide-react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { ListedResource } from '@/lib/iam-admin/types';
import { POLICY_VERSION } from '../policy-editor-model';
import {
  grantableOn,
  scopedName,
  wildcardProblem,
  type BuilderPublisher,
  type BuilderType,
  type Choice,
  type Choices,
} from './builder-model';
import './policy-builder.css';

const SEARCH_DELAY_MS = 250;
const PAGE = 25;

function message(error: unknown): string {
  return error instanceof IamAdminError || error instanceof Error ? error.message : String(error);
}

/** What a pattern the caller may grant stands for: the container the policy is attached at
 *  (`${scope}`), or what it holds that they may grant. */
function patternNote(pattern: string, type: BuilderType): string {
  if (pattern === '${scope}') return type.container ? `this ${type.type.replace(/_/g, ' ')} itself` : 'the scope itself';
  return 'all you may grant';
}

type Listing = { items: ListedResource[]; next: string | null; listed: boolean; loading: boolean; error: string | null };

/** The existing resources of ``type`` the caller may list at ``scope``, searched and paged. */
function useListing(api: IamAdminApi, scope: string, type: BuilderType, open: boolean, search: string, delayMs: number) {
  const [listing, setListing] = useState<Listing>({ items: [], next: null, listed: type.listed, loading: false, error: null });
  const query = { scope, service: type.service, type: type.type, module: type.module, q: search.trim(), limit: PAGE };

  useEffect(() => {
    if (!open || !type.listed) return;
    let cancelled = false;
    setListing((previous) => ({ ...previous, loading: true }));
    const timer = setTimeout(() => {
      api
        .resources(query)
        .then((page) => !cancelled && setListing({ items: page.items, next: page.next_cursor, listed: page.listed, loading: false, error: null }))
        .catch((error) => !cancelled && setListing({ items: [], next: null, listed: true, loading: false, error: message(error) }));
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // The query is read through its parts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, scope, type.key, open, search, delayMs]);

  const more = async () => {
    if (!listing.next) return;
    try {
      const page = await api.resources({ ...query, cursor: listing.next });
      setListing((previous) => ({ ...previous, items: [...previous.items, ...page.items], next: page.next_cursor }));
    } catch (error) {
      setListing((previous) => ({ ...previous, error: message(error) }));
    }
  };
  return { listing, more };
}

type Verdict = { pattern: string; problem: string | null; checking: boolean };

/** A wildcard typed after `${scope}/`: checked as typed, first here (it names the type), then by
 *  IAM (`/policies/validate`, as a policy of the scope), and added once both accept it. */
function WildcardField({
  api,
  type,
  title,
  actions,
  validateAt,
  onAdd,
  delayMs,
}: {
  api: IamAdminApi;
  type: BuilderType;
  title: string;
  actions: string[];
  validateAt?: string;
  onAdd: (resource: string) => void;
  delayMs: number;
}) {
  const [text, setText] = useState('');
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const resource = `\${scope}/${text.trim()}`;
  const local = text.trim() ? wildcardProblem(type, text) : null;
  const checkedActions = actions.length ? actions : [type.actions[0].action];

  useEffect(() => {
    if (!text.trim() || local) {
      setVerdict(null);
      return;
    }
    let cancelled = false;
    setVerdict({ pattern: resource, problem: null, checking: true });
    const timer = setTimeout(() => {
      api
        .validatePolicy(
          { document: { version: POLICY_VERSION, statements: [{ effect: 'Allow', actions: checkedActions, resources: [resource] }] } },
          validateAt,
        )
        .then((answer) => {
          if (cancelled) return;
          setVerdict({ pattern: resource, problem: answer.valid ? null : answer.errors.join('; ') || 'IAM refuses this pattern.', checking: false });
        })
        .catch((error) => !cancelled && setVerdict({ pattern: resource, problem: message(error), checking: false }));
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // The actions are read through their key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, resource, local, validateAt, checkedActions.join(','), delayMs]);

  const accepted = !local && verdict?.pattern === resource && !verdict.checking && verdict.problem === null;
  const add = () => {
    if (!accepted) return;
    onAdd(resource);
    setText('');
  };
  return (
    <div className="access-builder-wildcard">
      <div className="access-builder-wildcard-row">
        <code className="access-builder-prefix">{'${scope}/'}</code>
        <input
          type="text"
          className="access-policy-input"
          aria-label={`Wildcard of ${title}`}
          placeholder={`${type.marker}*`}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              add();
            }
          }}
        />
        <button type="button" className="access-policy-button" disabled={!accepted} onClick={add}>
          <Plus size={12} /> Add pattern
        </button>
      </div>
      {text.trim() && (
        <p
          className={local || verdict?.problem ? 'access-builder-refused' : 'access-policy-muted'}
          role={local || verdict?.problem ? 'alert' : 'status'}
          data-wildcard-verdict=""
        >
          {local ?? (verdict?.checking || !verdict ? 'Checking with IAM…' : verdict.problem ?? 'Valid pattern.')}
        </p>
      )}
    </div>
  );
}

/** One resource type: its actions, then its resources (the patterns the caller may grant, the
 *  listing, a wildcard), and what is chosen. */
function TypeSection({
  api,
  scope,
  validateAt,
  publisher,
  type,
  choice,
  onChange,
  refused,
  delayMs,
}: {
  api: IamAdminApi;
  scope: string;
  validateAt?: string;
  publisher: BuilderPublisher;
  type: BuilderType;
  choice: Choice;
  onChange: (choice: Choice) => void;
  refused?: string;
  delayMs: number;
}) {
  const chosen = choice.actions.length + choice.resources.length > 0;
  const [open, setOpen] = useState(chosen || !!refused);
  const [search, setSearch] = useState('');
  const { listing, more } = useListing(api, scope, type, open, search, delayMs);
  const title = publisher.kind === 'module' ? `${publisher.label} ${type.label}` : type.label;
  useEffect(() => {
    if (refused) setOpen(true);
  }, [refused]);

  const toggleAction = (action: string, on: boolean) =>
    onChange({ ...choice, actions: on ? [...choice.actions, action] : choice.actions.filter((a) => a !== action) });
  const toggleResource = (resource: string, on: boolean) =>
    onChange({
      ...choice,
      resources: on
        ? choice.resources.includes(resource)
          ? choice.resources
          : [...choice.resources, resource]
        : choice.resources.filter((r) => r !== resource),
    });
  // The patterns the caller may grant the chosen actions on (every action's when none is).
  const patterns = [
    ...new Set(
      type.actions
        .filter((a) => choice.actions.length === 0 || choice.actions.includes(a.action))
        .flatMap((a) => a.resources),
    ),
  ];
  // What the caller lists of the type, kept to what they may grant of it (within a parent).
  const items = listing.items
    .map((item) => ({ item, resource: scopedName(item.name, scope) }))
    .filter(({ resource }) => grantableOn(type, resource));
  const listedNames = new Set(items.map(({ resource }) => resource));
  // A listed resource is shown once: the container itself (`${scope}`) by its name, not twice.
  const shownPatterns = patterns.filter((p) => !listedNames.has(p));
  const others = choice.resources.filter((r) => !patterns.includes(r) && !listedNames.has(r));

  return (
    <li className="access-builder-type" data-builder-type={type.key}>
      <button
        type="button"
        className="access-builder-type-header"
        aria-expanded={open}
        aria-label={`${open ? 'Close' : 'Open'} ${title}`}
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
        <span className="access-builder-type-label">{title}</span>
        <code className="access-builder-type-code">
          {type.service}:{type.type}
        </code>
        {chosen && (
          <span className="access-policy-muted">
            {choice.actions.length} action{choice.actions.length === 1 ? '' : 's'} · {choice.resources.length} resource
            {choice.resources.length === 1 ? '' : 's'}
          </span>
        )}
      </button>
      {refused && (
        <p className="access-builder-refused" role="alert">
          {refused}
        </p>
      )}
      {open && (
        <div className="access-builder-type-body">
          {type.description && <p className="access-policy-muted">{type.description}</p>}
          <div className="access-builder-section">
            <h5 className="access-builder-heading">Actions</h5>
            <ul className="access-builder-items">
              {type.actions.map((action) => (
                <li key={action.action} className="access-builder-item">
                  <label className="access-checkbox" title={action.description || undefined}>
                    <input
                      type="checkbox"
                      aria-label={`${title}: ${action.name}`}
                      checked={choice.actions.includes(action.action)}
                      onChange={(e) => toggleAction(action.action, e.target.checked)}
                    />
                    <span>{action.name}</span>
                    <span className="access-policy-badge">{action.level}</span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
          <div className="access-builder-section">
            <h5 className="access-builder-heading">Resources</h5>
            <ul className="access-builder-items access-builder-items-wide" aria-label={`What you may grant of ${title}`}>
              {shownPatterns.map((pattern) => (
                <li key={pattern} className="access-builder-item">
                  <label className="access-checkbox">
                    <input
                      type="checkbox"
                      aria-label={`${title}: ${pattern}`}
                      checked={choice.resources.includes(pattern)}
                      onChange={(e) => toggleResource(pattern, e.target.checked)}
                    />
                    <code>{pattern}</code>
                    <span className="access-policy-muted">{patternNote(pattern, type)}</span>
                  </label>
                </li>
              ))}
            </ul>
            {listing.listed && (
              <div className="access-builder-listing">
                <input
                  type="search"
                  className="access-policy-input"
                  aria-label={`Search ${title}`}
                  placeholder={`Search ${type.label.toLowerCase()}`}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                {listing.error && <p className="access-policy-error">{listing.error}</p>}
                <ul className="access-builder-items" aria-label={`Existing ${title}`}>
                  {items.map(({ item, resource }) => {
                    return (
                      <li key={item.name} className="access-builder-item" data-builder-resource={resource}>
                        <label className="access-checkbox" title={item.description || item.name}>
                          <input
                            type="checkbox"
                            aria-label={`${title}: ${item.label}`}
                            checked={choice.resources.includes(resource)}
                            onChange={(e) => toggleResource(resource, e.target.checked)}
                          />
                          <span>{item.label}</span>
                          {item.label !== item.id && <code className="access-policy-muted">{item.id}</code>}
                        </label>
                      </li>
                    );
                  })}
                  {!listing.loading && items.length === 0 && !listing.error && (
                    <li className="access-policy-muted">{search ? 'Nothing matches.' : 'None you may list here.'}</li>
                  )}
                  {listing.loading && <li className="access-policy-muted">Loading…</li>}
                </ul>
                {listing.next && (
                  <button type="button" className="access-policy-button" onClick={() => void more()}>
                    Load more
                  </button>
                )}
              </div>
            )}
            {!listing.listed && <p className="access-policy-muted">Not listed: write a wildcard.</p>}
            {others.length > 0 && (
              <ul className="access-policy-values" aria-label={`Chosen patterns of ${title}`}>
                {others.map((resource) => (
                  <li key={resource} className="access-policy-value">
                    <code>{resource}</code>
                    <button
                      type="button"
                      className="access-policy-icon-button"
                      aria-label={`Remove ${resource}`}
                      onClick={() => toggleResource(resource, false)}
                    >
                      <X size={12} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <WildcardField
              api={api}
              type={type}
              title={title}
              actions={choice.actions}
              validateAt={validateAt}
              onAdd={(resource) => toggleResource(resource, true)}
              delayMs={delayMs}
            />
            {choice.actions.length > 0 && choice.resources.length === 0 && (
              <p className="access-policy-notice" role="status">
                Pick the resources these actions are on.
              </p>
            )}
            {choice.resources.length > 0 && choice.actions.length === 0 && (
              <p className="access-policy-notice" role="status">
                Pick the actions allowed on these resources.
              </p>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

/**
 * What the caller may grant at the scope, by publisher (the engine, naas_abi, then the modules):
 * per resource type its actions, then its resources, picked from the listing or written as a
 * wildcard under `${scope}/`. ``refused`` holds IAM's refusal of a type's choice, shown beside
 * it. ``kept`` counts the statements the builder cannot show (they stay in the policy: the
 * Statements view edits them).
 */
export function PolicyBuilder({
  api,
  scope,
  validateAt,
  publishers,
  choices,
  onChange,
  kept,
  refused = {},
  delayMs = SEARCH_DELAY_MS,
}: {
  api: IamAdminApi;
  /** Where the policy is written: `abi:` or a container. */
  scope: string;
  /** The owner `/policies/validate` checks a wildcard for (none: the platform). */
  validateAt?: string;
  publishers: BuilderPublisher[];
  choices: Choices;
  onChange: (key: string, choice: Choice) => void;
  kept: number;
  refused?: Record<string, string>;
  delayMs?: number;
}) {
  if (publishers.length === 0) {
    return (
      <p className="access-policy-notice" role="status">
        You hold nothing here that you could grant: write statements in the Statements view instead.
      </p>
    );
  }
  return (
    <div className="access-builder" aria-label="Policy builder">
      {kept > 0 && (
        <p className="access-policy-muted">
          {kept} other statement{kept === 1 ? '' : 's'} stay{kept === 1 ? 's' : ''} as written (Statements view).
        </p>
      )}
      {publishers.map((publisher) => {
        const chosen = publisher.types.filter((t) => choices[t.key]?.actions.length && choices[t.key]?.resources.length).length;
        return (
          <fieldset key={publisher.id} className="access-builder-group" data-builder-publisher={publisher.id}>
            <legend className="access-builder-legend">
              <span>{publisher.label}</span>
              <span className="access-policy-muted">
                {publisher.kind === 'module' ? 'module' : publisher.kind === 'engine' ? 'kernel services' : 'Nexus'} ·{' '}
                {chosen} of {publisher.types.length} chosen
              </span>
            </legend>
            <ul className="access-builder-types">
              {publisher.types.map((type) => (
                <TypeSection
                  key={type.key}
                  api={api}
                  scope={scope}
                  validateAt={validateAt}
                  publisher={publisher}
                  type={type}
                  choice={choices[type.key] ?? { actions: [], resources: [] }}
                  onChange={(choice) => onChange(type.key, choice)}
                  refused={refused[type.key]}
                  delayMs={delayMs}
                />
              ))}
            </ul>
          </fieldset>
        );
      })}
    </div>
  );
}
