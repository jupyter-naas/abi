'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Mail, RefreshCw, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { SettingsNotice, SettingsSection, settingsTable } from '@/components/settings/settings-ui';
import {
  fetchInvitations,
  invitationRoles,
  resendInvitation,
  revokeInvitation,
  type Invitation,
  type InviteScope,
} from '@/lib/invitations';

/**
 * The invitations still waiting for their person to sign in, with resend and
 * revoke. Reloads when `refreshKey` changes (after an invite). Renders nothing
 * while there is none, so a deployment without identity providers never sees it.
 */
export function PendingInvitations({
  scope,
  id,
  canManage,
  refreshKey = 0,
}: {
  scope: InviteScope;
  id: string;
  canManage: boolean;
  refreshKey?: number;
}) {
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const { confirm, dialog } = useConfirm();

  const load = useCallback(async () => {
    try {
      setInvitations(await fetchInvitations(scope, id));
      setError('');
    } catch (failure) {
      setInvitations([]);
      setError(failure instanceof Error ? failure.message : 'Failed to load invitations');
    }
  }, [scope, id]);

  useEffect(() => {
    if (canManage && id) void load();
  }, [canManage, id, load, refreshKey]);

  if (!canManage || (invitations.length === 0 && !error)) return null;

  const resend = async (invitation: Invitation) => {
    setBusy(invitation.id);
    setNotice('');
    setError('');
    try {
      const sent = await resendInvitation(invitation.id);
      setNotice(
        sent.sign_in_email_sent
          ? `Invitation emailed again to ${invitation.email}.`
          : `No email could be sent to ${invitation.email}.`
      );
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Failed to resend the invitation');
    } finally {
      setBusy(null);
    }
  };

  const revoke = async (invitation: Invitation) => {
    if (
      !(await confirm({
        title: `Revoke the invitation of ${invitation.email}?`,
        confirmLabel: 'Revoke',
      }))
    ) {
      return;
    }
    setBusy(invitation.id);
    setNotice('');
    setError('');
    try {
      await revokeInvitation(invitation.id);
      await load();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Failed to revoke the invitation');
    } finally {
      setBusy(null);
    }
  };

  return (
    <SettingsSection
      title="Pending invitations"
      description="Invited people who have not signed in yet. Their roles apply the first time they sign in with this email."
    >
      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />} className="mb-4">
          {error}
        </SettingsNotice>
      )}
      {notice && (
        <SettingsNotice tone="info" icon={<Mail size={14} />} className="mb-4">
          {notice}
        </SettingsNotice>
      )}
      <div className={settingsTable.wrapper}>
        <table className={settingsTable.table}>
          <thead>
            <tr className={settingsTable.headRow}>
              <th className={settingsTable.th}>Email</th>
              <th className={settingsTable.th}>Role</th>
              <th className={settingsTable.th}>Provider</th>
              <th className={settingsTable.th}>Invited</th>
              <th className={`${settingsTable.th} text-right`}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invitations.map((invitation) => (
              <tr key={invitation.id} className={settingsTable.row}>
                <td className={settingsTable.td}>{invitation.email}</td>
                <td className={settingsTable.td}>{invitationRoles(invitation)}</td>
                <td className={settingsTable.td}>{invitation.provider}</td>
                <td className={`${settingsTable.td} text-muted-foreground`}>
                  {invitation.created_at ? new Date(invitation.created_at).toLocaleDateString() : '—'}
                </td>
                <td className={`${settingsTable.td} text-right`}>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="secondary"
                      size="icon"
                      title="Resend the invitation"
                      disabled={busy === invitation.id}
                      onClick={() => void resend(invitation)}
                    >
                      <RefreshCw size={14} />
                    </Button>
                    <Button
                      variant="destructive-ghost"
                      size="icon"
                      title="Revoke the invitation"
                      disabled={busy === invitation.id}
                      onClick={() => void revoke(invitation)}
                    >
                      <X size={14} />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {dialog}
    </SettingsSection>
  );
}
