'use client';

import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, CornerDownRight, Pencil, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachmentView, PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import {
  AccessHeaderAction,
  ListHead,
  ListSearch,
  NameCell,
  RowActions,
  rowOpener,
  useAccessBadge,
  useListControls,
  type ListColumn,
} from '../access-list';
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

  const ownerLabel = (policy: PolicyView) => owners[policy.owner_scope ?? PLATFORM]?.label ?? '';
  const columns: ListColumn<PolicyView>[] = [
    { id: 'name', label: 'Policy', sortBy: (p) => p.name.toLowerCase(), values: (p) => [p.name] },
    { id: 'owner', label: 'Owner', sortBy: ownerLabel, values: (p) => [ownerLabel(p)] },
    {
      id: 'kind',
      label: 'Kind',
      sortBy: (p) => managedMark(p) ?? 'custom',
      values: (p) => [managedMark(p) ?? 'custom'],
    },
    {
      id: 'statements',
      label: 'Statements',
      sortBy: (p) => p.document.statements.length,
      values: (p) => [String(p.document.statements.length)],
    },
    { id: 'revision', label: 'Revision', sortBy: (p) => p.revision, values: (p) => [String(p.revision)] },
  ];
  const list = useListControls(policies, { searchText: (p) => [p.name, p.id, ownerLabel(p)], columns });
  const heldColumns: ListColumn<Held>[] = [
    { id: 'name', label: 'Policy', sortBy: (h) => h.name.toLowerCase(), values: (h) => [h.name] },
    { id: 'holders', label: 'Held by', sortBy: (h) => h.holders, values: (h) => [String(h.holders)] },
  ];
  const heldList = useListControls(held, { searchText: (h) => [h.name, h.id], columns: heldColumns });
  useAccessBadge(lists ? policies?.length ?? null : holdsOnly ? held?.length ?? null : null, 'policy', 'policies', !!next);

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

  // Searched, filtered or sorted, a flat list of what matches; else the tree.
  const rows =
    list.filtered || list.sortKey
      ? list.visible.map((policy) => ({ policy, depth: 0 }))
      : policyTree(policies);

  const nameCell = (policy: PolicyView, depth: number) => (
    <span className="access-policy-tree" style={{ paddingLeft: `${depth * 1.25}rem` }}>
      {depth > 0 && <CornerDownRight size={12} className="access-policy-tree-mark" aria-label="Sub-policy" />}
      <NameCell
        name={policy.name}
        detail={policy.id}
        badge={
          <>
            {managedMark(policy) && (
              <span
                className="platform-users-badge access-policy-badge"
                data-managed={managedMark(policy)}
                title="Managed: IAM writes this policy, read-only"
              >
                {managedMark(policy)}
              </span>
            )}
            {policy.managed_from === 'general' && (
              <span
                className="platform-users-badge access-policy-badge"
                data-managed-from="general"
                title="Set from Workspace settings › General › Features. Changed here, General shows it read-only."
              >
                managed from General
              </span>
            )}
          </>
        }
      />
      {refusals[policy.id] && (
        <p className="access-policy-error" role="alert" data-delete-refusal="">
          {refusals[policy.id]}
        </p>
      )}
    </span>
  );
  const controls = lists ? list : heldList;

  return (
    <div className="access-policies org-settings-users-main">
      {can('iam:CreatePolicy') && (
        <AccessHeaderAction>
          <button
            type="button"
            className="org-settings-primary-button"
            data-action="create-policy"
            onClick={() => select({ kind: 'new' })}
          >
            <Plus size={16} />
            Create policy
          </button>
        </AccessHeaderAction>
      )}
      {error && (
        <div className="org-settings-users-alert access-policy-error" role="alert">
          <span>{error}</span>
        </div>
      )}
      {(lists || holdsOnly) && (
        <ListSearch
          value={controls.search}
          onChange={controls.setSearch}
          placeholder="Search name, id, owner…"
          label="Search policies"
          shown={lists ? list.visible.length : heldList.visible.length}
          total={lists ? policies.length : held.length}
          noun="policy"
          plural="policies"
          filtered={controls.filtered}
          onClear={controls.clear}
        />
      )}

      {lists ? (
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table" aria-label="Policies">
            <ListHead columns={columns} controls={list} />
            <tbody>
              {rows.map(({ policy, depth }) => (
                <tr
                  key={policy.id}
                  data-policy={policy.id}
                  data-depth={depth}
                  title="Open the policy"
                  {...rowOpener(() => select({ kind: 'policy', policy }))}
                >
                  <td>{nameCell(policy, depth)}</td>
                  <td data-policy-owner="">
                    {linkTo(policy) ? (
                      <a className="access-policy-link" href={linkTo(policy)!}>
                        {ownerOfPolicy(policy)?.label}
                      </a>
                    ) : (
                      ownerOfPolicy(policy)?.label
                    )}
                  </td>
                  <td>{managedMark(policy) ?? 'custom'}</td>
                  <td>{policy.document.statements.length}</td>
                  <td>{policy.revision}</td>
                  <RowActions>
                      {confirming === policy.id ? (
                        <span className="access-policy-confirm">
                          Delete {policy.name}?{' '}
                          <button
                            type="button"
                            className="platform-users-button platform-users-button-danger"
                            onClick={() => void remove(policy)}
                          >
                            Confirm delete
                          </button>
                          <button type="button" className="platform-users-button" onClick={() => setConfirming(null)}>
                            Keep
                          </button>
                        </span>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="org-settings-users-edit"
                            data-action="open"
                            title={mayUpdate(policy) ? 'Edit' : 'Open'}
                            aria-label={`Open ${policy.name}`}
                            onClick={() => select({ kind: 'policy', policy })}
                          >
                            <Pencil size={16} />
                          </button>
                          {mayDelete(policy) && (
                            <button
                              type="button"
                              className="org-settings-users-remove"
                              title="Delete"
                              aria-label={`Delete ${policy.name}`}
                              onClick={() => setConfirming(policy.id)}
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                        </>
                      )}
                  </RowActions>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="org-settings-users-no-match">
                    {list.filtered ? 'No policies match the current search and filters.' : 'No policies.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : holdsOnly ? (
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table" aria-label="Policies held here">
            <ListHead columns={heldColumns} controls={heldList} actions={false} />
            <tbody>
              {heldList.visible.map((h) => (
                <tr
                  key={h.id}
                  data-policy={h.id}
                  data-held-by={h.holders}
                  title="Open who holds it"
                  {...rowOpener(() => void openPolicy(h.id))}
                >
                  <td>
                    <NameCell name={h.name} detail={h.id} />
                  </td>
                  <td>{h.holders}</td>
                </tr>
              ))}
              {heldList.visible.length === 0 && (
                <tr>
                  <td colSpan={2} className="org-settings-users-no-match">
                    {heldList.filtered ? 'No policies match the current search and filters.' : 'No policy is held here.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="access-policy-muted">You may create policies here, not list them.</p>
      )}
      {next && (
        <button type="button" className="org-settings-users-secondary-button" onClick={() => void more()}>
          Load more
        </button>
      )}
    </div>
  );
}
