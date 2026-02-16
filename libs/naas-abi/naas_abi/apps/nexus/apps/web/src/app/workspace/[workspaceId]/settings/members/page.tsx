'use client';

import { useState, useEffect } from 'react';
import { Plus, Mail, MoreVertical, Shield, User, Crown, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
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

export default function MembersPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const authUser = useAuthStore((s) => s.user);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'member' | 'viewer'>('member');
  const [showInvite, setShowInvite] = useState(false);

  // Fetch members
  useEffect(() => {
    const fetchMembers = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/workspaces/${workspaceId}/members`);
        const data = await response.json();
        setMembers(data.map((m: any) => ({
          ...m,
          joinedAt: new Date(m.created_at),
        })));
      } catch (error) {
        console.error('Failed to fetch members:', error);
      } finally {
        setLoading(false);
      }
    };
    
    if (workspaceId) {
      fetchMembers();
    }
  }, [workspaceId]);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    
    try {
      const { authFetch } = await import('@/stores/auth');
      await authFetch(`/api/workspaces/${workspaceId}/members/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      
      // Refresh members list
      const response = await authFetch(`/api/workspaces/${workspaceId}/members`);
      const data = await response.json();
      setMembers(data.map((m: any) => ({
        ...m,
        joinedAt: new Date(m.created_at),
      })));
      
      setInviteEmail('');
      setShowInvite(false);
    } catch (error: any) {
      console.error('Failed to invite member:', error);
      alert(error.message || 'Failed to send invite');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!confirm('Remove this member?')) return;
    
    try {
      const { authFetch } = await import('@/stores/auth');
      await authFetch(`/api/workspaces/${workspaceId}/members/${userId}`, {
        method: 'DELETE',
      });
      
      setMembers(members.filter(m => m.user_id !== userId));
    } catch (error: any) {
      console.error('Failed to remove member:', error);
      alert(error.message || 'Failed to remove member');
    }
  };

  const handleChangeRole = async (userId: string, newRole: 'admin' | 'member' | 'viewer') => {
    try {
      const { authFetch } = await import('@/stores/auth');
      await authFetch(`/api/workspaces/${workspaceId}/members/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      });
      
      // Update local state
      setMembers(members.map(m => 
        m.user_id === userId ? { ...m, role: newRole } : m
      ));
    } catch (error: any) {
      console.error('Failed to change role:', error);
      alert(error.message || 'Failed to change role');
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
          onClick={() => setShowInvite(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus size={16} />
          Invite Member
        </button>
      </div>

      {/* Invite form */}
      {showInvite && (
        <div className="rounded-xl border bg-card p-4">
          <h3 className="mb-4 font-medium">Invite New Member</h3>
          <div className="flex gap-3">
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
              onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}
              className="rounded-lg border bg-background px-3 py-2 text-sm"
            >
              <option value="admin">Admin</option>
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
            </select>
            <button
              onClick={handleInvite}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Send Invite
            </button>
            <button
              onClick={() => setShowInvite(false)}
              className="rounded-lg border px-4 py-2 text-sm text-muted-foreground hover:bg-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Members list */}
      <div className="rounded-xl border bg-card">
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
              const role = roleConfig[member.role];
              const RoleIcon = role.icon;
              return (
                <tr key={member.id} className="border-b last:border-0">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                        {member.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium">{member.name}</p>
                        <p className="text-sm text-muted-foreground">{member.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    {member.role === 'owner' || member.user_id === authUser?.id ? (
                      <div className={cn('flex items-center gap-2 text-sm', role.color)}>
                        <RoleIcon size={14} />
                        {role.label}
                      </div>
                    ) : (
                      <select
                        value={member.role}
                        onChange={(e) => handleChangeRole(member.user_id, e.target.value as 'admin' | 'member' | 'viewer')}
                        className="rounded border bg-background px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                      >
                        <option value="admin">Admin</option>
                        <option value="member">Member</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    )}
                  </td>
                  <td className="p-4 text-sm text-muted-foreground">
                    {member.joinedAt.toLocaleDateString()}
                  </td>
                  <td className="p-4 text-right">
                    {member.role !== 'owner' && member.user_id !== authUser?.id && (
                      <button 
                        onClick={() => handleRemoveMember(member.user_id)}
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
      </div>

      {/* Pending invites */}
      <div className="rounded-xl border bg-card p-6">
        <h3 className="mb-4 font-semibold">Pending Invites</h3>
        <p className="text-sm text-muted-foreground">No pending invites</p>
      </div>

      {/* Roles explanation */}
      <div className="rounded-xl border bg-muted/30 p-4">
        <h3 className="mb-3 font-medium">Role Permissions</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="font-medium text-sm">Admin</p>
            <p className="text-xs text-muted-foreground">
              Full access except billing and workspace deletion
            </p>
          </div>
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
        </div>
      </div>
    </div>
  );
}
