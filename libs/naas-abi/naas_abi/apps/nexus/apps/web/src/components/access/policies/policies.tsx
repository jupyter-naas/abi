'use client';

import { useCallback, useEffect, useState } from 'react';
import { CornerDownRight, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import { PLATFORM, ownerOf } from '../access-scope';
import { roleOfPolicy } from '../roles/role-change';
import { PolicyEditor } from './policy-editor';
import { ownerHref, usePolicyOwners } from './policy-owners';
import { policyTree } from './policy-tree';
import './policies.css';

type Selection = { kind: 'new' } | { kind: 'policy'; policy: PolicyView } | null;

function message(error: unknown): string {
  return error instanceof IamAdminError ? error.message : error instanceof Error ? error.message : String(error);
}

/**
 * The policies of the scope, as a tree of parents and their sub-policies: those it owns, which
 * its admins create (with the builder, from what they may grant here, or as a sub-policy of one
 * they hold), edit and delete, and those of other levels listed here (attachable from above, or
 * every level's at the platform). A policy is edited at its owner, wherever it is listed: by
 * whoever IAM lets update policies there (`GET /access?scope=<owner>`), with what they may grant
 * there; for anyone else it is read-only, naming its owner and linking to the owner's page.
 * Managed policies (built-in roles, approved module manifests) are read-only. Whoever may create
 * policies here and not list them still builds one. ``openPolicy`` opens one by its id once the
 * list is read (a link from another level's page).
 */
export function PoliciesView({ api, can, scope, nonce = 0, open, openPolicy: opening }: AccessViewProps & { openPolicy?: string | null }) {
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
  const here = ownerOf(scope);
  // The listed policies' owners, and that of one opened by its id (a parent, a link).
  const owners = usePolicyOwners(
    api,
    [...(policies ?? []), ...(selection?.kind === 'policy' ? [selection.policy] : [])].map((p) => p.owner_scope),
    here,
    can,
  );

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

  // A link names a policy to open: once, when the list is read.
  const [opened, setOpened] = useState(false);
  useEffect(() => {
    if (!opening || opened || policies === null) return;
    setOpened(true);
    void openPolicy(opening);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opening, opened, policies]);

  if (error && policies === null) return <p className="access-policy-error" role="alert">{error}</p>;
  if (policies === null) return <p className="access-empty">Loading…</p>;

  const wanted = filter.trim().toLowerCase();
  // Filtered, a flat list of what matches; else the tree.
  const rows = wanted
    ? policies.filter((p) => `${p.name} ${p.id}`.toLowerCase().includes(wanted)).map((policy) => ({ policy, depth: 0 }))
    : policyTree(policies);
  // What the caller may do with a policy: IAM's answer at its owner (this level's is ``can``).
  const ownerOfPolicy = (policy: PolicyView) => owners[policy.owner_scope ?? PLATFORM];
  const mayUpdate = (policy: PolicyView) => !policy.managed && !!ownerOfPolicy(policy)?.canUpdate;
  const mayDelete = (policy: PolicyView) => !policy.managed && !!ownerOfPolicy(policy)?.canDelete;
  const linkTo = (policy: PolicyView) => {
    const owner = ownerOfPolicy(policy);
    return owner?.opens ? ownerHref(owner.scope, policy.id) : null;
  };

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
                <td data-policy-owner="">
                  {linkTo(policy) ? (
                    <a className="access-policy-link" href={linkTo(policy)!}>
                      {ownerOfPolicy(policy)?.label}
                    </a>
                  ) : (
                    ownerOfPolicy(policy)?.label
                  )}
                </td>
                <td>{policy.document.statements.length}</td>
                <td>{policy.revision}</td>
                <td className="access-policy-row-actions">
                  {mayDelete(policy) && (
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
          readOnly={selection.kind === 'policy' && !mayUpdate(selection.policy)}
          owner={selection.kind === 'policy' ? ownerOfPolicy(selection.policy) ?? null : null}
          ownerLink={selection.kind === 'policy' ? linkTo(selection.policy) : null}
          onSaved={(saved) => {
            setSelection({ kind: 'policy', policy: saved });
            void load();
          }}
          onCancel={() => setSelection(null)}
          onOpen={(id) => void openPolicy(id)}
          can={can}
          open={open}
        />
      )}
    </div>
  );
}
