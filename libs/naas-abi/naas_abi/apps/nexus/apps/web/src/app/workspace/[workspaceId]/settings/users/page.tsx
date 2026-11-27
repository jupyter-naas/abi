'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { Suspense, useCallback, useState, useEffect, useMemo } from 'react';
import { Plus, Pencil, Trash2, AlertCircle, Mail, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { PendingInvitations } from '@/components/invitations/pending-invitations';
import { AddPeopleDialog } from '@/components/people/add-people-dialog';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { TablePager, usePagedRows } from '@/components/settings/users-table/table-pager';
import {
  RolesLoadingNote,
  RolesPending,
  rolesBatchFrom,
  useProgressiveRoles,
} from '@/components/settings/users-table/use-progressive-roles';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { matchesSearch } from '@/app/settings/lib/search';
import { countFacets } from '@/app/settings/lib/page-helpers';
import { InvitedBadge, ResendButton } from '@/components/people/member-status';
import {
  addedNotice,
  candidateLabel,
  createPeopleApi,
} from '@/lib/people';
import {
  MEMBER_COLUMNS,
  MEMBER_EXPORT_HEADERS,
  joinedDay,
  memberCellValues,
  memberExportRow,
  memberSearchTexts,
  readWorkspaceMember,
  sortMembers,
  type MemberColumnId,
  type SortDir,
  type WorkspaceMemberRow,
} from './members-model';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  countLabel,
} from '@/components/settings/settings-ui';
// The table of Platform and Organization settings › Users: columns that sort and filter.
import '@/app/organizations/[orgId]/settings/users/users.css';

type Member = WorkspaceMemberRow;

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || String(d)).join(', ');
    }
  } catch {
    // ignore parse errors
  }
  return fallback;
}

const peopleApi = createPeopleApi();

export default function MembersPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading members…" />}>
      <Members />
    </Suspense>
  );
}

