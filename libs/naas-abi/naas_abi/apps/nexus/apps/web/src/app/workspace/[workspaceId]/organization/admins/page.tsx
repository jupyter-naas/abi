'use client';

import { useState, useEffect } from 'react';
import { Plus, Shield, Crown, UserCircle, Trash2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOrganizationStore, OrganizationMember } from '@/stores/organization';

export default function OrgAdminsPage() {
  const {
    organizations,
    fetchOrganizations,
    fetchMembers,
    inviteMember,
    updateMemberRole,
    removeMember,
    membersCache,
    membersLoading,
  } = useOrganizationStore();
  
  const org = organizations[0]; // Primary org
  const members = org ? (membersCache[org.id] || []) : [];

  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'member'>('member');
  const [inviteError, setInviteError] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);

  useEffect(() => {
    fetchOrganizations();
  }, [fetchOrganizations]);

  useEffect(() => {
    if (org) {
      fetchMembers(org.id);
    }
  }, [org, fetchMembers]);

  const handleInvite = async () => {
    if (!org || !inviteEmail) return;
    
    setInviteError('');
    setInviteLoading(true);
    
    try {
      await inviteMember(org.id, inviteEmail, inviteRole);
      setShowInviteModal(false);
      setInviteEmail('');
      setInviteRole('member');
    } catch (error: any) {
      setInviteError(error.message || 'Failed to invite member');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRemove = async (userId: string) => {
    if (!org) return;
    if (!confirm('Are you sure you want to remove this member?')) return;
    
    try {
      await removeMember(org.id, userId);
    } catch (error: any) {
      alert(error.message || 'Failed to remove member');
    }
  };

  const handleRoleChange = async (userId: string, newRole: 'owner' | 'admin' | 'member') => {
    if (!org) return;
    
    try {
      await updateMemberRole(org.id, userId, newRole);
    } catch (error: any) {
      alert(error.message || 'Failed to update role');
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
          <h2 className="text-lg font-semibold">Admins & Members</h2>
          <p className="text-sm text-muted-foreground">
            Manage who can administer this organization
          </p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors"
        >
          <Plus size={16} />
          Add Member
        </button>
      </div>

      <div className="rounded-xl border bg-card">
        <div className="border-b px-4 py-3">
          <p className="text-sm font-medium text-muted-foreground">
            Organization Members ({members.length})
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
              <div key={member.id} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/10 text-blue-500">
                    <UserCircle size={20} />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{member.name || 'Unknown'}</p>
                    <p className="text-xs text-muted-foreground">{member.email}</p>
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
                  {member.role !== 'owner' && (
                    <button
                      onClick={() => handleRemove(member.userId)}
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

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-lg">
            <h3 className="text-lg font-semibold mb-4">Invite Member</h3>
            
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
                  onChange={(e) => setInviteRole(e.target.value as 'admin' | 'member')}
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
                onClick={handleInvite}
                disabled={!inviteEmail || inviteLoading}
                className={cn(
                  'flex-1 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors',
                  'hover:bg-blue-600',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {inviteLoading ? 'Inviting...' : 'Send Invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
