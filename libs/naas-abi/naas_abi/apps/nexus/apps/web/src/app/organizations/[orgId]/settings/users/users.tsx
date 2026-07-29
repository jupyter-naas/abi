'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Plus, Shield, Crown, UserCircle, AlertCircle, Trash2 } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './users.css';

type InviteRole = 'admin' | 'member';

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

  useEffect(() => {
    if (orgId) {
      void fetchMembers(orgId);
    }
  }, [orgId, fetchMembers]);

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
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to remove user';
      setActionError(message);
    }
  };

  return (
    <div className="org-settings-users-page">
      <OrgSettingsPageHeader
        title="Users"
        subtitle="Manage who has access to this organization"
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

      <OrgSettingsSectionCard flush overflowHidden>
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
            {members.map((user) => (
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
                <div className="org-settings-users-row-end">
                  {roleBadge(user.role)}
                  {canManage &&
                    user.role !== 'owner' &&
                    user.userId !== authUser?.id && (
                      <button
                        type="button"
                        className="org-settings-users-remove"
                        onClick={() => void handleRemove(user.userId)}
                        title="Remove user"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </OrgSettingsSectionCard>

      <p className="org-settings-footnote">
        Add User requires an existing account (same API as the abi CLI
        invite commands). Organization owner or admin only.
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
              The email must already belong to a registered user. New accounts
              are created via signup or ops CLI, not this form.
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
