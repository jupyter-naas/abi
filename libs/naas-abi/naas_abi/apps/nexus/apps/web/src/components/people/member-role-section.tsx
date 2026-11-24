'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import {
  createMemberRolesApi,
  roleProblem,
  type MemberRolesApi,
  type RoleOptions,
  type RoleScope,
  type RoleSelection,
} from '@/lib/member-roles';
import { RoleEditor } from './role-editor';

const same = (a: RoleSelection, b: RoleSelection) =>
  [...a.groups].sort().join() === [...b.groups].sort().join() &&
  [...a.policies].sort().join() === [...b.policies].sort().join();

const TITLES: Record<RoleScope['kind'], string> = {
  workspace: 'Role in this workspace',
  organization: 'Role in this organization',
  platform: 'Role on the platform',
};

/**
 * A person's Role at a workspace, an organization or the platform, on their page (Users ›
 * a person): the groups and policies they hold there, changed as on Create user, then saved at
 * once (`PUT …/roles`). At a workspace the page names them by their IAM id (`principalId`):
 * they are found among its members (an organization's admin reaches it without a level).
 */
export function MemberRoleSection({
  scope,
  userId,
  principalId,
  onChanged,
  api,
}: {
  scope: RoleScope;
  /** Their Nexus id (an organization's, the platform's page; the platform takes their IAM id too). */
  userId?: string;
  /** At a workspace: their IAM id, looked up among its members. */
  principalId?: string;
  onChanged?: () => void;
  api?: MemberRolesApi;
}) {
  const roles = useMemo(() => api ?? createMemberRolesApi(), [api]);
  const [person, setPerson] = useState<{ userId: string; name: string; reachesOtherwise: boolean } | null | undefined>(
    undefined
  );
  const [options, setOptions] = useState<RoleOptions>({ groups: [], policies: [] });
  const [held, setHeld] = useState<RoleSelection>({ groups: [], policies: [] });
  const [role, setRole] = useState<RoleSelection>({ groups: [], policies: [] });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const scopeKey = scope.kind === 'platform' ? 'platform' : `${scope.kind}:${scope.id}`;

  useEffect(() => {
    let live = true;
    (async () => {
      let found: { userId: string; name: string; reachesOtherwise: boolean } | null = null;
      if (scope.kind === 'workspace' && principalId && !userId) {
        const member = await roles.member(scope.id, principalId);
        found = member ? { userId: member.userId, name: member.name, reachesOtherwise: member.source === 'organization' } : null;
      } else if (userId) {
        found = { userId, name: 'They', reachesOtherwise: scope.kind === 'platform' };
      }
      if (!live) return;
      setPerson(found);
      if (!found) return;
      const [offered, mine] = await Promise.all([roles.options(scope), roles.held(scope, found.userId)]);
      if (!live) return;
      setOptions(offered);
      setHeld(mine);
      setRole(mine);
    })().catch((e: unknown) => live && setError(e instanceof Error ? e.message : 'Could not load their roles'));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `scope` is read through its key
  }, [roles, scopeKey, userId, principalId]);

  if (person === null) return null; // not one of its people: their page says the rest
  const reachesOtherwise = !!person?.reachesOtherwise;
  const changed = !same(role, held);
  const problem = roleProblem(options, role, reachesOtherwise);

  const save = async () => {
    if (!person) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await roles.set(scope, person.userId, role);
      const mine = await roles.held(scope, person.userId);
      setHeld(mine);
      setRole(mine);
      setNotice('Their Role is saved.');
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change their roles');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsSection
      title={TITLES[scope.kind]}
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
          disabled={saving || person === undefined}
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
