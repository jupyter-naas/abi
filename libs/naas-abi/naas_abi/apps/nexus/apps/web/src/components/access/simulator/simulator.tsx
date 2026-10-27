'use client';

import { useEffect, useId, useMemo, useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import type { CatalogsView, PrincipalView, Simulation } from '@/lib/iam-admin/types';
import { principalLabel } from '../attachments/attachments-model';
import type { PlatformViewProps } from '../access-props';
import { suggestActions, suggestResources } from '../policies/policy-editor-model';
import { SuggestInput } from '../policies/suggest-input';
import '../policies/policies.css';
import './simulator.css';
import { headline, reasonText, statementFacts } from './simulator-model';

/** "Can X do Y on Z?": asks IAM to explain the decision for a principal and shows the
 *  statement that decided it. */
export function SimulatorView({ api }: PlatformViewProps) {
  const [principals, setPrincipals] = useState<PrincipalView[]>([]);
  const [catalogs, setCatalogs] = useState<CatalogsView | null>(null);
  const [principalId, setPrincipalId] = useState('');
  const [action, setAction] = useState('');
  const [resource, setResource] = useState('');
  const [result, setResult] = useState<Simulation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const listId = useId();

  useEffect(() => {
    api
      .listPrincipals()
      .then((page) => setPrincipals(page.items.filter((p) => p.kind !== 'group')))
      .catch(() => setPrincipals([]));
    api
      .catalogs()
      .then(setCatalogs)
      .catch(() => setCatalogs(null));
  }, [api]);

  const actionSuggestions = useMemo(
    () => suggestActions(action, catalogs?.catalogs ?? []),
    [action, catalogs],
  );
  const resourceSuggestions = useMemo(
    () => suggestResources(resource, { catalogs, actions: action.trim() ? [action.trim()] : [] }),
    [resource, catalogs, action],
  );

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      setResult(
        await api.simulate({ principal_id: principalId.trim(), action: action.trim(), resource: resource.trim() }),
      );
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const ready = principalId.trim() !== '' && action.trim() !== '' && resource.trim() !== '';

  return (
    <div className="access-sim">
      <form
        className="access-sim-form"
        aria-label="Access simulator"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) void run();
        }}
      >
        <label className="access-policy-field">
          <span>Can this principal…</span>
          <input
            type="text"
            className="access-policy-input"
            aria-label="Principal"
            list={listId}
            autoComplete="off"
            placeholder="User or service account id"
            value={principalId}
            onChange={(event) => setPrincipalId(event.target.value)}
          />
          <datalist id={listId}>
            {principals.map((p) => (
              <option key={p.id} value={p.id}>
                {principalLabel(p, p.id)} ({p.kind.replace('_', ' ')})
              </option>
            ))}
          </datalist>
        </label>
        <div className="access-policy-field">
          <span>…do this action…</span>
          <SuggestInput
            label="Action"
            value={action}
            onChange={setAction}
            suggestions={actionSuggestions}
            onPick={(s) => setAction(s.value)}
            placeholder="service:Action, e.g. triple_store:Query"
          />
        </div>
        <div className="access-policy-field">
          <span>…on this resource?</span>
          <SuggestInput
            label="Resource"
            value={resource}
            onChange={setResource}
            suggestions={resourceSuggestions}
            onPick={(s) => setResource(s.value)}
            placeholder="abi:<org>:<workspace>:<service>:<type>/<id>"
          />
        </div>
        <button type="submit" className="access-policy-button access-policy-button-primary" disabled={!ready || running}>
          {running ? 'Asking IAM…' : 'Simulate'}
        </button>
      </form>

      {error && (
        <p className="access-policy-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <section
          className={result.allowed ? 'access-sim-result access-sim-allowed' : 'access-sim-result access-sim-denied'}
          aria-label="Decision"
        >
          <h3 className="access-sim-headline">
            {result.allowed ? <CheckCircle2 size={18} /> : <XCircle size={18} />} {headline(result)}
          </h3>
          <p className="access-sim-sentence">
            <strong>{principalLabel(result.principal, result.principal.id)}</strong>{' '}
            {result.allowed ? 'may' : 'may not'} <code>{result.action}</code> on <code>{result.resource}</code>.
          </p>
          <p className="access-sim-reason">{reasonText(result.reason)}</p>
          {result.statement ? (
            <div className="access-sim-statement" aria-label="Deciding statement">
              <h4 className="access-sim-subtitle">Deciding statement</h4>
              <dl className="access-sim-facts">
                {statementFacts(result.statement).map((fact) => (
                  <div key={fact.label}>
                    <dt>{fact.label}</dt>
                    <dd>{fact.value}</dd>
                  </div>
                ))}
              </dl>
              {result.statement.statement && (
                <pre className="access-sim-json">{JSON.stringify(result.statement.statement, null, 2)}</pre>
              )}
            </div>
          ) : (
            <p className="access-policy-muted">No statement decided this: nothing names it.</p>
          )}
        </section>
      )}
    </div>
  );
}
