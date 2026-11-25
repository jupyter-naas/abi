'use client';

import { useState, useEffect } from 'react';
import { Plus, Shield, UserCircle, Trash2, Mail } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { PendingInvitations } from '@/components/invitations/pending-invitations';
import { IdpGroupBindings } from '@/components/invitations/idp-group-bindings';
import { CapabilityGroupPicker } from '@/components/invitations/invite-policy-picker';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog } from '@/components/ui/dialog';
import { useConfirm } from '@/components/ui/dialogs';
import { Field } from '@/components/ui/field';
import { Input, Select } from '@/components/ui/input';
import { Notice } from '@/components/ui/notice';
import { toast } from '@/components/ui/toast';
import { useInviteProviders } from '@/components/invitations/use-invite-providers';
import { inviteSuccessMessage, providerHint } from '@/lib/invitations';

export default function OrgUsersPage() {
  const authUser = useAuthStore((s) => s.user);
  const {
    organizations,
    fetchOrganizations,
    fetchMembers,
    inviteToOrganization,
    removeFromOrganization,
    membersCache,
    membersLoading,
  } = useOrganizationStore();

  const org = organizations[0];
  const members = org ? membersCache[org.id] || [] : [];
  const myMembership = members.find((m) => m.userId === authUser?.id);
  const canManage = myMembership?.orgAdmin === true;

  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteOrgAdmin, setInviteOrgAdmin] = useState(false);
  // Capability groups beside their level (#1589): no policy is given to a person.
  const [inviteCapabilities, setInviteCapabilities] = useState<string[]>([]);
  const [inviteError, setInviteError] = useState('');
  const [inviteNotice, setInviteNotice] = useState('');
  const [invitationsKey, setInvitationsKey] = useState(0);
  const providers = useInviteProviders(showInviteModal);
  const [inviteLoading, setInviteLoading] = useState(false);
  const { confirm, dialog: confirmDialog } = useConfirm();

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
      const { answer } = await inviteToOrganization(org.id, {
        email: inviteEmail.trim(),
        orgAdmin: inviteOrgAdmin,
        provider: providers.providerToSend(),
        capabilities: inviteCapabilities,
      });
      if (answer.kind === 'invited') {
        setInviteNotice(inviteSuccessMessage(answer));
        setInvitationsKey((key) => key + 1);
      } else {
        setInviteNotice('');
      }
      setShowInviteModal(false);
      setInviteEmail('');
      setInviteOrgAdmin(false);
      setInviteCapabilities([]);
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
    const ok = await confirm({
      title: 'Remove them from the organization?',
      description: 'They leave all its workspaces; their account is kept.',
      confirmLabel: 'Remove',
    });
    if (!ok) return;

    try {
      await removeFromOrganization(org.id, userId);
    } catch (error: unknown) {
      toast.error('Failed to remove member', error instanceof Error ? error.message : undefined);
    }
  };

  const closeInvite = () => {
    setShowInviteModal(false);
    setInviteEmail('');
    setInviteError('');
    setInviteCapabilities([]);
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
          onClick={() => {
            setInviteNotice('');
            setShowInviteModal(true);
          }}
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

      {inviteNotice && (
        <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
          <Mail size={16} className="mt-0.5 shrink-0" />
          <span>{inviteNotice}</span>
        </div>
      )}

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
                  {member.orgAdmin && (
                    <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-500">
                      <Shield size={12} />
                      Admin
                    </span>
                  )}
                  {!member.orgAdmin && member.role !== null && (
                    <span className="flex items-center gap-1 rounded-full bg-gray-500/10 px-2 py-0.5 text-xs font-medium text-gray-500">
                      <UserCircle size={12} />
                      {member.level === 'viewer' || member.role === 'viewer' ? 'Viewer' : 'Member'}
                    </span>
                  )}
                  {canManage && member.userId !== authUser?.id && (
                      <button
                        onClick={() => void handleRemove(member.userId)}
                        className="text-red-500 hover:text-red-600 transition-colors"
                        title="Remove from organization"
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

      <PendingInvitations
        scope="organizations"
        id={org.id}
        canManage={canManage}
        refreshKey={invitationsKey}
      />

      <IdpGroupBindings scope="organizations" id={org.id} canManage={canManage} />

      {confirmDialog}
      <Dialog
        open={showInviteModal && canManage}
        title="Add User"
        description={
          <>
            {providers.known.enabled
              ? 'The identity provider creates the account if needed; their access applies when they first sign in with this email. Same API as'
              : 'Creates the account if needed and emails a sign-in code. Same API as'}{' '}
            <code>POST /api/organizations/{'{id}'}/members/invite</code>.
          </>
        }
        onClose={closeInvite}
        footer={
          <>
            <Button variant="ghost" onClick={closeInvite}>
              Cancel
            </Button>
            <Button onClick={() => void handleInvite()} disabled={!inviteEmail.trim() || inviteLoading}>
              {inviteLoading ? 'Adding...' : 'Add User'}
            </Button>
          </>
        }
      >
        {inviteError && <Notice tone="error">{inviteError}</Notice>}
        <Field label="Email" htmlFor="org-invite-email">
          <Input
            id="org-invite-email"
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="user@example.com"
          />
        </Field>
        {providers.choosable && (
          <Field label="Identity provider" htmlFor="org-invite-provider">
            <Select
              id="org-invite-provider"
              value={providers.picked ?? ''}
              onChange={(e) => providers.setPicked(e.target.value)}
            >
              {providers.known.providers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.display_name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        {providers.known.enabled && providerHint(providers.chosen) && (
          <p className="text-xs text-muted-foreground">{providerHint(providers.chosen)}</p>
        )}
        <Checkbox label="Org admin" checked={inviteOrgAdmin} onCheckedChange={setInviteOrgAdmin} disabled={inviteLoading} />
        <CapabilityGroupPicker
          at={{ organizationId: org.id }}
          value={inviteCapabilities}
          onChange={setInviteCapabilities}
          disabled={inviteLoading}
        />
      </Dialog>
    </div>
  );
}
