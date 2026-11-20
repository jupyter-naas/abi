'use client';

import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, CornerDownRight, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachmentView, PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import { NEW_POLICY } from '../access-paths';
import { PLATFORM, ownerOf } from '../access-scope';
import { roleOfPolicy } from '../roles/role-change';
import { PolicyAttachments } from './policy-attachments';
import { PolicyEditor } from './policy-editor';
import { ownerHref, usePolicyOwners } from './policy-owners';
import { policyTree } from './policy-tree';
import './policies.css';

/** A policy whose page is open: being created, read, or known only by what is attached
 *  (the caller lists attachments, not policies: its holders alone, with why). */
type Selection =
  | { kind: 'new' }
  | { kind: 'policy'; policy: PolicyView }
  | { kind: 'held'; id: string; name: string; note: string | null }
  | null;

/** A policy held at the scope, as its attachments name it. */
type Held = { id: string; name: string; holders: number };

function message(error: unknown): string {
  return error instanceof IamAdminError ? error.message : error instanceof Error ? error.message : String(error);
}

/** A managed policy's mark: IAM's built-in ones (the roles among them), a module's approved
 *  manifest, or another IAM writes. */
export function managedMark(policy: Pick<PolicyView, 'id' | 'managed'>): string | null {
  if (!policy.managed) return null;
  if (policy.id.startsWith('builtin.')) return 'built-in';
  if (policy.id.startsWith('module.')) return 'module';
  return 'managed';
}

/** The policies held at the scope, from its attachments: each once, with how many hold it. */
export function heldPolicies(attachments: AttachmentView[]): Held[] {
  const found = new Map<string, Held>();
  for (const a of attachments) {
    const seen = found.get(a.policy_id);
    if (seen) seen.holders += 1;
    else found.set(a.policy_id, { id: a.policy_id, name: a.policy_name ?? a.policy_id, holders: 1 });
  }
  return [...found.values()];
}

type Props = AccessViewProps & {
  /** The policy whose page is open (its id, or `new`), from the page's address or a link. */
  focus?: string | null;
  /** Told when a policy's page opens (its id, `new`) or closes (null). */
  onFocus?: (id: string | null) => void;
};

/**
 * The policies of the scope, as a tree of parents and their sub-policies: those it owns, which
 * its admins create (with the builder, from what they may grant here, or as a sub-policy of one
 * they hold), edit and delete, and those of other levels listed here (attachable from above, or
 * every level's at the platform), the built-in roles among them. A policy opens on its own
 * page: who holds it and at which level (attached and detached there, where IAM lets the
 * caller), then its document. A policy is edited at its owner, wherever it is listed: by whoever
 * IAM lets update policies there (`GET /access?scope=<owner>`), with what they may grant there;
 * for anyone else it is read-only, naming its owner and linking to the owner's page. Managed
 * policies (built-in roles, approved module manifests) are read-only. Whoever may create
 * policies here and not list them still builds one; whoever may list the attachments and not
 * the policies sees the policies held here and who holds each.
 */
