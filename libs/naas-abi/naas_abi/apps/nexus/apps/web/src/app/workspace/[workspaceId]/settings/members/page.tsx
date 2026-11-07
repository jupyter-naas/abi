'use client';

import { useState, useEffect, useMemo } from 'react';
import { Plus, Shield, User, Crown, Trash2, AlertCircle, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Select } from '@/components/ui/input';
import { IdpGroupBindings } from '@/components/invitations/idp-group-bindings';
import { PendingInvitations } from '@/components/invitations/pending-invitations';
import { InvitePolicyPicker } from '@/components/invitations/invite-policy-picker';
import { useInviteProviders } from '@/components/invitations/use-invite-providers';
import { workspaceAccessScope } from '@/components/access/access-scope';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import {
  classifyInviteAnswer,
  inviteSuccessMessage,
  providerHint,
  workspaceInviteBody,
} from '@/lib/invitations';
import { ROLE_LABELS, assignableRoles, changeMemberRole, roleChangeable } from '@/components/access/roles/role-change';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsFilterSelect,
  SettingsSection,
  SettingsTableToolbar,
  countLabel,
  settingsTable,
} from '@/components/settings/settings-ui';

interface Member {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  avatar?: string;
  joinedAt: Date | null;
  /** 'organization': no membership row; access comes from the org owner/admin role. */
  source: 'workspace' | 'organization';
}

