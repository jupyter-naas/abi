'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Pencil, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import { ConfirmDialog } from '@/components/ui/dialogs';
import { listAllGroups } from '@/lib/iam-admin/batched';
import type { AttachmentView, GroupView, PrincipalView } from '@/lib/iam-admin/types';
import { NO_PROVIDERS, fetchInviteProviders, type InviteProviders } from '@/lib/invitations';
import type { AccessViewProps } from '../access-props';
import { NEW_GROUP } from '../access-paths';
import { GroupPage } from './group-page';
import {
  AccessHeaderAction,
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
import { TablePager, usePagedRows } from '@/components/settings/users-table/table-pager';
import { PLATFORM, ownedHere, ownerOf } from '../access-scope';
import { AttachForm } from '../attachments/attach-form';
import { scopeLabel } from '../attachments/attachments-model';
import { holdingRows, levelLabel, scopesOf } from '../holdings/holdings-model';
import { HoldingsTable } from '../holdings/holdings-table';
import { useActionsAt, useContainerNames } from '../policies/policy-owners';
import { GROUP_KIND_LABELS, groupKind, groupRank } from '@/lib/access-model/levels';
import '../people/people.css';
import './groups.css';

const message = (e: unknown) => (e instanceof IamAdminError ? e.message : String(e));

export const principalLabel = (p: PrincipalView) => p.display_name || p.email || p.name || p.id;

type Props = AccessViewProps & {
  /** The identity providers an IdP group can be mapped from (tests pass their own). */
  loadProviders?: () => Promise<InviteProviders>;
  /** The group whose page is open (`?group=<id>`), from the page's address or a link. */
  focus?: string | null;
  /** Told when a group's page opens (its id) or closes (null). */
  onFocus?: (groupId: string | null) => void;
};

/**
 * The groups of the scope: those it owns, which its admins create, fill and delete, and
 * (at a workspace) its organization's the caller attaches to there. A group's page lists its
 * members (each opening their own page), every attachment of the group at every level IAM lets
 * the caller list, and, where `access` offers IdP mappings (the platform), the IdP group claims
 * that put people in it.
 */
export function GroupsView({
  api,
  can,
  scope,
  directory,
  nonce,
  open,
  loadProviders = fetchInviteProviders,
  focus = null,
  onFocus,
}: Props) {
  const [groups, setGroups] = useState<PrincipalView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelectedState] = useState<string | null>(focus);
  useEffect(() => setSelectedState(focus), [focus]);
  // A group's page shown (a click opens it before the address follows): the level hides the list's header.
  useAccessInstance(selected !== null);
  const setSelected = (id: string | null) => {
    setSelectedState(id);
    onFocus?.(id);
  };
  const [deleting, setDeleting] = useState<PrincipalView | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const load = useCallback(async () => {
    try {
      // Each group's member count comes with the list (#1608): null where the caller may not
      // read the group, as its detail would be refused. No detail is read per group.
      const items = await listAllGroups(api, scope.value ?? undefined);
      setGroups(items);
      setCounts(
        Object.fromEntries(items.flatMap((g) => (typeof g.member_count === 'number' ? [[g.id, g.member_count]] : []))),
      );
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, scope]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const act = async (run: () => Promise<unknown>) => {
    try {
      await run();
      setError(null);
      await load();
    } catch (e) {
      setError(message(e));
    }
  };

  const kindOf = (g: PrincipalView) => GROUP_KIND_LABELS[groupKind(g)];
  const columns: ListColumn<PrincipalView>[] = [
    { id: 'name', label: 'Group', sortBy: (g) => (g.name ?? g.id).toLowerCase(), values: (g) => [g.name ?? g.id] },
    {
      id: 'kind',
      label: 'Kind',
      // The model's groups first (levels, admins, workspaces, people, capabilities), then custom.
      sortBy: (g) => `${groupRank(groupKind(g))}-${(g.name ?? g.id).toLowerCase()}`,
      values: (g) => [kindOf(g)],
    },
    {
      id: 'owner',
      label: 'Owner',
      sortBy: (g) => scopeLabel(g.owner_scope ?? PLATFORM),
      values: (g) => [scopeLabel(g.owner_scope ?? PLATFORM)],
    },
    {
      id: 'members',
      label: 'Members',
      sortBy: (g) => counts[g.id] ?? -1,
      values: (g) => [String(counts[g.id] ?? '–')],
    },
  ];
  const list = useListControls(groups, {
    searchText: (g) => [g.name, g.id, scopeLabel(g.owner_scope ?? PLATFORM)],
    columns,
    initialSort: 'kind',
  });
  useAccessBadge(groups?.length ?? null, 'group');
  const paged = usePagedRows(list.visible, list.pageKey);

  if (selected === NEW_GROUP && can('iam:CreateGroup')) {
    return (
      <div className="access-group org-settings-users-main access-instance-page">
        <button type="button" className="access-person-back" onClick={() => setSelected(null)}>
          <ArrowLeft size={14} /> Groups
        </button>
        <GroupPage
          key={NEW_GROUP}
          api={api}
          can={can}
          scope={scope}
          directory={directory}
          nonce={nonce}
          open={open}
          groupId={null}
          owned
          loadProviders={loadProviders}
          onChanged={load}
          // Made: its page opens, where it is changed as any group.
          onCreated={(id) => setSelected(id)}
        />
      </div>
    );
  }

  // A new group waits for IAM to let the caller create (its rights are read a moment later).
  if (selected && selected !== NEW_GROUP) {
    // Listed here, or reached by a link from another page (a person's, a policy's): a group
    // owned elsewhere is shown as IAM lets the caller read it, never changed here. The page
    // needs only the group and its attachments: it opens whether the list was read or not.
    const listed = groups?.find((g) => g.id === selected);
    return (
      <div className="access-group org-settings-users-main access-instance-page">
        <button type="button" className="access-person-back" onClick={() => setSelected(null)}>
          <ArrowLeft size={14} /> Groups
        </button>
        <GroupPage
          key={selected}
          api={api}
          can={can}
          scope={scope}
          directory={directory}
          nonce={nonce}
          open={open}
          groupId={selected}
          owned={!!listed && ownedHere(scope, listed.owner_scope)}
          loadProviders={loadProviders}
          onChanged={load}
        />
      </div>
    );
  }

  if (groups === null) {
    return error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>;
  }

  return (
    <div className="access-group org-settings-users-main">
      {can('iam:CreateGroup') && (
        <AccessHeaderAction>
          <button
            type="button"
            className="org-settings-primary-button"
            data-action="create-group"
            onClick={() => setSelected(NEW_GROUP)}
          >
            <Plus size={16} />
            Create group
          </button>
        </AccessHeaderAction>
      )}
      {error && (
        <div className="org-settings-users-alert" role="alert">
          <span>{error}</span>
        </div>
      )}
      <ListSearch
        value={list.search}
        onChange={list.setSearch}
        placeholder="Search name, id, owner…"
        label="Search groups"
        shown={list.visible.length}
        total={groups.length}
        noun="group"
        filtered={list.filtered}
        onClear={list.clear}
      />
      <div className="org-settings-users-table-wrap">
        <table className="org-settings-users-table" aria-label="Groups">
          <ListHead columns={columns} controls={list} />
          <tbody>
            {paged.pageRows.map((group) => (
              <tr
                key={group.id}
                data-group={group.id}
                title="Open its members and what it holds"
                {...rowOpener(() => setSelected(group.id))}
              >
                <td>
                  <NameCell name={group.name ?? group.id} detail={group.id} />
                </td>
                <td data-group-kind={groupKind(group)}>{kindOf(group)}</td>
                <td>{scopeLabel(group.owner_scope ?? PLATFORM)}</td>
                <td data-field="members">{counts[group.id] ?? '–'}</td>
                <RowActions>
                    <button
                      type="button"
                      className="org-settings-users-edit"
                      data-action="open"
                      title="Open"
                      aria-label={`Open ${group.name ?? group.id}`}
                      onClick={() => setSelected(group.id)}
                    >
                      <Pencil size={16} />
                    </button>
                    {can('iam:DeleteGroup') && ownedHere(scope, group.owner_scope) && (
                      <button
                        type="button"
                        className="org-settings-users-remove"
                        title="Delete"
                        aria-label={`Delete ${group.name ?? group.id}`}
                        onClick={() => setDeleting(group)}
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                </RowActions>
              </tr>
            ))}
            {groups.length > 0 && list.visible.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="org-settings-users-no-match">
                  No groups match the current search and filters
                </td>
              </tr>
            )}
            {groups.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="org-settings-users-no-match">
                  No groups.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <TablePager total={list.visible.length} paged={paged} />
      {/* A modal, wherever the row was: never below the pager, out of sight (UX-05). */}
      <ConfirmDialog
        open={deleting !== null}
        title={`Delete ${deleting?.name ?? deleting?.id ?? 'this group'}?`}
        description="Its members lose what it gave them. Its policies stay, attached to no one through it."
        confirmLabel="Delete group"
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          const target = deleting;
          setDeleting(null);
          if (target) void act(() => api.deleteGroup(target.id));
        }}
      />
    </div>
  );
}
