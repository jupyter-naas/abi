'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useParams, useRouter } from 'next/navigation';
import {
  Plus,
  Shield,
  Crown,
  UserCircle,
  AlertCircle,
  Trash2,
  X,
  Filter,
  ChevronUp,
  ChevronDown,
  Search,
  Download,
  Pencil,
} from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { IdpGroupBindings } from '@/components/invitations/idp-group-bindings';
import { PendingInvitations } from '@/components/invitations/pending-invitations';
import { ColumnResizeHandle } from '@/components/shell/column-resize-handle';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { rowMatchesColumnFilter } from './users-table-filter';
import { SearchBox } from '@/components/settings/search-box';
import { matchesSearch } from '@/app/settings/lib/search';
import {
  downloadUsersExport,
  type UsersExportFormat,
} from './users-table-export';
import '../components/org-settings-components.css';
import './users.css';

const PANE_WIDTH_DEFAULT = 440;
const PANE_WIDTH_MIN = 320;
const PANE_WIDTH_MAX = 560;

type SortKey = 'user' | 'workspaces' | 'role';
type SortDir = 'asc' | 'desc';
type ColumnId = SortKey;

type OrgWorkspace = {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
};

type WorkspaceMembership = {
  user_id: string;
  workspace_id: string;
  role: string;
};

const ROLE_LABEL: Record<'owner' | 'admin' | 'member', string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
};

const ROLE_RANK: Record<string, number> = { owner: 0, admin: 1, member: 2 };

function summarizeWorkspaces(names: string[], visible = 2) {
  if (names.length === 0) {
    return { label: 'No workspaces', extra: 0, count: 0 };
  }
  return {
    label: names.slice(0, visible).join(', '),
    extra: Math.max(0, names.length - visible),
    count: names.length,
  };
}

function roleBadge(role: 'owner' | 'admin' | 'member') {
  if (role === 'owner') {
    return (
      <span className="org-settings-users-badge org-settings-users-badge-owner">
        <Crown size={12} />
        Owner
      </span>
    );
  }
  if (role === 'admin') {
    return (
      <span className="org-settings-users-badge org-settings-users-badge-admin">
        <Shield size={12} />
        Admin
      </span>
    );
  }
  return (
    <span className="org-settings-users-badge org-settings-users-badge-member">
      <UserCircle size={12} />
      Member
    </span>
  );
}

function memberPhotoUrl(avatar?: string) {
  if (!avatar) return '';
  return avatar.startsWith('/') ? `${getApiUrl()}${avatar}` : avatar;
}

function countFacets(values: string[]): FacetBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

