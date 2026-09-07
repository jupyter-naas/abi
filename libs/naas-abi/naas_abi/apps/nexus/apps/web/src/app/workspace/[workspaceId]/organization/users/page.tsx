'use client';

import { useState, useEffect } from 'react';
import { Plus, Shield, Crown, UserCircle, Trash2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';

export default function OrgUsersPage() {
  const authUser = useAuthStore((s) => s.user);
  const {
    organizations,
    fetchOrganizations,
    fetchMembers,
    inviteMember,
    removeMember,
    membersCache,
    membersLoading,
  } = useOrganizationStore();

  const org = organizations[0];
  const members = org ? membersCache[org.id] || [] : [];
  const myMembership = members.find((m) => m.userId === authUser?.id);
  const canManage =
    myMembership?.role === 'owner' || myMembership?.role === 'admin';

  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'member'>('member');
  const [inviteError, setInviteError] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);

  useEffect(() => {
    void fetchOrganizations();
  }, [fetchOrganizations]);

  useEffect(() => {
    if (org) {
      void fetchMembers(org.id);
    }
  }, [org, fetchMembers]);

  const handleInvite = async () => {
    if (!org || !inviteEmail.trim() || !canManage) return;

    setInviteError('');
    setInviteLoading(true);

    try {
      await inviteMember(org.id, inviteEmail.trim(), inviteRole);
      setShowInviteModal(false);
      setInviteEmail('');
      setInviteRole('member');
    } catch (error: unknown) {
      setInviteError(
        error instanceof Error ? error.message : 'Failed to invite member'
      );
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRemove = async (userId: string) => {
    if (!org || !canManage) return;
    if (!confirm('Are you sure you want to remove this member?')) return;

    try {
      await removeMember(org.id, userId);
    } catch (error: unknown) {
      alert(
        error instanceof Error ? error.message : 'Failed to remove member'
      );
    }
  };

  if (!org) {
    return (
      <div className="text-center text-muted-foreground py-12">
        Loading organization...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Users</h2>
          <p className="text-sm text-muted-foreground">
            Manage who has access to this organization
          </p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          disabled={!canManage}
          title={
            canManage
              ? undefined
              : 'Only organization owners and admins can add users'
          }
          className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus size={16} />
          Add User
        </button>
      </div>

      <div className="rounded-xl border bg-card">
        <div className="border-b px-4 py-3">
          <p className="text-sm font-medium text-muted-foreground">
            Organization Users ({members.length})
          </p>
        </div>
        {membersLoading && members.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Loading members...
          </div>
        ) : members.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            No members yet. Invite someone to get started.
          </div>
        ) : (
          <div className="divide-y">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/10 text-blue-500">
                    <UserCircle size={20} />
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      {member.name || 'Unknown'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {member.email}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {member.role === 'owner' && (
                    <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-500">
                      <Crown size={12} />
                      Owner
                    </span>
                  )}
                  {member.role === 'admin' && (
                    <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-500">
                      <Shield size={12} />
                      Admin
                    </span>
                  )}
                  {member.role === 'member' && (
                    <span className="flex items-center gap-1 rounded-full bg-gray-500/10 px-2 py-0.5 text-xs font-medium text-gray-500">
                      <UserCircle size={12} />
                      Member
                    </span>
                  )}
                  {canManage &&
                    member.role !== 'owner' &&
                    member.userId !== authUser?.id && (
                      <button
                        onClick={() => void handleRemove(member.userId)}
                        className="text-red-500 hover:text-red-600 transition-colors"
                        title="Remove member"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showInviteModal && canManage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-lg">
            <h3 className="text-lg font-semibold mb-2">Add User</h3>
            <p className="mb-4 text-xs text-muted-foreground">
              Creates the account if needed and emails a sign-in code. Same API as{' '}
              <code>POST /api/organizations/{'{id}'}/members/invite</code>.
            </p>

            {inviteError && (
              <div className="mb-4 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle size={16} />
                <span>{inviteError}</span>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Email</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) =>
                    setInviteRole(e.target.value as 'admin' | 'member')
                  }
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/30"
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>

            <div className="mt-6 flex gap-2">
              <button
                onClick={() => {
                  setShowInviteModal(false);
                  setInviteEmail('');
                  setInviteError('');
                }}
                className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleInvite()}
                disabled={!inviteEmail.trim() || inviteLoading}
                className={cn(
                  'flex-1 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors',
                  'hover:bg-blue-600',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
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
