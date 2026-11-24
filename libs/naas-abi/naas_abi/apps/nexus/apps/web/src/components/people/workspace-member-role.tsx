'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import {
  createMemberRolesApi,
  roleProblem,
  type MemberRef,
  type MemberRolesApi,
  type RoleOptions,
  type RoleSelection,
} from '@/lib/member-roles';
import { RoleEditor } from './role-editor';

const same = (a: RoleSelection, b: RoleSelection) =>
  [...a.groups].sort().join() === [...b.groups].sort().join() &&
  [...a.policies].sort().join() === [...b.policies].sort().join();

/**
 * A person's Role at a workspace, on their page (Users › Edit): the groups and policies they
 * hold here, changed as on Create user, then saved at once (`PUT …/roles`). An organization's
 * admin reaches the workspace without a level.
 */
export function WorkspaceMemberRole({
  workspaceId,
  principalId,
  onChanged,
  api,
}: {
  workspaceId: string;
  principalId: string;
  onChanged?: () => void;
  api?: MemberRolesApi;
}) {
  const roles = useMemo(() => api ?? createMemberRolesApi(), [api]);
  const [member, setMember] = useState<MemberRef | null | undefined>(undefined);
  const [options, setOptions] = useState<RoleOptions>({ groups: [], policies: [] });
  const [held, setHeld] = useState<RoleSelection>({ groups: [], policies: [] });
  const [role, setRole] = useState<RoleSelection>({ groups: [], policies: [] });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    (async () => {
      const found = await roles.member(workspaceId, principalId);
      if (!live) return;
      setMember(found);
      if (!found) return;
      const [offered, mine] = await Promise.all([roles.options(workspaceId), roles.held(workspaceId, found.userId)]);
      if (!live) return;
      setOptions(offered);
      setHeld(mine);
      setRole(mine);
    })().catch((e: unknown) => live && setError(e instanceof Error ? e.message : 'Could not load their roles'));
    return () => {
      live = false;
    };
  }, [roles, workspaceId, principalId]);

  if (member === null) return null; // not a member of this workspace: their page says the rest
  const reachesOtherwise = member?.source === 'organization';
  const changed = !same(role, held);
  const problem = roleProblem(options, role, reachesOtherwise);

  const save = async () => {
    if (!member) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await roles.set(workspaceId, member.userId, role);
      const mine = await roles.held(workspaceId, member.userId);
      setHeld(mine);
      setRole(mine);
      setNotice(`${member.name}'s Role here is saved.`);
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change their roles');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsSection
      title="Role in this workspace"
      description="The groups they are in and the policies attached to them here. A level (Members, Viewers) applies in all their workspaces."
    >
      <div className="space-y-3" data-member-role>
        {error && (
          <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
            {error}
          </SettingsNotice>
        )}
        {notice && <SettingsNotice tone="info">{notice}</SettingsNotice>}
        <RoleEditor
          options={options}
          value={role}
          onChange={setRole}
          disabled={saving || member === undefined}
          reachesOtherwise={reachesOtherwise}
        />
        <div className="flex gap-2">
          <Button size="sm" onClick={() => void save()} disabled={!changed || !!problem || saving} data-action="save-role">
            {saving ? 'Saving…' : 'Save'}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setRole(held)} disabled={!changed || saving}>
            Reset
          </Button>
        </div>
      </div>
    </SettingsSection>
  );
}
