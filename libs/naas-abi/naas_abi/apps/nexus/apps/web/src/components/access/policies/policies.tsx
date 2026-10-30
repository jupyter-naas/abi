'use client';

import { useCallback, useEffect, useState } from 'react';
import { CornerDownRight, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import { PLATFORM, ownedHere } from '../access-scope';
import { scopeLabel } from '../attachments/attachments-model';
import { roleOfPolicy } from '../roles/role-change';
import { PolicyEditor } from './policy-editor';
import { policyTree } from './policy-tree';
import './policies.css';

type Selection = { kind: 'new' } | { kind: 'policy'; policy: PolicyView } | null;

function message(error: unknown): string {
  return error instanceof IamAdminError ? error.message : error instanceof Error ? error.message : String(error);
}

/**
 * The policies of the scope, as a tree of parents and their sub-policies: those it owns, which
 * its admins create (with the builder, from what they may grant here, or as a sub-policy of one
 * they hold), edit and delete, and those of higher levels that may be attached here, read-only.
 * Managed policies (built-in roles, approved module manifests) are read-only. Whoever may create
 * policies here and not list them still builds one.
 */
export function PoliciesView({ api, can, scope, nonce = 0 }: AccessViewProps) {
  const lists = can('iam:ListPolicies');
  const [policies, setPolicies] = useState<PolicyView[] | null>(lists ? null : []);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  // IAM's refusal of a delete (a parent with sub-policies), shown at its row.
  const [refusals, setRefusals] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState('');
  const listedAt = scope.value ?? undefined;

  const load = useCallback(async () => {
    if (!lists) return;
    try {
      const page = await api.listPolicies(undefined, listedAt);
      setPolicies(page.items);
      setNext(page.next_after);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, listedAt, lists]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const more = async () => {
    if (!next) return;
    try {
      const page = await api.listPolicies(next, listedAt);
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
      setRefusals(({ [policy.id]: _gone, ...rest }) => rest);
      if (selection?.kind === 'policy' && selection.policy.id === policy.id) setSelection(null);
      await load();
    } catch (e) {
      setRefusals((current) => ({ ...current, [policy.id]: message(e) }));
      setConfirming(null);
    }
  };

  /** A parent or a sub-policy, opened from the editor: as listed, else read by its id. */
  const openPolicy = async (id: string) => {
    const listed = policies?.find((p) => p.id === id);
    if (listed) {
      setSelection({ kind: 'policy', policy: listed });
      return;
    }
    try {
      setSelection({ kind: 'policy', policy: await api.getPolicy(id) });
    } catch (e) {
      setError(message(e));
    }
  };

  if (error && policies === null) return <p className="access-policy-error" role="alert">{error}</p>;
  if (policies === null) return <p className="access-empty">Loading…</p>;

  const wanted = filter.trim().toLowerCase();
  // Filtered, a flat list of what matches; else the tree.
  const rows = wanted
    ? policies.filter((p) => `${p.name} ${p.id}`.toLowerCase().includes(wanted)).map((policy) => ({ policy, depth: 0 }))
    : policyTree(policies);
  // A policy owned above this scope is attached here, never changed here.
  const editable = (policy: PolicyView) => !policy.managed && ownedHere(scope, policy.owner_scope);

  return (
    <div className="access-policies">
      <div className="access-policy-toolbar">
        {lists && (
          <input
            type="search"
            className="access-policy-input"
            aria-label="Filter policies"
            placeholder="Filter policies"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        )}
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

      {lists ? (
        <table className="access-policy-table" aria-label="Policies">
          <thead>
            <tr>
              <th>Name</th>
              <th>Id</th>
              <th>Owner</th>
              <th>Statements</th>
              <th>Revision</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {rows.map(({ policy, depth }) => (
              <tr key={policy.id} data-policy={policy.id} data-depth={depth}>
                <td>
                  <span className="access-policy-tree" style={{ paddingLeft: `${depth * 1.25}rem` }}>
                    {depth > 0 && <CornerDownRight size={12} className="access-policy-tree-mark" aria-label="Sub-policy" />}
                    <button
                      type="button"
                      className="access-policy-link"
                      onClick={() => setSelection({ kind: 'policy', policy })}
                    >
                      {policy.name}
                    </button>
                    {policy.managed && <span className="access-policy-badge">managed</span>}
                  </span>
                </td>
                <td>
                  <code>{policy.id}</code>
                </td>
                <td>{scopeLabel(policy.owner_scope ?? PLATFORM)}</td>
                <td>{policy.document.statements.length}</td>
                <td>{policy.revision}</td>
                <td className="access-policy-row-actions">
                  {editable(policy) && can('iam:DeletePolicy') && (
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
                  {refusals[policy.id] && (
                    <p className="access-policy-error" role="alert" data-delete-refusal="">
                      {refusals[policy.id]}
                    </p>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="access-policy-muted">
                  No policies{filter ? ' match' : ''}.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      ) : (
        <p className="access-policy-muted">You may create policies here, not list them.</p>
      )}
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
          scope={scope}
          roles={policies.filter((p) => roleOfPolicy(p.id))}
          parents={policies}
          readOnly={selection.kind === 'policy' && (!editable(selection.policy) || !can('iam:UpdatePolicy'))}
          onSaved={(saved) => {
            setSelection({ kind: 'policy', policy: saved });
            void load();
          }}
          onCancel={() => setSelection(null)}
          onOpen={(id) => void openPolicy(id)}
        />
      )}
    </div>
  );
}
