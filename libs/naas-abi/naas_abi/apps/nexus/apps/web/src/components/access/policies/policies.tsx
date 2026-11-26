'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowLeft, CornerDownRight, Pencil, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachmentView, PolicyView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import {
  AccessHeaderAction,
  AccessHeaderSlotContext,
  useAccessInstance,
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
import { PLATFORM, ownerOf, parseScope } from '../access-scope';
import { listedOnPolicies } from '../builtins';
import { WorkspaceOfferEditor } from '../offer/offer-editor';
import { roleOfPolicy } from '../roles/role-change';
import { levelPolicyOf, workspaceGroupName } from '@/lib/access-model/levels';
import { PolicyAttachments } from './policy-attachments';
import { PolicyEditor } from './policy-editor';
import { InstanceHeader } from '../instance-header';
import { ownerHref, usePolicyOwners } from './policy-owners';
import { policyTree } from './policy-tree';
import { TablePager, usePagedRows } from '@/components/settings/users-table/table-pager';
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

/** The workspace a policy is "<W> access" of: its owner is a workspace's container and its name
 *  "<label> access" (`container_defaults`); the offer editor checks the id against `/offer`. */
export function offerWorkspaceOf(policy: Pick<PolicyView, 'name' | 'owner_scope'>): string | null {
  const parsed = parseScope(policy.owner_scope);
  const last = parsed && !parsed.below ? parsed.containers[parsed.containers.length - 1] : null;
  if (!last || last.service !== 'nexus' || last.type !== 'workspace') return null;
  return policy.name.endsWith(' access') ? last.id : null;
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
  // A page of them shows at once; the others follow in the background (`next`: more to come).
  const [next, setNext] = useState<string | null>(null);
  const reading = useRef(0);
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

  // The focus a Back click leaves: the address still names it a moment, the list shows already.
  const [leaving, setLeaving] = useState<string | null>(null);
  const select = (next: Selection) => {
    setLeaving(next === null ? focus : null);
    setSelection(next);
    onFocus?.(next === null ? null : next.kind === 'new' ? NEW_POLICY : next.kind === 'policy' ? next.policy.id : next.id);
  };

  const load = useCallback(async () => {
    const mine = ++reading.current;
    try {
      if (lists) {
        let page = await api.listPolicies(undefined, listedAt);
        // The automatic platform access and the service accounts' are not listed here.
        let found = page.items.filter(listedOnPolicies);
        if (reading.current !== mine) return;
        setPolicies(found);
        setNext(page.next_after);
        setError(null);
        // The other pages follow, so that the search and the filters reach every policy.
        while (page.next_after) {
          page = await api.listPolicies(page.next_after, listedAt);
          if (reading.current !== mine) return;
          found = [...found, ...page.items.filter(listedOnPolicies)];
          setPolicies(found);
          setNext(page.next_after);
        }
      } else if (holdsOnly) {
        const found = await api.listAttachments(scope.value ? { scope: scope.value } : {});
        setHeld(heldPolicies(found.items.filter((a) => a.scope === scope.value)).filter(listedOnPolicies));
      }
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, listedAt, lists, holdsOnly, scope]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

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

  // The page follows its address (the list and a policy's page are one view, kept mounted): a
  // policy listed opens as listed, at once; another is read by its id, without waiting for the
  // list. A new one waits for IAM to let the caller create here: Create policy changes the
  // address, and the page knows its rights a moment later. No policy named: the list.
  const mayCreate = can('iam:CreatePolicy');
  const shown =
    selection === null ? null : selection.kind === 'new' ? NEW_POLICY : selection.kind === 'policy' ? selection.policy.id : selection.id;
  const resolving = useRef<string | null>(null);
  // The address left the policy (a back link, the browser's Back): the list again. A view whose
  // address never names one (a test, a page shown alone) keeps what a click opened.
  const lastFocus = useRef(focus);
  useEffect(() => {
    const left = lastFocus.current !== null && focus === null;
    lastFocus.current = focus;
    if (left) {
      resolving.current = null;
      setSelection(null);
      setLeaving(null);
    }
  }, [focus]);
  useEffect(() => {
    if (!focus || focus === shown) return;
    if (focus === NEW_POLICY) {
      if (mayCreate) setSelection({ kind: 'new' });
      return;
    }
    const listed = policies?.find((p) => p.id === focus);
    if (listed) {
      resolving.current = null;
      setSelection({ kind: 'policy', policy: listed });
      return;
    }
    if (resolving.current === focus) return;
    resolving.current = focus;
    if (lists && policies === null) {
      // The list is still read: the policy by its id at once; if it cannot be read so, the list
      // decides when it comes (listed, or read again and else shown by its holders).
      api.getPolicy(focus).then(
        (policy) => resolving.current === focus && setSelection((current) => current ?? { kind: 'policy', policy }),
        () => {
          if (resolving.current === focus) resolving.current = null;
        }
      );
      return;
    }
    resolve(focus).then(
      (found) => resolving.current === focus && setSelection(found),
      (e: unknown) => setError(message(e))
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, shown, policies, mayCreate]);

  // A policy's page shown, or about to be (its address names it): the level hides the list's header.
  useAccessInstance(selection !== null || (!!focus && focus !== leaving));

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
  // Searched, filtered or sorted, a flat list of what matches; else the tree. A page of it.
  const rows = useMemo(
    () =>
      policies === null
        ? []
        : list.filtered || list.sortKey
          ? list.visible.map((policy) => ({ policy, depth: 0 }))
          : policyTree(policies),
    [policies, list.filtered, list.sortKey, list.visible]
  );
  const paged = usePagedRows(rows, list.pageKey);
  const heldPaged = usePagedRows(heldList.visible, heldList.pageKey);

  // What the caller may do with a policy: IAM's answer at its owner (this level's is ``can``).
  const ownerOfPolicy = (policy: PolicyView) => owners[policy.owner_scope ?? PLATFORM];
  // A generic level policy is written once for every workspace: read-only here (S2).
  const mayUpdate = (policy: PolicyView) =>
    !policy.managed && !levelPolicyOf(policy) && !!ownerOfPolicy(policy)?.canUpdate;
  const mayDelete = (policy: PolicyView) =>
    !policy.managed && !levelPolicyOf(policy) && !!ownerOfPolicy(policy)?.canDelete;
  const linkTo = (policy: PolicyView) => {
    const owner = ownerOfPolicy(policy);
    return owner?.opens ? ownerHref(owner.scope, policy.id) : null;
  };

  if (selection) {
    return (
      <div className="access-policy-page access-instance-page" data-policy-page={selection.kind === 'new' ? NEW_POLICY : selection.kind === 'policy' ? selection.policy.id : selection.id}>
        <button type="button" className="access-policy-back" onClick={() => select(null)}>
          <ArrowLeft size={14} /> Policies
        </button>
        {error && <p className="access-policy-error" role="alert">{error}</p>}
        {selection.kind === 'held' ? (
          <HeldPolicySection name={selection.name} id={selection.id}>
            <p className="access-policy-muted" data-policy-unread="">
              {selection.note ?? 'You may list who holds this policy here, not read what it allows.'}
            </p>
            <PolicyAttachments api={api} policyId={selection.id} here={here} can={can} open={open} nonce={nonce} scope={scope} directory={directory} />
          </HeldPolicySection>
        ) : (
          <>
          {selection.kind === 'policy' && levelPolicyOf(selection.policy) && (
            <section className="access-policy-level" data-level-summary={levelPolicyOf(selection.policy)!.level}>
              <h3 className="access-policy-title">What {selection.policy.name} grants</h3>
              <p className="access-policy-muted">{levelPolicyOf(selection.policy)!.summary}</p>
              <p className="access-policy-muted">
                A generic level policy, written once and held by its level group: it applies only in the workspaces
                each person belongs to. Read-only.
              </p>
            </section>
          )}
          <PolicyEditor
            key={selection.kind === 'new' ? NEW_POLICY : `${selection.policy.id}@${selection.policy.revision}`}
            api={api}
            policy={selection.kind === 'policy' ? selection.policy : null}
            scope={scope}
            directory={directory}
            roles={(policies ?? []).filter((p) => roleOfPolicy(p.id))}
            parents={policies ?? []}
            readOnly={selection.kind === 'policy' && !mayUpdate(selection.policy)}
            owner={selection.kind === 'policy' ? ownerOfPolicy(selection.policy) ?? null : null}
            ownerLink={selection.kind === 'policy' ? linkTo(selection.policy) : null}
            onSaved={(saved) => {
              select({ kind: 'policy', policy: saved });
              void load();
            }}
            onOpen={(id) => void openPolicy(id)}
            can={can}
            open={open}
            nonce={nonce}
            offerOf={
              selection.kind === 'policy' && offerWorkspaceOf(selection.policy)
                ? workspaceGroupName(selection.policy.name.replace(/ access$/, ''))
                : null
            }
            configuration={
              // A workspace's offer ("<W> access"): its switches are the policy's Configuration.
              selection.kind === 'policy' && offerWorkspaceOf(selection.policy)
                ? (changed) => (
                    <WorkspaceOfferEditor
                      workspaceId={offerWorkspaceOf(selection.policy)!}
                      scope={selection.policy.owner_scope ?? here}
                      policyId={selection.policy.id}
                      workspaceName={selection.policy.name.replace(/ access$/, '')}
                      api={api}
                      nonce={nonce}
                      onChanged={changed}
                    />
                  )
                : undefined
            }
          />
          </>
        )}
      </div>
    );
  }


  // The list waits for its first page; a policy's page (above) does not.
  if (error && (policies === null || held === null)) return <p className="access-policy-error" role="alert">{error}</p>;
  if (policies === null || held === null) return <p className="access-empty">Loading…</p>;

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
            {levelPolicyOf(policy) && (
              <span
                className="platform-users-badge access-policy-badge"
                data-level-policy={levelPolicyOf(policy)!.level}
                title={levelPolicyOf(policy)!.summary}
              >
                level
              </span>
            )}
            {offerWorkspaceOf(policy) && (
              <span
                className="platform-users-badge access-policy-badge"
                data-workspace-offer=""
                title="What the workspace offers: edited with toggles on its page"
              >
                workspace offer
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
      {lists && next && (
        <p className="org-settings-users-filter-meta" data-field="policies-loading">
          Loading policies: {policies.length} so far; a search or filter sees those read.
        </p>
      )}

      {lists ? (
        <>
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table" aria-label="Policies">
            <ListHead columns={columns} controls={list} />
            <tbody>
              {paged.pageRows.map(({ policy, depth }) => (
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
        <TablePager total={rows.length} paged={paged} />
        </>
      ) : holdsOnly ? (
        <>
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table" aria-label="Policies held here">
            <ListHead columns={heldColumns} controls={heldList} actions={false} />
            <tbody>
              {heldPaged.pageRows.map((h) => (
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
        <TablePager total={heldList.visible.length} paged={heldPaged} />
        </>
      ) : (
        <p className="access-policy-muted">You may create policies here, not list them.</p>
      )}
    </div>
  );
}

/** A policy the caller may list the holders of, not read: its title, its actions ("+ Attach") at
 *  its right, as on an editable policy's page. */
function HeldPolicySection({ name, id, children }: { name: string; id: string; children: ReactNode }) {
  const [actions, setActions] = useState<HTMLElement | null>(null);
  return (
    <AccessHeaderSlotContext.Provider value={actions}>
      <section className="access-policy-editor" aria-label={`Policy ${name}`}>
        <InstanceHeader name={name} id={id} actionsRef={setActions} />
        {children}
      </section>
    </AccessHeaderSlotContext.Provider>
  );
}