const roleConfig = {
  owner: { label: 'Owner', icon: Crown, color: 'text-primary' },
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
  // Policies attached at this workspace with the role (features come from policies).
  const [invitePolicyIds, setInvitePolicyIds] = useState<string[]>([]);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [inviteNotice, setInviteNotice] = useState('');
  const [invitationsKey, setInvitationsKey] = useState(0);
  const providers = useInviteProviders(showInvite);
  const [actionError, setActionError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const { confirm: confirmRemove, dialog: confirmDialog } = useConfirm();

  const organizationId = workspaceOrganization(workspace);
  const inviteScope = useMemo(
    () => (workspace?.id ? workspaceAccessScope(organizationId, workspace.id).value : null),
    [organizationId, workspace?.id]
  );

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
        joinedAt: m.created_at ? new Date(m.created_at as string) : null,
        source: m.source === 'organization' ? 'organization' : 'workspace',
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
          body: JSON.stringify(
            workspaceInviteBody({
              email: inviteEmail.trim(),
              role: inviteRole,
              provider: providers.providerToSend(),
              policyIds: invitePolicyIds,
            })
          ),
        }
      );

      if (!response.ok) {
        throw new Error(await readApiError(response, 'Failed to send invite'));
      }

      // Someone with no account yet is invited, not added: they show in the
      // pending invitations until they sign in.
      const answer = classifyInviteAnswer(await response.json().catch(() => null));
      setInviteNotice(answer.kind === 'invited' ? inviteSuccessMessage(answer) : '');
      setInvitationsKey((key) => key + 1);
      await refreshMembers();
      setInviteEmail('');
      setInviteRole('member');
      setInvitePolicyIds([]);
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

  // The same role change as Roles & permissions › People & roles: the membership route, IAM decides.
  const handleChangeRole = async (
    userId: string,
    newRole: 'admin' | 'member' | 'viewer'
  ) => {
    if (!canManage) return;
    setActionError('');
    try {
      await changeMemberRole({ level: 'workspace', workspaceId }, userId, newRole);

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

  const query = searchQuery.trim().toLowerCase();
  const filteredMembers = members.filter((member) => {
    if (roleFilter !== 'all' && member.role !== roleFilter) return false;
    return !query || member.name.toLowerCase().includes(query) || member.email.toLowerCase().includes(query);
  });
  const adminCount = members.filter((m) => m.role === 'owner' || m.role === 'admin').length;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Members"
        badge={`${members.length} active`}
        description="Manage who has access to this workspace"
        actions={
          <Button
            onClick={() => {
              setInviteError('');
              setInviteNotice('');
              setShowInvite(true);
            }}
            disabled={!canManage}
            title={canManage ? undefined : 'Only workspace owners and admins can invite members'}
          >
            <Plus size={16} />
            Invite Member
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

      {showInvite && canManage && (
        <SettingsSection
          title="Invite New Member"
          description={
            providers.known.enabled ? (
              <>
                The person is created at the identity provider if needed, and their role applies
                when they first sign in with this email. Same API as{' '}
                <code>abi workspace members add</code> / <code>POST /api/workspaces/{'{id}'}/members/invite</code>.
              </>
            ) : (
              <>
                Creates the account if needed and emails a sign-in code. Same API as{' '}
                <code>abi workspace members add</code> / <code>POST /api/workspaces/{'{id}'}/members/invite</code>.
              </>
            )
          }
        >
          {inviteError && (
            <SettingsNotice tone="error" icon={<AlertCircle size={14} />} className="mb-4">
              {inviteError}
            </SettingsNotice>
          )}

          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="email@example.com"
              className="flex-1"
            />
            {providers.choosable && (
              <Select
                value={providers.picked ?? ''}
                onChange={(e) => providers.setPicked(e.target.value)}
                className="sm:w-48"
                aria-label="Identity provider"
              >
                {providers.known.providers.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.display_name}
                  </option>
                ))}
              </Select>
            )}
            <Select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}
              className="sm:w-40"
            >
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </Select>
            <Button onClick={() => void handleInvite()} disabled={!inviteEmail.trim() || inviteLoading}>
              {inviteLoading ? 'Sending...' : 'Send Invite'}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setShowInvite(false);
                setInviteError('');
                setInvitePolicyIds([]);
              }}
            >
              Cancel
            </Button>
          </div>
          {providers.known.enabled && providerHint(providers.chosen) && (
            <p className="mt-3 text-xs text-muted-foreground">{providerHint(providers.chosen)}</p>
          )}
          <InvitePolicyPicker
            className="mt-4 max-w-xl"
            scope={showInvite ? inviteScope : null}
            value={invitePolicyIds}
            onChange={setInvitePolicyIds}
            disabled={inviteLoading}
          />
        </SettingsSection>
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
          searchPlaceholder="Search members by name or email..."
          filters={
            <SettingsFilterSelect
              label="Role"
              value={roleFilter}
              onChange={setRoleFilter}
              options={[
                { value: 'all', label: 'All roles' },
                ...(Object.keys(roleConfig) as (keyof typeof roleConfig)[]).map((role) => ({
                  value: role,
                  label: roleConfig[role].label,
                })),
              ]}
            />
          }
          meta={`${countLabel(filteredMembers.length, members.length, 'member')} · ${adminCount} owner${adminCount === 1 ? '' : 's'} or admin${adminCount === 1 ? '' : 's'}`}
        />
        <div className={settingsTable.wrapper}>
          <table className={settingsTable.table}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Member</th>
                <th className={settingsTable.th}>Role</th>
                <th className={settingsTable.th}>Joined</th>
                <th className={cn(settingsTable.th, 'text-right')}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredMembers.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-muted-foreground">
                    No members match the current search and filters
                  </td>
                </tr>
              )}
              {filteredMembers.map((member) => {
                const role = roleConfig[member.role] || roleConfig.member;
                const RoleIcon = role.icon;
                const initial = (member.name || member.email || '?').charAt(0).toUpperCase();
                const inherited = member.source === 'organization';
                const roleLocked =
                  !canManage ||
                  !roleChangeable({ role: member.role, inherited, userId: member.user_id, selfId: authUser?.id });
                return (
                  <tr key={member.id} className={settingsTable.row}>
                    <td className={settingsTable.td}>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center bg-primary text-primary-foreground">
                          {initial}
                        </div>
                        <div>
                          <p className="flex items-center gap-2 font-medium">
                            {member.name}
                            {inherited && (
                              <span
                                className="border border-border px-1.5 py-0.5 text-[10px] font-normal uppercase tracking-wide text-muted-foreground"
                                title="Organization owners and admins reach every workspace of the organization. Manage them in Organization > Users."
                              >
                                via organization
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-muted-foreground">{member.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className={settingsTable.td}>
                      {roleLocked ? (
                        <div className={cn('flex items-center gap-2', role.color)}>
                          <RoleIcon size={14} />
                          {role.label}
                        </div>
                      ) : (
                        <Select
                          value={member.role}
                          onChange={(e) =>
                            void handleChangeRole(member.user_id, e.target.value as 'admin' | 'member' | 'viewer')
                          }
                          className="h-8 w-32"
                        >
                          {assignableRoles('workspace').map((r) => (
                            <option key={r} value={r}>
                              {ROLE_LABELS[r]}
                            </option>
                          ))}
                        </Select>
                      )}
                    </td>
                    <td className={cn(settingsTable.td, 'text-muted-foreground')}>
                      {member.joinedAt ? member.joinedAt.toLocaleDateString() : '—'}
                    </td>
                    <td className={cn(settingsTable.td, 'text-right')}>
                      {canManage && !inherited && member.role !== 'owner' && member.user_id !== authUser?.id && (
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

      <PendingInvitations
        scope="workspaces"
        id={workspaceId}
        canManage={canManage}
        refreshKey={invitationsKey}
      />

      <IdpGroupBindings scope="workspaces" id={workspaceId} canManage={canManage} />

      <SettingsSection title="Role Permissions">
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-sm font-medium">Member</p>
            <p className="text-xs text-muted-foreground">Can use agents, create content, and view data</p>
          </div>
          <div>
            <p className="text-sm font-medium">Viewer</p>
            <p className="text-xs text-muted-foreground">Read-only access to workspace content</p>
          </div>
          <div>
            <p className="text-sm font-medium">Admin</p>
            <p className="text-xs text-muted-foreground">Full access except billing and workspace deletion</p>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Organization owners and admins have owner or admin access to every workspace of the
          organization without being invited here. People invited here are also added to the
          organization as members. Features (chat, files, graph, …) come from policies granting
          them, not from the role: pick them when inviting, or attach them in Roles &amp; permissions.
        </p>
      </SettingsSection>
      {confirmDialog}
    </div>
  );
}
