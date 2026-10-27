'use client';

import { useCallback, useEffect, useState } from 'react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { DeclaredCatalog, ManifestStatus, ManifestView, PolicyDocument } from '@/lib/iam-admin/types';
import type { AccessViewProps, PlatformViewProps } from '../access-props';
import {
  initialChoice,
  isUnchanged,
  narrowed,
  problem,
  summarize,
  summaryText,
  toggleAction,
  toggleResource,
  type Choice,
} from './narrow-model';
import './approvals.css';

const message = (e: unknown) => (e instanceof IamAdminError ? e.message : String(e));
const STATUSES: (ManifestStatus | 'all')[] = ['pending', 'approved', 'rejected', 'superseded', 'all'];
const when = (value: string | null) => (value ? new Date(value).toLocaleString() : '–');

/** What modules ask for, and the admin's answer: approve, narrow or reject. */
export function ApprovalsView({ api, can, nonce }: PlatformViewProps) {
  const [status, setStatus] = useState<ManifestStatus | 'all'>('pending');
  const [items, setItems] = useState<ManifestView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await api.listManifests(status === 'all' ? undefined : status)).items);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, status]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  return (
    <div className="access-approval">
      <div className="access-approval-filter">
        <label className="access-checkbox">
          Status
          <select className="access-input" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value as ManifestStatus | 'all')}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="access-source-note" role="alert">{error}</p>}
      {items === null && !error && <p className="access-empty">Loading…</p>}
      {items?.length === 0 && <p className="access-empty">No {status === 'all' ? '' : status} manifests.</p>}
      {items?.map((manifest) => (
        <ManifestCard key={`${manifest.principal_id}/${manifest.sha256}`} api={api} can={can} manifest={manifest} onDecided={load} />
      ))}
    </div>
  );
}

function ManifestCard({
  api,
  can,
  manifest,
  onDecided,
}: Pick<AccessViewProps, 'api' | 'can'> & { manifest: ManifestView; onDecided: () => Promise<void> }) {
  const [mode, setMode] = useState<'view' | 'narrow' | 'reject'>('view');
  const [choice, setChoice] = useState<Choice>(() => initialChoice(manifest.document));
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const decide = async (call: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await call();
      setError(null);
      setMode('view');
      await onDecided();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  const pending = manifest.status === 'pending';
  const summary = summarize(manifest.document, choice);
  const blocked = problem(manifest.document, choice);
  const label = manifest.account_name ?? manifest.principal_id;

  return (
    <article className="access-approval-card" data-manifest={manifest.sha256}>
      <header className="access-approval-header">
        <div>
          <strong>{label}</strong>{' '}
          <span className="access-approval-status" data-status={manifest.status}>{manifest.status}</span>
        </div>
        <div className="access-approval-meta">
          {manifest.project}/{manifest.module_id} · <span className="access-mono">{manifest.sha256.slice(0, 12)}</span> · submitted {when(manifest.submitted_at)}
          {manifest.decided_at && ` · decided ${when(manifest.decided_at)}`}
          {manifest.reason && ` · ${manifest.reason}`}
        </div>
      </header>
      {error && <p className="access-source-note" role="alert">{error}</p>}
      <Statements document={manifest.document} choice={mode === 'narrow' ? choice : null} onAction={(i, a) => setChoice(toggleAction(choice, i, a))} onResource={(i, r) => setChoice(toggleResource(choice, i, r))} />
      {manifest.catalog && <DeclaredActions catalog={manifest.catalog} />}
      {pending && mode === 'view' && (
        <div className="access-approval-actions">
          {can('iam:ApproveManifest') && (
            <>
              <button type="button" className="access-button access-button-primary" disabled={busy} onClick={() => void decide(() => api.approveManifest(manifest.principal_id, manifest.sha256))}>
                Approve
              </button>
              <button type="button" className="access-button" disabled={busy} onClick={() => setMode('narrow')}>
                Narrow…
              </button>
            </>
          )}
          {can('iam:RejectManifest') && (
            <button type="button" className="access-button" disabled={busy} onClick={() => setMode('reject')}>
              Reject…
            </button>
          )}
        </div>
      )}
      {pending && mode === 'narrow' && (
        <div className="access-approval-actions">
          <span className="access-approval-summary" role="status">{summaryText(summary)}</span>
          {blocked && <span className="access-approval-problem" role="alert">{blocked}</span>}
          <button type="button" className="access-button" onClick={() => { setChoice(initialChoice(manifest.document)); setMode('view'); }}>
            Cancel
          </button>
          <button
            type="button"
            className="access-button access-button-primary"
            disabled={busy || blocked !== null}
            onClick={() =>
              void decide(() =>
                isUnchanged(manifest.document, choice)
                  ? api.approveManifest(manifest.principal_id, manifest.sha256)
                  : api.approveManifest(manifest.principal_id, manifest.sha256, {
                      document: narrowed(manifest.document, choice),
                    }),
              )
            }
          >
            {isUnchanged(manifest.document, choice) ? 'Approve as submitted' : 'Approve narrowed'}
          </button>
        </div>
      )}
      {pending && mode === 'reject' && (
        <form
          className="access-approval-actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (reason.trim()) void decide(() => api.rejectManifest(manifest.principal_id, manifest.sha256, { reason: reason.trim() }));
          }}
        >
          <input className="access-input access-input-grow" aria-label="Reason" placeholder="Why it is rejected (the module's owner reads this)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button type="button" className="access-button" onClick={() => setMode('view')}>Cancel</button>
          <button type="submit" className="access-button access-button-primary" disabled={busy || !reason.trim()}>
            Reject manifest
          </button>
        </form>
      )}
    </article>
  );
}

