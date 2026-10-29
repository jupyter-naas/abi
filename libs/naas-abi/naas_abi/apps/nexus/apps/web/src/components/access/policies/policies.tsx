'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import { FEATURE_LABELS } from '@/lib/feature-labels';
import { useWorkspaceStore } from '@/stores/workspace';
import type { CatalogsView, ModuleScopesView, PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import { PLATFORM, ownedHere, ownerOf, type AccessScope } from '../access-scope';
import { scopeLabel } from '../attachments/attachments-model';
import { roleOfPolicy } from '../roles/role-change';
import { builderGroups, type BuilderGroup } from './builder/builder-model';
import { PolicyEditor } from './policy-editor';
import './policies.css';

type Selection = { kind: 'new' } | { kind: 'policy'; policy: PolicyView } | null;

function message(error: unknown): string {
  return error instanceof IamAdminError ? error.message : error instanceof Error ? error.message : String(error);
}

/** Where the module scopes are listed for this scope: its workspace or org, or, at the
 *  platform, the workspace the user is in (platform admins hold it in every one). */
function moduleScopesAt(scope: AccessScope, currentWorkspace: string | undefined) {
  if (scope.workspaceId) return { workspace_id: scope.workspaceId };
  if (scope.organizationId) return { organization_id: scope.organizationId };
  return currentWorkspace ? { workspace_id: currentWorkspace } : null;
}

/**
 * The policies of the scope: those it owns, which its admins create (with the builder, from
 * what they may grant here), edit and delete, and those of higher levels that may be attached
 * here, read-only. Managed policies (built-in roles, approved module manifests) are read-only.
 */
export function PoliciesView({ api, can, scope, nonce = 0 }: AccessViewProps) {
  const [policies, setPolicies] = useState<PolicyView[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalogs, setCatalogs] = useState<CatalogsView | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [modules, setModules] = useState<ModuleScopesView | null>(null);
  const [builder, setBuilder] = useState<BuilderGroup[] | null>(null);
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspaceId) ?? undefined;
  const [selection, setSelection] = useState<Selection>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const writes = can('iam:CreatePolicy') || can('iam:UpdatePolicy');
  const listedAt = scope.value ?? undefined;

  const load = useCallback(async () => {
    try {
      const page = await api.listPolicies(undefined, listedAt);
      setPolicies(page.items);
      setNext(page.next_after);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, listedAt]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  useEffect(() => {
    api
      .catalogs(listedAt)
      .then(setCatalogs)
      .catch((e) => setCatalogError(message(e)));
  }, [api, listedAt]);

  // The builder: what the caller may grant here, named with what the modules expose. Without
  // the module listing it still offers the features; without `grantable`, no builder.
  const where = moduleScopesAt(scope, currentWorkspace);
  const whereKey = JSON.stringify(where);
  useEffect(() => {
    if (!writes) return;
    let cancelled = false;
    const listing = where ? api.moduleScopes(where).catch(() => null) : Promise.resolve(null);
    Promise.all([api.grantable(ownerOf(scope)), listing])
      .then(([grantable, found]) => {
        if (cancelled) return;
        setModules(found);
        setBuilder(builderGroups(grantable, found?.modules ?? [], Object.keys(FEATURE_LABELS)));
      })
      .catch(() => !cancelled && setBuilder(null));
    return () => {
      cancelled = true;
    };
    // `where` is read through its key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, scope, writes, whereKey]);

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
      if (selection?.kind === 'policy' && selection.policy.id === policy.id) setSelection(null);
      await load();
    } catch (e) {
      setError(message(e));
      setConfirming(null);
    }
  };

  if (error && policies === null) return <p className="access-policy-error" role="alert">{error}</p>;
  if (policies === null) return <p className="access-empty">Loading…</p>;

  const shown = policies.filter((p) =>
    `${p.name} ${p.id}`.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  // A policy owned above this scope is attached here, never changed here.
  const editable = (policy: PolicyView) => !policy.managed && ownedHere(scope, policy.owner_scope);

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
            <th>Owner</th>
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
              </td>
            </tr>
          ))}
          {shown.length === 0 && (
            <tr>
              <td colSpan={6} className="access-policy-muted">
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
          modules={modules}
          builder={builder}
          scope={scope}
          roles={policies.filter((p) => roleOfPolicy(p.id))}
          readOnly={selection.kind === 'policy' && (!editable(selection.policy) || !can('iam:UpdatePolicy'))}
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