export function PoliciesView({ api, can, scope, directory, nonce = 0, open, focus = null, onFocus }: Props) {
  const lists = can('iam:ListPolicies');
  const holdsOnly = !lists && can('iam:ListAttachments');
  const [policies, setPolicies] = useState<PolicyView[] | null>(lists ? null : []);
  const [held, setHeld] = useState<Held[] | null>(holdsOnly ? null : []);
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
    nonce,
  );

  const select = (next: Selection) => {
    setSelection(next);
    onFocus?.(next === null ? null : next.kind === 'new' ? NEW_POLICY : next.kind === 'policy' ? next.policy.id : next.id);
  };

  const load = useCallback(async () => {
    try {
      if (lists) {
        const page = await api.listPolicies(undefined, listedAt);
        setPolicies(page.items);
        setNext(page.next_after);
      } else if (holdsOnly) {
        const found = await api.listAttachments(scope.value ? { scope: scope.value } : {});
        setHeld(heldPolicies(found.items.filter((a) => a.scope === scope.value)));
      }
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, listedAt, lists, holdsOnly, scope]);

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
      await load();
    } catch (e) {
      setRefusals((current) => ({ ...current, [policy.id]: message(e) }));
      setConfirming(null);
    }
  };

  /** A policy's page, opened from the list, the editor (a parent, a sub-policy) or a link: as
   *  listed, else read by its id; one the caller may not read shows its holders alone. */
  const resolve = async (id: string): Promise<Selection> => {
    const listed = policies?.find((p) => p.id === id);
    if (listed) return { kind: 'policy', policy: listed };
    try {
      return { kind: 'policy', policy: await api.getPolicy(id) };
    } catch (e) {
      if (!can('iam:ListAttachments')) throw e;
      const known = held?.find((h) => h.id === id);
      return { kind: 'held', id, name: known?.name ?? id, note: lists ? message(e) : null };
    }
  };
  const openPolicy = async (id: string) => {
    try {
      select(await resolve(id));
    } catch (e) {
      setError(message(e));
    }
  };

  // The address names a policy to open (or a new one): once, when the list is read.
  const [opened, setOpened] = useState(false);
  useEffect(() => {
    if (!focus || opened || policies === null || held === null) return;
    setOpened(true);
    if (focus === NEW_POLICY) {
      if (can('iam:CreatePolicy')) setSelection({ kind: 'new' });
      return;
    }
    resolve(focus).then(setSelection, (e: unknown) => setError(message(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, opened, policies, held]);

  if (error && (policies === null || held === null)) return <p className="access-policy-error" role="alert">{error}</p>;
  if (policies === null || held === null) return <p className="access-empty">Loading…</p>;

  // What the caller may do with a policy: IAM's answer at its owner (this level's is ``can``).
  const ownerOfPolicy = (policy: PolicyView) => owners[policy.owner_scope ?? PLATFORM];
  const mayUpdate = (policy: PolicyView) => !policy.managed && !!ownerOfPolicy(policy)?.canUpdate;
  const mayDelete = (policy: PolicyView) => !policy.managed && !!ownerOfPolicy(policy)?.canDelete;
  const linkTo = (policy: PolicyView) => {
    const owner = ownerOfPolicy(policy);
    return owner?.opens ? ownerHref(owner.scope, policy.id) : null;
  };

  if (selection) {
    return (
      <div className="access-policy-page" data-policy-page={selection.kind === 'new' ? NEW_POLICY : selection.kind === 'policy' ? selection.policy.id : selection.id}>
        <button type="button" className="access-policy-back" onClick={() => select(null)}>
          <ArrowLeft size={14} /> Policies
        </button>
        {error && <p className="access-policy-error" role="alert">{error}</p>}
        {selection.kind === 'held' ? (
          <section className="access-policy-editor" aria-label={`Policy ${selection.name}`}>
            <header className="access-policy-editor-header">
              <h3 className="access-policy-title">{selection.name}</h3>
              <code className="access-policy-id">{selection.id}</code>
            </header>
            <p className="access-policy-muted" data-policy-unread="">
              {selection.note ?? 'You may list who holds this policy here, not read what it allows.'}
            </p>
            <PolicyAttachments api={api} policyId={selection.id} here={here} can={can} open={open} nonce={nonce} scope={scope} directory={directory} />
          </section>
        ) : (
          <PolicyEditor
            key={selection.kind === 'new' ? NEW_POLICY : `${selection.policy.id}@${selection.policy.revision}`}
            api={api}
            policy={selection.kind === 'policy' ? selection.policy : null}
            scope={scope}
            directory={directory}
            roles={policies.filter((p) => roleOfPolicy(p.id))}
            parents={policies}
            readOnly={selection.kind === 'policy' && !mayUpdate(selection.policy)}
            owner={selection.kind === 'policy' ? ownerOfPolicy(selection.policy) ?? null : null}
            ownerLink={selection.kind === 'policy' ? linkTo(selection.policy) : null}
            onSaved={(saved) => {
              select({ kind: 'policy', policy: saved });
              void load();
            }}
            onCancel={() => select(null)}
            onOpen={(id) => void openPolicy(id)}
            can={can}
            open={open}
            nonce={nonce}
          />
        )}
      </div>
    );
  }

  const wanted = filter.trim().toLowerCase();
  // Filtered, a flat list of what matches; else the tree.
  const rows = wanted
    ? policies.filter((p) => `${p.name} ${p.id}`.toLowerCase().includes(wanted)).map((policy) => ({ policy, depth: 0 }))
    : policyTree(policies);
  const heldRows = held.filter((h) => !wanted || `${h.name} ${h.id}`.toLowerCase().includes(wanted));

  return (
    <div className="access-policies">
      <div className="access-policy-toolbar">
        {(lists || holdsOnly) && (
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
            onClick={() => select({ kind: 'new' })}
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
                      onClick={() => select({ kind: 'policy', policy })}
                    >
                      {policy.name}
                    </button>
                    {managedMark(policy) && (
                      <span
                        className="access-policy-badge"
                        data-managed={managedMark(policy)}
                        title="Managed: IAM writes this policy, read-only"
                      >
                        {managedMark(policy)}
                      </span>
                    )}
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
      ) : holdsOnly ? (
        <table className="access-policy-table" aria-label="Policies held here">
          <thead>
            <tr>
              <th>Name</th>
              <th>Id</th>
              <th>Held by</th>
            </tr>
          </thead>
          <tbody>
            {heldRows.map((h) => (
              <tr key={h.id} data-policy={h.id} data-held-by={h.holders}>
                <td>
                  <button type="button" className="access-policy-link" onClick={() => void openPolicy(h.id)}>
                    {h.name}
                  </button>
                </td>
                <td>
                  <code>{h.id}</code>
                </td>
                <td>{h.holders}</td>
              </tr>
            ))}
            {heldRows.length === 0 && (
              <tr>
                <td colSpan={3} className="access-policy-muted">
                  {filter ? 'No policies match.' : 'No policy is held here.'}
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
    </div>
  );
}