function Members() {
  const params = useParams();
  const router = useRouter();
  const search = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const authUser = useAuthStore((s) => s.user);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const workspace = workspaces.find((w) => w.id === workspaceId);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  // Back from the create page: who was added (worded here, never taken from the URL as is).
  const [inviteNotice, setInviteNotice] = useState(
    () => addedNotice(search) ?? search.get('notice')?.slice(0, 500) ?? ''
  );
  const [actionError, setActionError] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  // Said once: a reload does not say it again.
  useEffect(() => {
    if (search.get('added')) router.replace(`/workspace/${workspaceId}/settings/users`);
    // Read on arrival only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<Partial<Record<MemberColumnId, ColumnFilterState>>>({});
  const [sortKey, setSortKey] = useState<MemberColumnId>('member');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [openFilter, setOpenFilter] = useState<{ id: MemberColumnId; left: number; top: number } | null>(null);
  const { confirm: confirmRemove, dialog: confirmDialog } = useConfirm();

  const self = members.find((m) => m.user_id === authUser?.id);
  const canManage =
    workspace?.currentUserRole === 'owner' || workspace?.currentUserRole === 'admin' || !!self?.admin;

  const refreshMembers = async () => {
    const { authFetch } = await import('@/stores/auth');
    // The list comes alone; each one's Role follows, the page shown first.
    const response = await authFetch(`/api/workspaces/${workspaceId}/members?roles=false`);
    if (!response.ok) {
      throw new Error(await readApiError(response, 'Failed to load members'));
    }
    const data = await response.json();
    setMembers(data.map((m: Record<string, unknown>) => readWorkspaceMember(m)));
  };

  useEffect(() => {
    const fetchMembers = async () => {
      try {
        await refreshMembers();
      } catch (error) {
        console.error('Failed to fetch members:', error);
        setActionError(
          error instanceof Error ? error.message : 'Failed to load members'
        );
      } finally {
        setLoading(false);
      }
    };

    if (workspaceId) {
      void fetchMembers();
    }
    // refreshMembers closes over workspaceId; effect keyed on workspaceId only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  const memberIds = useMemo(() => new Set(members.map((m) => m.user_id)), [members]);

  const handleRemoveMember = async (userId: string) => {
    if (!canManage) return;
    if (!(await confirmRemove({ title: 'Remove this member?', confirmLabel: 'Remove' }))) return;

    setActionError('');
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/workspaces/${workspaceId}/members/${userId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) {
        throw new Error(await readApiError(response, 'Failed to remove member'));
      }
      setMembers(members.filter((m) => m.user_id !== userId));
    } catch (error: unknown) {
      console.error('Failed to remove member:', error);
      setActionError(
        error instanceof Error ? error.message : 'Failed to remove member'
      );
    }
  };

  const fetchRoles = useMemo(
    () => rolesBatchFrom(`/api/workspaces/${encodeURIComponent(workspaceId)}/members/roles`, authFetch),
    [workspaceId]
  );
  const roles = useProgressiveRoles(
    useMemo(() => members.map((m) => m.principalId), [members]),
    fetchRoles
  );
  const withRoles = useMemo(
    () =>
      members.map((m) => ({
        ...m,
        roles: ((m.principalId ? roles.found[m.principalId] : undefined) ?? []).map((r) => ({
          kind: r.kind,
          id: r.id,
          name: r.name,
          scope: r.scope ?? null,
          implied: r.implied === true,
        })),
      })),
    [members, roles.found]
  );
  const filteredMembers = useMemo(
    () =>
      sortMembers(
        withRoles.filter(
          (member) =>
            matchesSearch(memberSearchTexts(member), searchQuery) &&
            MEMBER_COLUMNS.every((column) =>
              rowMatchesColumnFilter(memberCellValues(member, column.id), filters[column.id])
            )
        ),
        sortKey,
        sortDir
      ),
    [withRoles, searchQuery, filters, sortKey, sortDir]
  );
  // A page of them; the search, the filters and the sort reach every row.
  const paged = usePagedRows(filteredMembers, JSON.stringify([searchQuery, filters, sortKey, sortDir]));
  roles.show(paged.pageRows.map((m) => m.principalId));
  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      return countFacets(withRoles.flatMap((member) => memberCellValues(member, columnId as MemberColumnId))).filter(
        (bucket) => bucket.value.toLowerCase().includes(needle)
      );
    },
    [members]
  );
  const toggleSort = (column: MemberColumnId) => {
    if (sortKey === column) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(column);
    setSortDir('asc');
  };
  const filtered = searchQuery.trim() !== '' || MEMBER_COLUMNS.some((column) => !isBlank(filters[column.id]));
  const exportVisible = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(MEMBER_EXPORT_HEADERS, filteredMembers.map(memberExportRow), format, `users_${date}`, 'Users');
  };
  const invitedCount = members.filter((m) => m.status === 'invited').length;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Users"
        badge={
          invitedCount > 0
            ? `${members.length - invitedCount} active · ${invitedCount} invited`
            : `${members.length} active`
        }
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/users']}
        actions={
          <>
            <UsersExportMenu
              onExport={exportVisible}
              disabled={filteredMembers.length === 0 || !roles.done}
              title={roles.done ? undefined : 'Available once every role is read'}
            />
            <Button
              onClick={() => setAddOpen(true)}
              disabled={!canManage}
              title={canManage ? undefined : 'Only workspace owners and admins can add members'}
              data-action="add-people"
            >
              <Plus size={16} />
              Invite user
            </Button>
          </>
        }
      />

      {actionError && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {actionError}
        </SettingsNotice>
      )}

      {inviteNotice && (
        <SettingsNotice tone="info" icon={<Mail size={14} />}>
          {inviteNotice}
        </SettingsNotice>
      )}

      {canManage && (
        <AddPeopleDialog
          open={addOpen}
          onClose={() => setAddOpen(false)}
          workspaceId={workspaceId}
          memberIds={memberIds}
          navigate={(href) => router.push(href)}
          onAdded={async (candidate, emailSent) => {
            setActionError('');
            setInviteNotice(
              `${candidateLabel(candidate)} was added to this workspace.${
                emailSent ? ' They were emailed that they have access.' : ''
              }`
            );
            await refreshMembers().catch((error: unknown) =>
              setActionError(error instanceof Error ? error.message : 'Failed to load members')
            );
          }}
        />
      )}

      {loading ? (
        <SettingsLoading label="Loading members…" />
      ) : members.length === 0 ? (
        <SettingsEmpty title="No members yet." />
      ) : (
        <div className="space-y-4">
        <SettingsTableToolbar
          search={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search name, email, level, admin, invited…"
          // As the organization's and the platform's Users: nothing above the search but, while
          // it narrows the table, how many it keeps and Clear.
          meta={
            filtered ? (
              <>
                {countLabel(filteredMembers.length, members.length, 'member')}
                <button
                  type="button"
                  className="org-settings-users-filter-clear ml-3"
                  data-action="clear-filters"
                  onClick={() => {
                    setSearchQuery('');
                    setFilters({});
                  }}
                >
                  Clear search and filters
                </button>
              </>
            ) : null
          }
        />
        <RolesLoadingNote roles={roles} />
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table">
            <thead>
              <tr>
                {MEMBER_COLUMNS.map((column) => {
                  const sorted = sortKey === column.id;
                  const active = !isBlank(filters[column.id]);
                  return (
                    <th key={column.id}>
                      <div className="org-settings-users-th">
                        <button
                          type="button"
                          className="org-settings-users-sort"
                          data-sort={column.id}
                          onClick={() => toggleSort(column.id)}
                          title="Sort"
                        >
                          <span>{column.label}</span>
                          {sorted && sortDir === 'asc' && <ChevronUp size={12} />}
                          {sorted && sortDir === 'desc' && <ChevronDown size={12} />}
                        </button>
                        <button
                          type="button"
                          className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                          data-filter-trigger={column.id}
                          title="Filter"
                          onClick={(event) => {
                            if (openFilter?.id === column.id) {
                              setOpenFilter(null);
                              return;
                            }
                            const rect = event.currentTarget.getBoundingClientRect();
                            setOpenFilter({ id: column.id, left: rect.left, top: rect.bottom + 4 });
                          }}
                        >
                          <Filter size={11} />
                        </button>
                      </div>
                      {openFilter?.id === column.id && (
                        <ColumnFilterPopover
                          columnId={column.id}
                          label={column.label}
                          datatype="string"
                          facetable
                          anchor={{ left: openFilter.left, top: openFilter.top }}
                          state={filters[column.id]}
                          onChange={(next) => setFilters((current) => ({ ...current, [column.id]: next }))}
                          onClear={() =>
                            setFilters((current) => {
                              const next = { ...current };
                              delete next[column.id];
                              return next;
                            })
                          }
                          loadFacets={loadFacets}
                          onClose={() => setOpenFilter(null)}
                        />
                      )}
                    </th>
                  );
                })}
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {filteredMembers.length === 0 && (
                <tr>
                  <td colSpan={MEMBER_COLUMNS.length + 1} className="org-settings-users-no-match">
                    No members match the current search and filters
                  </td>
                </tr>
              )}
              {paged.pageRows.map((member) => {
                const initial = (member.name || member.email || '?').charAt(0).toUpperCase();
                const inherited = member.source === 'organization';
                const personHref = `/workspace/${workspaceId}/settings/users/${encodeURIComponent(
                  member.principalId ?? member.user_id
                )}`;
                return (
                  <tr
                    key={member.id}
                    className="cursor-pointer"
                    data-person={member.user_id}
                    onClick={(event) => {
                      // A click on a button or a field of the row does its own thing.
                      if ((event.target as HTMLElement).closest('button, a, input, select, label')) return;
                      router.push(personHref);
                    }}
                  >
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center bg-primary text-primary-foreground">
                          {initial}
                        </div>
                        <div>
                          <p className="flex items-center gap-2 font-medium">
                            {member.name}
                            <InvitedBadge status={member.status} />
                          </p>
                          <p className="flex items-center gap-2 text-xs text-muted-foreground">
                            {member.email}
                            {canManage && member.status === 'invited' && member.email && (
                              <ResendButton
                                email={member.email}
                                resend={() => peopleApi.resendWorkspace(workspaceId, member.user_id)}
                                onDone={(message) => {
                                  setActionError('');
                                  setInviteNotice(message);
                                }}
                                onError={setActionError}
                              />
                            )}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td data-field="role">
                      {member.principalId && roles.of(member.principalId) === undefined ? (
                        <RolesPending />
                      ) : member.roles.length === 0 ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <span className="flex flex-wrap gap-1">
                          {member.roles.map((role) => (
                            <span
                              key={`${role.kind}:${role.id}:${role.scope ?? ''}`}
                              data-role={role.kind}
                              title={
                                role.kind === 'policy'
                                  ? `Policy attached to them${role.scope ? ` at ${role.scope}` : ''}`
                                  : role.implied
                                    ? 'They reach this workspace through their admins group'
                                    : 'Group'
                              }
                              className={
                                role.kind === 'group'
                                  ? 'border border-border bg-muted/60 px-1.5 py-0.5 text-[11px]'
                                  : 'border border-dashed border-primary/60 px-1.5 py-0.5 text-[11px] text-primary'
                              }
                            >
                              {role.name}
                            </span>
                          ))}
                        </span>
                      )}
                    </td>
                    <td className="text-muted-foreground">{joinedDay(member) || '—'}</td>
                    <td className="whitespace-nowrap text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.push(personHref)}
                        title="Edit their roles"
                        aria-label={`Edit the roles of ${member.name}`}
                        data-action="edit"
                      >
                        <Pencil size={14} />
                      </Button>
                      {canManage && !inherited && member.user_id !== authUser?.id && (
                        <Button
                          variant="destructive-ghost"
                          size="icon"
                          onClick={() => void handleRemoveMember(member.user_id)}
                          title="Remove member"
                        >
                          <Trash2 size={14} />
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        </div>
      )}
      <TablePager total={filteredMembers.length} paged={paged} />

      {/* Invitations made before people were created at once: listed until they are migrated. */}
      <PendingInvitations scope="workspaces" id={workspaceId} canManage={canManage} />

      {confirmDialog}
    </div>
  );
}
