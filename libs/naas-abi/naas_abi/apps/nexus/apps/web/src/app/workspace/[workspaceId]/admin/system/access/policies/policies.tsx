'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { CatalogsView, PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import { PolicyEditor } from './policy-editor';
import './policies.css';

type Selection = { kind: 'new' } | { kind: 'policy'; policy: PolicyView } | null;

function message(error: unknown): string {
  return error instanceof IamAdminError ? error.message : error instanceof Error ? error.message : String(error);
}

/** The platform's policies: list, create, edit (visual or text, validated by IAM) and delete.
 *  Managed policies (built-in roles, approved module manifests) are read-only. */
export function PoliciesView({ api, can, nonce = 0 }: AccessViewProps) {
  const [policies, setPolicies] = useState<PolicyView[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalogs, setCatalogs] = useState<CatalogsView | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    try {
      const page = await api.listPolicies();
      setPolicies(page.items);
      setNext(page.next_after);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  useEffect(() => {
    api
      .catalogs()
      .then(setCatalogs)
      .catch((e) => setCatalogError(message(e)));
  }, [api]);

  const more = async () => {
    if (!next) return;
    try {
      const page = await api.listPolicies(next);
      setPolicies((current) => [...(current ?? []), ...page.items]);
      setNext(page.next_after);
    } catch (e) {
      setError(message(e));
    }
  };

  const remove = async (policy: PolicyView) => {
    try {
      await api.deletePolicy(policy.id);
      setConfirming(null);
      if (selection?.kind === 'policy' && selection.policy.id === policy.id) setSelection(null);
      await load();
    } catch (e) {
      setError(message(e));
      setConfirming(null);
    }
  };

  if (error && policies === null) return <p className="access-policy-error" role="alert">{error}</p>;
  if (policies === null) return <p className="system-empty">Loading…</p>;

  const shown = policies.filter((p) =>
    `${p.name} ${p.id}`.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  return (
    <div className="access-policies">
      <div className="access-policy-toolbar">
        <input
          type="search"
          className="access-policy-input"
          aria-label="Filter policies"
          placeholder="Filter policies"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        {can('iam:CreatePolicy') && (
          <button
            type="button"
            className="access-policy-button access-policy-button-primary"
            onClick={() => setSelection({ kind: 'new' })}
          >
            <Plus size={14} /> New policy
          </button>
        )}
      </div>
      {error && <p className="access-policy-error" role="alert">{error}</p>}
      {catalogError && (
        <p className="access-policy-notice" role="status">
          Autocomplete is unavailable: {catalogError}
        </p>
      )}

      <table className="access-policy-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Id</th>
            <th>Statements</th>
            <th>Revision</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {shown.map((policy) => (
            <tr key={policy.id} data-policy={policy.id}>
              <td>
                <button
                  type="button"
                  className="access-policy-link"
                  onClick={() => setSelection({ kind: 'policy', policy })}
                >
                  {policy.name}
                </button>
                {policy.managed && <span className="access-policy-badge">managed</span>}
              </td>
              <td>
                <code>{policy.id}</code>
              </td>
              <td>{policy.document.statements.length}</td>
              <td>{policy.revision}</td>
              <td className="access-policy-row-actions">
                {!policy.managed && can('iam:DeletePolicy') && (
                  confirming === policy.id ? (
                    <span className="access-policy-confirm">
                      Delete {policy.name}?{' '}
                      <button type="button" className="access-policy-button access-policy-button-danger" onClick={() => void remove(policy)}>
                        Confirm delete
                      </button>
                      <button type="button" className="access-policy-button" onClick={() => setConfirming(null)}>
                        Keep
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="access-policy-icon-button"
                      aria-label={`Delete ${policy.name}`}
                      onClick={() => setConfirming(policy.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  )
                )}
              </td>
            </tr>
          ))}
          {shown.length === 0 && (
            <tr>
              <td colSpan={5} className="access-policy-muted">
                No policies{filter ? ' match' : ''}.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {next && (
        <button type="button" className="access-policy-button" onClick={() => void more()}>
          Load more
        </button>
      )}

      {selection && (
        <PolicyEditor
          key={selection.kind === 'new' ? 'new' : `${selection.policy.id}@${selection.policy.revision}`}
          api={api}
          policy={selection.kind === 'policy' ? selection.policy : null}
          catalogs={catalogs}
          readOnly={selection.kind === 'policy' && (selection.policy.managed || !can('iam:UpdatePolicy'))}
          onSaved={(saved) => {
            setSelection({ kind: 'policy', policy: saved });
            void load();
          }}
          onCancel={() => setSelection(null)}
        />
      )}
    </div>
  );
}