export default function OrgUsersPage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const authUser = useAuthStore((s) => s.user);
  const {
    fetchMembers,
    removeMember,
    membersCache,
    membersLoading,
  } = useOrganizationStore();

  const members = membersCache[orgId] || [];
  const myMembership = members.find((m) => m.userId === authUser?.id);
  const canManage =
    myMembership?.role === 'owner' || myMembership?.role === 'admin';

  const [actionError, setActionError] = useState('');
  const { confirm: confirmAction, dialog: confirmDialog } = useConfirm();
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [openPickerUserId, setOpenPickerUserId] = useState<string | null>(null);
  const [draftWorkspaceIds, setDraftWorkspaceIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [sheetQuery, setSheetQuery] = useState('');
  const [search, setSearch] = useState('');
  const [columnFilters, setColumnFilters] = useState<
    Partial<Record<ColumnId, ColumnFilterState>>
  >({});
  const [sortKey, setSortKey] = useState<SortKey>('user');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [openFilter, setOpenFilter] = useState<{
    id: ColumnId;
    left: number;
    top: number;
  } | null>(null);
  const isMobile = useIsMobile();
  const [paneHost, setPaneHost] = useState<HTMLElement | null>(null);
  const [paneWidth, setPaneWidth] = useState(PANE_WIDTH_DEFAULT);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);
  const isDraggingRef = useRef(false);

  const membershipByUser = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const row of memberships) {
      if (!map[row.user_id]) map[row.user_id] = [];
      map[row.user_id].push(row.workspace_id);
    }
    return map;
  }, [memberships]);

  const workspaceById = useMemo(
    () => Object.fromEntries(workspaces.map((ws) => [ws.id, ws])),
    [workspaces]
  );

  const assignedNamesByUser = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const user of members) {
      const names = (membershipByUser[user.userId] || [])
        .map((workspaceId) => workspaceById[workspaceId]?.name || workspaceId)
        .sort((a, b) => a.localeCompare(b));
      map[user.userId] = names;
    }
    return map;
  }, [members, membershipByUser, workspaceById]);

  const sortedWorkspaces = useMemo(
    () => [...workspaces].sort((a, b) => a.name.localeCompare(b.name)),
    [workspaces]
  );

  const sheetWorkspaces = useMemo(() => {
    const query = sheetQuery.trim().toLowerCase();
    if (!query) return sortedWorkspaces;
    return sortedWorkspaces.filter((workspace) =>
      workspace.name.toLowerCase().includes(query)
    );
  }, [sortedWorkspaces, sheetQuery]);

  const pickerUser = members.find((user) => user.userId === openPickerUserId);

  const loadMemberWorkspaces = useCallback(async () => {
    if (!orgId) return;
    setWorkspacesLoading(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/organizations/${orgId}/member-workspaces`
      );
      if (!response.ok) {
        throw new Error('Failed to load workspace memberships');
      }
      const data = await response.json();
      setWorkspaces(data.workspaces || []);
      setMemberships(data.memberships || []);
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to load workspace memberships';
      setActionError(message);
    } finally {
      setWorkspacesLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    if (orgId) {
      void fetchMembers(orgId);
      void loadMemberWorkspaces();
    }
  }, [orgId, fetchMembers, loadMemberWorkspaces]);

  useEffect(() => {
    setPaneHost(document.querySelector<HTMLElement>('[data-org-settings-root]'));
  }, []);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = dragStartX.current - event.clientX;
      setPaneWidth(
        Math.max(
          PANE_WIDTH_MIN,
          Math.min(PANE_WIDTH_MAX, Math.round(dragStartWidth.current + delta))
        )
      );
    };
    const onUp = () => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, []);

  const handlePaneDragStart = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStartX.current = event.clientX;
      dragStartWidth.current = paneWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [paneWidth]
  );

  const closePane = useCallback(() => {
    setOpenPickerUserId(null);
    setDraftWorkspaceIds([]);
    setSheetQuery('');
  }, []);

  useEffect(() => {
    if (!openPickerUserId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closePane();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openPickerUserId, closePane]);

  const putMemberWorkspaces = async (userId: string, workspaceIds: string[]) => {
    const { authFetch } = await import('@/stores/auth');
    const response = await authFetch(
      `/api/organizations/${orgId}/members/${userId}/workspaces`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_ids: workspaceIds }),
      }
    );
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to update workspaces');
    }
  };

  const openWorkspacePicker = (userId: string) => {
    if (!canManage) return;
    setSheetQuery('');
    setDraftWorkspaceIds([...(membershipByUser[userId] || [])]);
    setOpenPickerUserId(userId);
  };

  const handleRemove = async (userId: string) => {
    if (!orgId || !canManage) return;
    if (
      !(await confirmAction({
        title: 'Remove this user from the organization?',
        confirmLabel: 'Remove',
      }))
    ) {
      return;
    }
    setActionError('');
    try {
      await removeMember(orgId, userId);
      await loadMemberWorkspaces();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to remove user';
      setActionError(message);
    }
  };

  const toggleDraftWorkspace = (workspaceId: string) => {
    setDraftWorkspaceIds((current) =>
      current.includes(workspaceId)
        ? current.filter((id) => id !== workspaceId)
        : [...current, workspaceId]
    );
  };

  const saveWorkspaceAssignments = async (userId: string) => {
    if (!orgId || !canManage) return;
    const previous = new Set(membershipByUser[userId] || []);
    const next = new Set(draftWorkspaceIds);
    const removed = [...previous].filter((id) => !next.has(id));
    if (removed.length > 0) {
      const names = removed
        .map((id) => workspaceById[id]?.name || id)
        .join(', ');
      if (
        !(await confirmAction({
          title: `Remove this user from workspace${removed.length > 1 ? 's' : ''}: ${names}?`,
          confirmLabel: 'Remove',
        }))
      ) {
        return;
      }
    }
    setSaving(true);
    setActionError('');
    try {
      await putMemberWorkspaces(userId, draftWorkspaceIds);
      await loadMemberWorkspaces();
      closePane();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to update workspaces';
      setActionError(message);
    } finally {
      setSaving(false);
    }
  };

  const cellValues = useCallback(
    (userId: string, columnId: ColumnId): string[] => {
      const user = members.find((row) => row.userId === userId);
      if (!user) return [];
      if (columnId === 'user') {
        return [user.name || 'Unknown', user.email || user.userId].filter(
          (value, index, all) => all.indexOf(value) === index
        );
      }
      if (columnId === 'role') return [ROLE_LABEL[user.role]];
      const names = assignedNamesByUser[user.userId] || [];
      return names.length > 0 ? names : ['No workspaces'];
    },
    [members, assignedNamesByUser]
  );

  const filteredMembers = useMemo(() => {
    return members.filter(
      (user) =>
        // Global search: every word must appear in a column or the member profile.
        matchesSearch(
          [
            ...(['user', 'workspaces', 'role'] as ColumnId[]).flatMap((columnId) =>
              cellValues(user.userId, columnId)
            ),
            user.organization ?? '',
            user.jobTitle ?? '',
            user.serviceLine ?? '',
            user.country ?? '',
            user.interest ?? '',
          ],
          search
        ) &&
        (['user', 'workspaces', 'role'] as ColumnId[]).every((columnId) =>
          rowMatchesColumnFilter(cellValues(user.userId, columnId), columnFilters[columnId])
        )
    );
  }, [members, search, columnFilters, cellValues]);

  const visibleMembers = useMemo(() => {
    const rows = [...filteredMembers];
    rows.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'user') {
        cmp = (a.name || a.email || '').localeCompare(b.name || b.email || '');
      } else if (sortKey === 'role') {
        cmp = (ROLE_RANK[a.role] ?? 9) - (ROLE_RANK[b.role] ?? 9);
      } else {
        cmp =
          (assignedNamesByUser[a.userId]?.length || 0) -
          (assignedNamesByUser[b.userId]?.length || 0);
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [filteredMembers, sortKey, sortDir, assignedNamesByUser]);

  const loadFacets = useCallback(
    async (columnId: string, search: string): Promise<FacetBucket[]> => {
      const query = search.trim().toLowerCase();
      const values = members.flatMap((user) => cellValues(user.userId, columnId as ColumnId));
      return countFacets(values).filter((bucket) =>
        bucket.value.toLowerCase().includes(query)
      );
    },
    [members, cellValues]
  );

  const toggleSort = (columnId: ColumnId) => {
    if (sortKey === columnId) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(columnId);
    setSortDir('asc');
  };

  const setFilter = (columnId: ColumnId, next: ColumnFilterState) => {
    setColumnFilters((current) => ({ ...current, [columnId]: next }));
  };

  const clearFilter = (columnId: ColumnId) => {
    setColumnFilters((current) => {
      const next = { ...current };
      delete next[columnId];
      return next;
    });
  };

  const columns: { id: ColumnId; label: string }[] = [
    { id: 'user', label: 'User' },
    { id: 'workspaces', label: 'Workspaces' },
    { id: 'role', label: 'Role' },
  ];

  const hasActiveFilters = columns.some((column) => !isBlank(columnFilters[column.id]));

  const exportVisibleUsers = (format: UsersExportFormat) => {
    const rows = visibleMembers.map((user) => ({
      name: user.name || 'Unknown',
      email: user.email || user.userId,
      role: ROLE_LABEL[user.role],
      groups: (assignedNamesByUser[user.userId] || []).join('; '),
    }));
    const date = new Date().toISOString().slice(0, 10);
    downloadUsersExport(rows, format, `users_${date}`);
  };

  return (
    <div className="org-settings-users-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title="Users"
          badge={`${members.length} ${members.length === 1 ? 'user' : 'users'}`}
          subtitle="Manage who has access to this organization and its workspaces"
          actions={
            <>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    type="button"
                    className="org-settings-users-secondary-button"
                    disabled={visibleMembers.length === 0}
                  >
                    <Download size={16} />
                    Export
                    <ChevronDown size={14} />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    align="end"
                    sideOffset={4}
                    className="org-settings-users-export-menu"
                  >
                    <DropdownMenu.Item
                      className="org-settings-users-export-item"
                      onSelect={() => exportVisibleUsers('csv')}
                    >
                      CSV
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="org-settings-users-export-item"
                      onSelect={() => exportVisibleUsers('xlsx')}
                    >
                      Excel (.xlsx)
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
              {canManage ? (
                <button
                  type="button"
                  className="org-settings-primary-button"
                  onClick={() => router.push(`/organizations/${orgId}/settings/users/new`)}
                >
                  <Plus size={16} />
                  Create user
                </button>
              ) : (
                <button
                  type="button"
                  className="org-settings-primary-button"
                  disabled
                  title="Only organization owners and admins can create users"
                >
                  <Plus size={16} />
                  Create user
                </button>
              )}
            </>
          }
        />

        {actionError && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{actionError}</span>
          </div>
        )}

        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search name, email, role, workspace, organization, country..."
          label="Search users"
        />

        {(hasActiveFilters || search.trim()) && (
          <p className="org-settings-users-filter-meta">
            {visibleMembers.length} of {members.length}{' '}
            {members.length === 1 ? 'user' : 'users'}
            <button
              type="button"
              className="org-settings-users-filter-clear"
              onClick={() => {
                setSearch('');
                setColumnFilters({});
              }}
            >
              Clear search and filters
            </button>
          </p>
        )}

        <div className="org-settings-users-table-wrap">
          {membersLoading && members.length === 0 ? (
            <div className="org-settings-loading">Loading users...</div>
          ) : members.length === 0 ? (
            <div className="org-settings-empty">
              <div className="org-settings-empty-icon">
                <UserCircle size={24} />
              </div>
              <p className="org-settings-empty-title">No users yet</p>
              <p className="org-settings-empty-body">
                {canManage
                  ? 'Add an existing account by email to grant organization access.'
                  : 'Ask an organization owner or admin to add users.'}
              </p>
            </div>
          ) : (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {columns.map((column) => {
                    const sorted = sortKey === column.id;
                    const active = !isBlank(columnFilters[column.id]);
                    return (
                      <th key={column.id}>
                        <div className="org-settings-users-th">
                          <button
                            type="button"
                            className="org-settings-users-sort"
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
                            data-filter-trigger=""
                            title="Filter"
                            onClick={(event) => {
                              if (openFilter?.id === column.id) {
                                setOpenFilter(null);
                                return;
                              }
                              const rect = event.currentTarget.getBoundingClientRect();
                              setOpenFilter({
                                id: column.id,
                                left: rect.left,
                                top: rect.bottom + 4,
                              });
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
                            state={columnFilters[column.id]}
                            onChange={(next) => setFilter(column.id, next)}
                            onClear={() => clearFilter(column.id)}
                            loadFacets={loadFacets}
                            onClose={() => setOpenFilter(null)}
                          />
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {visibleMembers.length === 0 && (
                  <tr>
                    <td colSpan={3} className="org-settings-users-no-match">
                      No users match the current search and filters
                    </td>
                  </tr>
                )}
                {visibleMembers.map((user) => {
                  const assignedNames = assignedNamesByUser[user.userId] || [];
                  const summary = summarizeWorkspaces(assignedNames);
                  const isPickerOpen = openPickerUserId === user.userId;
                  const canRemove =
                    canManage &&
                    user.role !== 'owner' &&
                    user.userId !== authUser?.id;
                  const summaryLabel =
                    workspacesLoading && assignedNames.length === 0
                      ? 'Loading...'
                      : summary.label;
                  return (
                    <tr
                      key={user.id}
                      className={canManage ? 'org-settings-users-row-link' : undefined}
                      onClick={(event) => {
                        // Buttons and inputs in the row (workspaces, remove) keep their own action.
                        if (!canManage) return;
                        if ((event.target as HTMLElement).closest('button, a, input, select, label')) return;
                        router.push(`/organizations/${orgId}/settings/users/${user.userId}`);
                      }}
                    >
                      <td>
                        <div className="org-settings-users-row-start">
                          {memberPhotoUrl(user.avatar) ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={memberPhotoUrl(user.avatar)}
                              alt=""
                              className="org-settings-users-avatar-image"
                            />
                          ) : (
                            <div className="org-settings-users-avatar">
                              {(user.name || user.email || '?')
                                .charAt(0)
                                .toUpperCase()}
                            </div>
                          )}
                          <div className="org-settings-users-identity">
                            <p className="org-settings-users-name">
                              {user.name || 'Unknown'}
                            </p>
                            <p className="org-settings-users-email">
                              {user.email || user.userId}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td>
                        {canManage ? (
                          <button
                            type="button"
                            className={`org-settings-users-workspace-summary${
                              isPickerOpen ? ' is-open' : ''
                            }`}
                            aria-expanded={isPickerOpen}
                            onClick={() =>
                              isPickerOpen
                                ? closePane()
                                : openWorkspacePicker(user.userId)
                            }
                          >
                            <span className="org-settings-users-workspace-summary-label">
                              {summaryLabel}
                            </span>
                            {summary.extra > 0 && (
                              <span className="org-settings-users-workspace-extra">
                                +{summary.extra}
                              </span>
                            )}
                          </button>
                        ) : (
                          <span className="org-settings-users-workspace-summary is-static">
                            <span className="org-settings-users-workspace-summary-label">
                              {summaryLabel}
                            </span>
                            {summary.extra > 0 && (
                              <span className="org-settings-users-workspace-extra">
                                +{summary.extra}
                              </span>
                            )}
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="org-settings-users-row-end">
                          {roleBadge(user.role)}
                          {canManage ? (
                            <span className="org-settings-users-row-actions">
                              <button
                                type="button"
                                className="org-settings-users-edit"
                                title="Open user"
                                aria-label={`Edit ${user.name || user.email || 'user'}`}
                                onClick={() =>
                                  router.push(
                                    `/organizations/${orgId}/settings/users/${user.userId}`
                                  )
                                }
                              >
                                <Pencil size={16} />
                              </button>
                              <span className="org-settings-users-remove-slot">
                                {canRemove ? (
                                  <button
                                    type="button"
                                    className="org-settings-users-remove"
                                    onClick={() => void handleRemove(user.userId)}
                                    title="Remove user"
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                ) : null}
                              </span>
                            </span>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <p className="org-settings-footnote">
          Click a user to open their organization profile. Create user invites
          the person through the identity provider: the account is made there
          if it does not exist yet, and they sign in with the code it emails.
        </p>

        <PendingInvitations
          scope="organizations"
          id={orgId}
          canManage={canManage}
        />

        <IdpGroupBindings scope="organizations" id={orgId} canManage={canManage} />
      </div>

      {openPickerUserId &&
        paneHost &&
        createPortal(
          <>
            {isDragging && <div className="fixed inset-0 z-50 cursor-col-resize" />}
            {!isMobile && (
              <ColumnResizeHandle
                onMouseDown={handlePaneDragStart}
                label="Drag to resize workspaces pane"
                isActive={isDragging}
              />
            )}
            <aside
              className={
                isMobile
                  ? 'fixed inset-0 z-40 flex flex-col bg-background'
                  : 'flex h-full shrink-0 flex-col border-l border-border/50 bg-background'
              }
              style={isMobile ? undefined : { width: paneWidth }}
              role="complementary"
              aria-labelledby="org-assign-workspaces-title"
            >
              <div className="org-settings-users-pane-header">
                <h3
                  id="org-assign-workspaces-title"
                  className="min-w-0 flex-1 truncate text-xs font-medium text-foreground"
                >
                  {pickerUser?.name || pickerUser?.email || 'Workspaces'}
                </h3>
                <span className="mr-1 shrink-0 text-[11px] text-muted-foreground">
                  {draftWorkspaceIds.length} selected
                </span>
                <button
                  type="button"
                  className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
                  title="Close pane"
                  aria-label="Close pane"
                  onClick={closePane}
                >
                  <X size={16} />
                </button>
              </div>
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex items-center gap-2 border-b border-border/50 px-3 py-2">
                  <label className="relative min-w-0 flex-1">
                    <Search
                      size={12}
                      className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 text-muted-foreground"
                    />
                    <input
                      type="text"
                      value={sheetQuery}
                      onChange={(event) => setSheetQuery(event.target.value)}
                      placeholder="Search workspaces..."
                      className="org-settings-users-pane-search w-full bg-transparent py-1 pl-5 pr-2 text-xs placeholder:text-muted-foreground"
                      autoFocus
                    />
                  </label>
                  <button
                    type="button"
                    className="shrink-0 text-[11px] text-muted-foreground hover:text-foreground"
                    onClick={() =>
                      setDraftWorkspaceIds(sortedWorkspaces.map((ws) => ws.id))
                    }
                  >
                    All
                  </button>
                  <button
                    type="button"
                    className="shrink-0 text-[11px] text-muted-foreground hover:text-foreground"
                    onClick={() => setDraftWorkspaceIds([])}
                  >
                    None
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-auto py-1">
                  {sortedWorkspaces.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-muted-foreground">
                      No organization workspaces yet.
                    </p>
                  ) : sheetWorkspaces.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-muted-foreground">
                      {`No workspaces match "${sheetQuery.trim()}"`}
                    </p>
                  ) : (
                    <ul className="m-0 list-none p-0">
                      {sheetWorkspaces.map((workspace) => {
                        const checked = draftWorkspaceIds.includes(workspace.id);
                        return (
                          <li key={workspace.id}>
                            <label className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted">
                              <Checkbox
                                checked={checked}
                                onCheckedChange={() =>
                                  toggleDraftWorkspace(workspace.id)
                                }
                              />
                              <span className="min-w-0 flex-1 truncate">
                                {workspace.name}
                              </span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
                <div className="flex h-10 shrink-0 items-center justify-end gap-1 border-t border-border/50 px-2">
                  <button
                    type="button"
                    className="px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                    style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
                    onClick={closePane}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="px-2 py-1 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
                    style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
                    disabled={saving}
                    onClick={() => void saveWorkspaceAssignments(openPickerUserId)}
                  >
                    {saving ? 'Saving...' : 'Apply'}
                  </button>
                </div>
              </div>
            </aside>
          </>,
          paneHost
        )}
      {confirmDialog}
    </div>
  );
}
