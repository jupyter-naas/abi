'use client';

import { Suspense, useState, useEffect, useMemo } from 'react';
import { Plus, Shield, User, Crown, Trash2, AlertCircle, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { Select } from '@/components/ui/input';
import { IdpGroupBindings } from '@/components/invitations/idp-group-bindings';
import { PendingInvitations } from '@/components/invitations/pending-invitations';
import { workspaceAccessScope } from '@/components/access/access-scope';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import { AddPeople } from '@/components/people/add-people';
import { InvitedBadge, ResendButton } from '@/components/people/member-status';
import {
  addedNotice,
  candidateLabel,
  createPeopleApi,
  createUserHref,
  memberStatus,
  type MemberStatus,
} from '@/lib/people';
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
  /** Invited: created, has not signed in yet. */
  status: MemberStatus;
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
  // Said once: a reload does not say it again.
  useEffect(() => {
    if (search.get('added')) router.replace(`/workspace/${workspaceId}/settings/users`);
    // Read on arrival only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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
        status: memberStatus(m.status),
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
            onClick={() => router.push(createUserHref(workspaceId, ''))}
            disabled={!canManage}
            title={canManage ? undefined : 'Only workspace owners and admins can add members'}
          >
            <Plus size={16} />
            Create user
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
        <SettingsSection
          title="Add people"
          description="Search this workspace's organization by name or email. Picking someone adds them at once with the role you choose; with no match, create them."
        >
          <AddPeople
            workspaceId={workspaceId}
            callerRole={membershipRole}
            policyScope={inviteScope}
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
                            <InvitedBadge status={member.status} />
                            {inherited && (
                              <span
                                className="border border-border px-1.5 py-0.5 text-[10px] font-normal uppercase tracking-wide text-muted-foreground"
                                title="Organization owners and admins reach every workspace of the organization. Manage them in Organization > Users."
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

      {/* Invitations made before people were created at once: listed until they are migrated. */}
      <PendingInvitations scope="workspaces" id={workspaceId} canManage={canManage} />

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
          organization without being added here. People added here are listed in the
          organization&apos;s users as having workspace access only: they get no organization role.
          Features (chat, files, graph, …) come from policies granting them, not from the role:
          pick them when adding someone, or attach them in Roles &amp; permissions.
        </p>
      </SettingsSection>
      {confirmDialog}
    </div>
  );
}
