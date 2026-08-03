'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { useParams } from 'next/navigation';
import {
  Plus,
  Shield,
  Crown,
  UserCircle,
  AlertCircle,
  Trash2,
  ChevronDown,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './users.css';

type InviteRole = 'admin' | 'member';

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

type PickerPosition = {
  top: number;
  left: number;
};

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

function computePickerPosition(trigger: HTMLElement): PickerPosition {
  const rect = trigger.getBoundingClientRect();
  const pickerWidth = Math.min(280, window.innerWidth - 24);
  const estimatedHeight = 320;
  const gap = 6;
  const spaceBelow = window.innerHeight - rect.bottom - 12;
  const placeAbove = spaceBelow < estimatedHeight && rect.top > spaceBelow;
  const top = placeAbove
    ? Math.max(12, rect.top - estimatedHeight - gap)
    : Math.min(rect.bottom + gap, window.innerHeight - 12);
  let left = rect.left;
  if (left + pickerWidth > window.innerWidth - 12) {
    left = window.innerWidth - pickerWidth - 12;
  }
  left = Math.max(12, left);
  return { top, left };
}

export default function OrgUsersPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const authUser = useAuthStore((s) => s.user);
  const {
    fetchMembers,
    inviteMember,
    removeMember,
    membersCache,
    membersLoading,
  } = useOrganizationStore();

  const members = membersCache[orgId] || [];
  const myMembership = members.find((m) => m.userId === authUser?.id);
  const canManage =
    myMembership?.role === 'owner' || myMembership?.role === 'admin';

  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<InviteRole>('member');
  const [inviteError, setInviteError] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [openPickerUserId, setOpenPickerUserId] = useState<string | null>(null);
  const [draftWorkspaceIds, setDraftWorkspaceIds] = useState<string[]>([]);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [pickerPos, setPickerPos] = useState<PickerPosition | null>(null);
  const [mounted, setMounted] = useState(false);
  const assignTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>(
    {}
  );

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
    setMounted(true);
  }, []);

  useEffect(() => {
    if (orgId) {
      void fetchMembers(orgId);
      void loadMemberWorkspaces();
    }
  }, [orgId, fetchMembers, loadMemberWorkspaces]);

  const updatePickerPosition = useCallback(() => {
    if (!openPickerUserId) {
      setPickerPos(null);
      return;
    }
    const trigger = assignTriggerRefs.current[openPickerUserId];
    if (!trigger) {
      setPickerPos(null);
      return;
    }
    setPickerPos(computePickerPosition(trigger));
  }, [openPickerUserId]);

  useLayoutEffect(() => {
    updatePickerPosition();
  }, [updatePickerPosition]);

  useEffect(() => {
    if (!openPickerUserId) return;
    const onReposition = () => updatePickerPosition();
    window.addEventListener('resize', onReposition);
    window.addEventListener('scroll', onReposition, true);
    return () => {
      window.removeEventListener('resize', onReposition);
      window.removeEventListener('scroll', onReposition, true);
    };
  }, [openPickerUserId, updatePickerPosition]);

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setInviteEmail('');
    setInviteRole('member');
    setInviteError('');
  };

  const handleInvite = async () => {
    if (!orgId || !inviteEmail.trim() || !canManage) return;

    setInviteError('');
    setInviteLoading(true);

    try {
      await inviteMember(orgId, inviteEmail.trim(), inviteRole);
      closeInviteModal();
      await loadMemberWorkspaces();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to add user';
      setInviteError(message);
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRemove = async (userId: string) => {
    if (!orgId || !canManage) return;
    if (!confirm('Remove this user from the organization?')) return;

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

  const openWorkspacePicker = (userId: string) => {
    if (!canManage) return;
    setOpenPickerUserId(userId);
    setDraftWorkspaceIds([...(membershipByUser[userId] || [])]);
  };

  const closeWorkspacePicker = () => {
    setOpenPickerUserId(null);
    setDraftWorkspaceIds([]);
    setPickerPos(null);
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
        !confirm(
          `Remove this user from workspace${removed.length > 1 ? 's' : ''}: ${names}?`
        )
      ) {
        return;
      }
    }

    setSavingUserId(userId);
    setActionError('');
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/organizations/${orgId}/members/${userId}/workspaces`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workspace_ids: draftWorkspaceIds }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to update workspaces');
      }
      await loadMemberWorkspaces();
      closeWorkspacePicker();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to update workspaces';
      setActionError(message);
    } finally {
      setSavingUserId(null);
    }
  };

  const workspacePickerPortal =
    mounted &&
    openPickerUserId &&
    pickerPos &&
    createPortal(
      <>
        <button
          type="button"
          className="org-settings-users-workspace-picker-backdrop"
          aria-label="Close workspace assign menu"
          onClick={closeWorkspacePicker}
        />
        <div
          className="org-settings-users-workspace-picker org-settings-users-workspace-picker-portal"
          style={{ top: pickerPos.top, left: pickerPos.left }}
          role="dialog"
          aria-label="Assign workspaces"
          onClick={(event) => event.stopPropagation()}
        >
          {workspaces.length === 0 ? (
            <p className="org-settings-users-workspace-empty">
              No organization workspaces yet.
            </p>
          ) : (
            <ul className="org-settings-users-workspace-options">
              {workspaces.map((workspace) => {
                const checked = draftWorkspaceIds.includes(workspace.id);
                return (
                  <li key={workspace.id}>
                    <label className="org-settings-users-workspace-option">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleDraftWorkspace(workspace.id)}
                      />
                      <span>{workspace.name}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="org-settings-users-workspace-picker-actions">
            <button
              type="button"
              className="org-settings-users-secondary-button"
              onClick={closeWorkspacePicker}
            >
              Cancel
            </button>
            <button
              type="button"
              className="org-settings-primary-button"
              disabled={savingUserId === openPickerUserId}
              onClick={() =>
                void saveWorkspaceAssignments(openPickerUserId)
              }
            >
              {savingUserId === openPickerUserId ? 'Saving...' : 'Apply'}
            </button>
          </div>
        </div>
      </>,
      document.body
    );

  return (
    <div className="org-settings-users-page">
      <OrgSettingsPageHeader
        title="Users"
        subtitle="Manage who has access to this organization and its workspaces"
        actions={
          canManage ? (
            <button
              type="button"
              className="org-settings-primary-button"
              onClick={() => setShowInviteModal(true)}
            >
              <Plus size={16} />
              Add User
            </button>
          ) : (
            <button
              type="button"
              className="org-settings-primary-button"
              disabled
              title="Only organization owners and admins can add users"
            >
              <Plus size={16} />
              Add User
            </button>
          )
        }
      />

      {actionError && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      <OrgSettingsSectionCard flush>
        <p className="org-settings-users-list-label">
          Organization Users{members.length > 0 ? ` (${members.length})` : ''}
        </p>
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
          <ul className="org-settings-users-list">
            <li className="org-settings-users-header-row" aria-hidden="true">
              <span>User</span>
              <span>Workspaces</span>
              <span>Role</span>
            </li>
            {members.map((user) => {
              const assignedIds = membershipByUser[user.userId] || [];
              const isPickerOpen = openPickerUserId === user.userId;
              const canRemove =
                canManage &&
                user.role !== 'owner' &&
                user.userId !== authUser?.id;
              return (
                <li key={user.id} className="org-settings-users-row">
                  <div className="org-settings-users-row-start">
                    <div className="org-settings-users-avatar">
                      <UserCircle size={20} />
                    </div>
                    <div>
                      <p className="org-settings-users-name">
                        {user.name || 'Unknown'}
                      </p>
                      <p className="org-settings-users-email">
                        {user.email || user.userId}
                      </p>
                    </div>
                  </div>

                  <div className="org-settings-users-workspaces">
                    {workspacesLoading && assignedIds.length === 0 ? (
                      <span className="org-settings-users-workspace-empty">
                        Loading...
                      </span>
                    ) : assignedIds.length === 0 ? (
                      <span className="org-settings-users-workspace-empty">
                        No workspaces
                      </span>
                    ) : (
                      <div className="org-settings-users-workspace-chips">
                        {assignedIds.map((workspaceId) => (
                          <span
                            key={workspaceId}
                            className="org-settings-users-workspace-chip"
                          >
                            {workspaceById[workspaceId]?.name || workspaceId}
                          </span>
                        ))}
                      </div>
                    )}

                    {canManage && (
                      <div className="org-settings-users-workspace-picker-wrap">
                        <button
                          ref={(node) => {
                            assignTriggerRefs.current[user.userId] = node;
                          }}
                          type="button"
                          className={`org-settings-users-workspace-edit${
                            isPickerOpen ? ' is-open' : ''
                          }`}
                          aria-expanded={isPickerOpen}
                          aria-haspopup="dialog"
                          onClick={() =>
                            isPickerOpen
                              ? closeWorkspacePicker()
                              : openWorkspacePicker(user.userId)
                          }
                        >
                          Assign
                          <ChevronDown size={14} />
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="org-settings-users-row-end">
                    {roleBadge(user.role)}
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
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </OrgSettingsSectionCard>

      {workspacePickerPortal}

      <p className="org-settings-footnote">
        Add User creates the account if needed and emails a sign-in code
        (OTP / magic link). Assign workspaces from the Workspaces column.
        Organization owner or admin only.
      </p>

      {showInviteModal && (
        <div
          className="org-settings-users-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) closeInviteModal();
          }}
        >
          <div
            className="org-settings-users-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="org-add-user-title"
          >
            <h3 id="org-add-user-title" className="org-settings-users-modal-title">
              Add User
            </h3>
            <p className="org-settings-users-modal-hint">
              Enter any email. If they are new, we create their account and send
              a sign-in code so they can log in. Assign workspaces after adding.
            </p>

            {inviteError && (
              <div className="org-settings-users-alert" role="alert">
                <AlertCircle size={16} />
                <span>{inviteError}</span>
              </div>
            )}

            <div className="org-settings-users-modal-fields">
              <label className="org-settings-field">
                <span className="org-settings-field-label">Email</span>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="org-settings-input"
                  autoFocus
                />
              </label>

              <label className="org-settings-field">
                <span className="org-settings-field-label">Role</span>
                <select
                  value={inviteRole}
                  onChange={(e) =>
                    setInviteRole(e.target.value as InviteRole)
                  }
                  className="org-settings-input"
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </label>
            </div>

            <div className="org-settings-users-modal-actions">
              <button
                type="button"
                className="org-settings-users-secondary-button"
                onClick={closeInviteModal}
              >
                Cancel
              </button>
              <button
                type="button"
                className="org-settings-primary-button"
                onClick={() => void handleInvite()}
                disabled={!inviteEmail.trim() || inviteLoading}
              >
                {inviteLoading ? 'Adding...' : 'Add User'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