function Statements({
  document,
  choice,
  onAction,
  onResource,
}: {
  document: PolicyDocument;
  choice: Choice | null;
  onAction: (index: number, action: string) => void;
  onResource: (index: number, resource: string) => void;
}) {
  return (
    <ol className="access-approval-statements">
      {document.statements.map((statement, index) => {
        const editable = choice !== null && statement.effect === 'Allow';
        return (
          <li key={index} className={`access-approval-statement access-approval-${statement.effect.toLowerCase()}`} data-effect={statement.effect}>
            <div className="access-approval-effect">
              {statement.effect}
              {statement.sid ? ` · ${statement.sid}` : ''}
              {choice !== null && statement.effect === 'Deny' && ' (stays as submitted)'}
            </div>
            <div className="access-approval-columns">
              <ItemList
                title="Actions"
                values={statement.actions}
                kept={editable ? choice[index].actions : null}
                onToggle={(v) => onAction(index, v)}
              />
              <ItemList
                title="Resources"
                values={statement.resources}
                kept={editable ? choice[index].resources : null}
                onToggle={(v) => onResource(index, v)}
              />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ItemList({
  title,
  values,
  kept,
  onToggle,
}: {
  title: string;
  values: string[];
  kept: Set<string> | null;
  onToggle: (value: string) => void;
}) {
  return (
    <div>
      <div className="access-approval-list-title">{title}</div>
      <ul className="access-approval-list">
        {values.map((value) => (
          <li key={value} className="access-mono">
            {kept ? (
              <label className="access-checkbox">
                <input type="checkbox" aria-label={value} checked={kept.has(value)} onChange={() => onToggle(value)} />
                {value}
              </label>
            ) : (
              value
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The actions a module declares under its own service: registered when the manifest is
 *  approved, as submitted (narrowing applies to the permissions above, not to these). */
function DeclaredActions({ catalog }: { catalog: DeclaredCatalog }) {
  return (
    <section className="access-approval-catalog" aria-label="Declared actions">
      <h4>
        Declares <span className="access-mono">{catalog.service}</span> (version {catalog.version}), approved as
        submitted
      </h4>
      <ul>
        {catalog.actions.map((action) => (
          <li key={action.name}>
            <span className="access-mono">
              {catalog.service}:{action.name}
            </span>{' '}
            ({action.level}, on {action.resource_types.join(', ')}){action.description ? `: ${action.description}` : ''}
          </li>
        ))}
      </ul>
    </section>
  );
}
