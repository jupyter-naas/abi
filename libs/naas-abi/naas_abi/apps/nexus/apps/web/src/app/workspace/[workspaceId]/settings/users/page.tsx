'use client';

import { Suspense, useCallback, useState, useEffect, useMemo } from 'react';
import { Plus, Shield, Trash2, AlertCircle, Mail, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { Select } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { IdpGroupBindings } from '@/components/invitations/idp-group-bindings';
import { PendingInvitations } from '@/components/invitations/pending-invitations';
import { AddPeopleDialog } from '@/components/people/add-people-dialog';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { matchesSearch } from '@/app/settings/lib/search';
import { countFacets } from '@/app/settings/lib/page-helpers';
import { InvitedBadge, ResendButton } from '@/components/people/member-status';
import {
  addedNotice,
  candidateLabel,
  createPeopleApi,
  LEVELS,
  LEVEL_EVERYWHERE_NOTE,
  LEVEL_LABELS,
  type Level,
} from '@/lib/people';
import {
  MEMBER_COLUMNS,
  accessEditable,
  joinedDay,
  levelLabel,
  memberCellValues,
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
  SettingsSection,
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
  const [inviteNotice, setInviteNotice] = useState(() => addedNotice(search) ?? '');
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
    const response = await authFetch(`/api/workspaces/${workspaceId}/members`);
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

  // A level is the person's, in all their workspaces; the admin toggle is this workspace's
  // ("<W> admins"). IAM decides: a workspace's admins may change the level of its people.
  const handleChange = async (member: Member, change: { level?: Level; admin?: boolean }) => {
    if (!canManage) return;
    setActionError('');
    try {
      const done = await peopleApi.updateWorkspaceMember(workspaceId, member.user_id, change);
      setMembers((current) =>
        current.map((m) =>
          m.user_id === member.user_id
            ? { ...m, level: done.level ?? change.level ?? m.level, admin: change.admin ?? done.admin }
            : m
        )
      );
      if (change.level) {
        setInviteNotice(
          `${member.name} is now a ${LEVEL_LABELS[change.level]} in all of their workspaces.`
        );
      }
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : 'Failed to change this member');
    }
  };

  const filteredMembers = useMemo(
    () =>
      sortMembers(
        members.filter(
          (member) =>
            matchesSearch(memberSearchTexts(member), searchQuery) &&
            MEMBER_COLUMNS.every((column) =>
              rowMatchesColumnFilter(memberCellValues(member, column.id), filters[column.id])
            )
        ),
        sortKey,
        sortDir
      ),
    [members, searchQuery, filters, sortKey, sortDir]
  );
  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      return countFacets(members.flatMap((member) => memberCellValues(member, columnId as MemberColumnId))).filter(
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
  const adminCount = members.filter((m) => m.admin).length;
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
        description="Manage who has access to this workspace"
        actions={
          <Button
            onClick={() => setAddOpen(true)}
            disabled={!canManage}
            title={canManage ? undefined : 'Only workspace owners and admins can add members'}
            data-action="add-people"
          >
            <Plus size={16} />
            Add people
          </Button>
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
          meta={
            <>
              {`${countLabel(filteredMembers.length, members.length, 'member')} · ${adminCount} admin${adminCount === 1 ? '' : 's'}`}
              {filtered && (
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
              )}
            </>
          }
        />
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table">
            <thead>
              <tr>
                {MEMBER_COLUMNS.map((column) => {
                  const sorted = sortKey === column.id;
                  const active = !isBlank(filters[column.id]);
                  return (
                    <th key={column.id} title={column.id === 'level' ? LEVEL_EVERYWHERE_NOTE : undefined}>
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
              {filteredMembers.map((member) => {
                const initial = (member.name || member.email || '?').charAt(0).toUpperCase();
                const inherited = member.source === 'organization';
                const editable = accessEditable(member, { canManage, selfId: authUser?.id });
                return (
                  <tr key={member.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center bg-primary text-primary-foreground">
                          {initial}
                        </div>
                        <div>
                          <p className="flex items-center gap-2 font-medium">
                            {member.name}
                            <InvitedBadge status={member.status} />
                            {inherited && (
                              <span
                                className="border border-border px-1.5 py-0.5 text-[10px] font-normal uppercase tracking-wide text-muted-foreground"
                                title="Organization admins reach every workspace of the organization. Manage them in Organization > Users."
                              >
                                via organization
                              </span>
                            )}
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
                    <td>
                      {editable ? (
                        <Select
                          value={member.level ?? ''}
                          onChange={(e) => void handleChange(member, { level: e.target.value as Level })}
                          className="h-8 w-32"
                          aria-label={`Level of ${member.name}`}
                          title={LEVEL_EVERYWHERE_NOTE}
                          data-field="level"
                        >
                          {member.level === null && <option value="">—</option>}
                          {LEVELS.map((level) => (
                            <option key={level} value={level}>
                              {LEVEL_LABELS[level]}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <span>{levelLabel(member.level)}</span>
                      )}
                    </td>
                    <td>
                      {editable ? (
                        <span data-field="admin">
                          <Checkbox
                            aria-label={`${member.name} administers this workspace`}
                            checked={member.admin}
                            onCheckedChange={(on) => void handleChange(member, { admin: on })}
                          />
                        </span>
                      ) : member.admin ? (
                        <span className="flex items-center gap-2 text-primary">
                          <Shield size={14} />
                          Admin
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="text-muted-foreground">{joinedDay(member) || '—'}</td>
                    <td className="text-right">
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

      {/* Invitations made before people were created at once: listed until they are migrated. */}
      <PendingInvitations scope="workspaces" id={workspaceId} canManage={canManage} />

      <IdpGroupBindings scope="workspaces" id={workspaceId} canManage={canManage} />

      <SettingsSection title="Levels">
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-sm font-medium">Member</p>
            <p className="text-xs text-muted-foreground">
              Uses the workspace&apos;s agents and apps, chat, files, datasets, graph, maps, ontology and search
            </p>
          </div>
          <div>
            <p className="text-sm font-medium">Viewer</p>
            <p className="text-xs text-muted-foreground">Opens the workspace&apos;s apps and datasets, read-only</p>
          </div>
          <div>
            <p className="text-sm font-medium">Workspace admin</p>
            <p className="text-xs text-muted-foreground">
              A Member who also manages this workspace: its settings, people, workflows and maps
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          {LEVEL_EVERYWHERE_NOTE} Organization admins reach every workspace of the organization without being
          added here. Capability groups (Workflow runners, Models · all, a seat) add one thing to a level: pick them
          when adding someone.
        </p>
      </SettingsSection>
      {confirmDialog}
    </div>
  );
}
