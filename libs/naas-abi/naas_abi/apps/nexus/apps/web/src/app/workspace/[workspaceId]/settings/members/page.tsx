'use client';

import { useState, useEffect } from 'react';
import { Plus, Shield, User, Crown, Trash2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useParams } from 'next/navigation';

interface Member {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  avatar?: string;
  joinedAt: Date;
}

const roleConfig = {
  owner: { label: 'Owner', icon: Crown, color: 'text-yellow-500' },
  admin: { label: 'Admin', icon: Shield, color: 'text-primary' },
  member: { label: 'Member', icon: User, color: 'text-foreground' },
  viewer: { label: 'Viewer', icon: User, color: 'text-muted-foreground' },
};

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

export default function MembersPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const authUser = useAuthStore((s) => s.user);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const workspace = workspaces.find((w) => w.id === workspaceId);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'member' | 'viewer'>('member');
  const [showInvite, setShowInvite] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [actionError, setActionError] = useState('');

  const membershipRole =
    workspace?.currentUserRole ||
    members.find((m) => m.user_id === authUser?.id)?.role;
  const canManage =
    membershipRole === 'owner' || membershipRole === 'admin';

  const refreshMembers = async () => {
    const { authFetch } = await import('@/stores/auth');
    const response = await authFetch(`/api/workspaces/${workspaceId}/members`);
    if (!response.ok) {
      throw new Error(await readApiError(response, 'Failed to load members'));
    }
    const data = await response.json();
    setMembers(
      data.map((m: Record<string, unknown>) => ({
        ...m,
        name: (m.name as string) || 'Unknown',
        email: (m.email as string) || '',
        joinedAt: new Date(m.created_at as string),
      }))
    );
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

  const handleInvite = async () => {
    if (!inviteEmail.trim() || !canManage) return;

    setInviteError('');
    setInviteLoading(true);

    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/workspaces/${workspaceId}/members/invite`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
        }
      );

      if (!response.ok) {
        throw new Error(await readApiError(response, 'Failed to send invite'));
      }

      await refreshMembers();
      setInviteEmail('');
      setInviteRole('member');
      setShowInvite(false);
    } catch (error: unknown) {
      console.error('Failed to invite member:', error);
      setInviteError(
        error instanceof Error ? error.message : 'Failed to send invite'
      );
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!canManage) return;
    if (!confirm('Remove this member?')) return;

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

  const handleChangeRole = async (
    userId: string,
    newRole: 'admin' | 'member' | 'viewer'
  ) => {
    if (!canManage) return;
    setActionError('');
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/workspaces/${workspaceId}/members/${userId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: newRole }),
        }
      );
      if (!response.ok) {
        throw new Error(await readApiError(response, 'Failed to change role'));
      }

      setMembers(
        members.map((m) =>
          m.user_id === userId ? { ...m, role: newRole } : m
        )
      );
    } catch (error: unknown) {
      console.error('Failed to change role:', error);
      setActionError(
        error instanceof Error ? error.message : 'Failed to change role'
      );
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Members</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {members.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage who has access to this workspace
          </p>
        </div>
        <button
          onClick={() => {
            setInviteError('');
            setShowInvite(true);
          }}
          disabled={!canManage}
          title={
            canManage
              ? undefined
              : 'Only workspace owners and admins can invite members'
          }
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus size={16} />
          Invite Member
        </button>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {showInvite && canManage && (
        <div className="rounded-xl border bg-card p-4">
          <h3 className="mb-2 font-medium">Invite New Member</h3>
          <p className="mb-4 text-xs text-muted-foreground">
            Creates the account if needed and emails a sign-in code. Same API as{' '}
            <code className="text-[0.95em]">abi workspace members add</code> /{' '}
            <code className="text-[0.95em]">
              POST /api/workspaces/{'{id}'}/members/invite
            </code>
            .
          </p>

          {inviteError && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle size={16} />
              <span>{inviteError}</span>
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="flex-1">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="email@example.com"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <select
              value={inviteRole}
              onChange={(e) =>
                setInviteRole(e.target.value as typeof inviteRole)
              }
              className="rounded-lg border bg-background px-3 py-2 text-sm"
            >
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </select>
            <button
              onClick={() => void handleInvite()}
              disabled={!inviteEmail.trim() || inviteLoading}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {inviteLoading ? 'Sending...' : 'Send Invite'}
            </button>
            <button
              onClick={() => {
                setShowInvite(false);
                setInviteError('');
              }}
              className="rounded-lg border px-4 py-2 text-sm text-muted-foreground hover:bg-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border bg-card">
        {loading ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Loading members...
          </div>
        ) : members.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            No members yet.
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-sm text-muted-foreground">
                <th className="p-4 font-medium">Member</th>
                <th className="p-4 font-medium">Role</th>
                <th className="p-4 font-medium">Joined</th>
                <th className="p-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => {
                const role = roleConfig[member.role] || roleConfig.member;
                const RoleIcon = role.icon;
                const initial = (member.name || member.email || '?')
                  .charAt(0)
                  .toUpperCase();
                const roleLocked =
                  member.role === 'owner' ||
                  member.user_id === authUser?.id ||
                  !canManage;
                return (
                  <tr key={member.id} className="border-b last:border-0">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                          {initial}
                        </div>
                        <div>
                          <p className="font-medium">{member.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {member.email}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      {roleLocked ? (
                        <div
                          className={cn(
                            'flex items-center gap-2 text-sm',
                            role.color
                          )}
                        >
                          <RoleIcon size={14} />
                          {role.label}
                        </div>
                      ) : (
                        <select
                          value={member.role}
                          onChange={(e) =>
                            void handleChangeRole(
                              member.user_id,
                              e.target.value as 'admin' | 'member' | 'viewer'
                            )
                          }
                          className="rounded border bg-background px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                        >
                          <option value="member">Member</option>
                          <option value="viewer">Viewer</option>
                          <option value="admin">Admin</option>
                        </select>
                      )}
                    </td>
                    <td className="p-4 text-sm text-muted-foreground">
                      {member.joinedAt.toLocaleDateString()}
                    </td>
                    <td className="p-4 text-right">
                      {canManage &&
                        member.role !== 'owner' &&
                        member.user_id !== authUser?.id && (
                          <button
                            onClick={() =>
                              void handleRemoveMember(member.user_id)
                            }
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="rounded-xl border bg-muted/30 p-4">
        <h3 className="mb-3 font-medium">Role Permissions</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="font-medium text-sm">Member</p>
            <p className="text-xs text-muted-foreground">
              Can use agents, create content, and view data
            </p>
          </div>
          <div>
            <p className="font-medium text-sm">Viewer</p>
            <p className="text-xs text-muted-foreground">
              Read-only access to workspace content
            </p>
          </div>
          <div>
            <p className="font-medium text-sm">Admin</p>
            <p className="text-xs text-muted-foreground">
              Full access except billing and workspace deletion
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
