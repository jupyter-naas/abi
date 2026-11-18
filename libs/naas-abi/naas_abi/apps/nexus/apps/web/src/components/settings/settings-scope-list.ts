import { PLATFORM_SETTINGS_INDEX, firstPlatformSettingsPath, type PlatformActions } from '@/app/settings/lib/nav';
import { orgSettingsIndexPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import {
  settingsScopeReturnPath,
  type SettingsScopeKey,
  scopeKeysEqual,
} from '@/lib/settings-scope-path';

export type SettingsScopeMenuEntry =
  | { type: 'item'; id: string; label: string; href: string; current: boolean; external?: boolean }
  | { type: 'separator'; id: string };

export type OpenableOrganization = { id: string; name: string };

/** Pure list for the header scope switcher (Vitest covers access rules). */
export function buildSettingsScopeMenuEntries({
  currentScope,
  showPlatform,
  platformActions,
  organizations,
  workspace,
}: {
  currentScope: SettingsScopeKey;
  showPlatform: boolean;
  platformActions: PlatformActions | null;
  organizations: OpenableOrganization[];
  workspace: { id: string; name: string } | null;
}): SettingsScopeMenuEntry[] {
  const entries: SettingsScopeMenuEntry[] = [];

  if (showPlatform) {
    const href =
      settingsScopeReturnPath(
        { kind: 'platform' },
        firstPlatformSettingsPath(platformActions) ?? PLATFORM_SETTINGS_INDEX
      );
    entries.push({
      type: 'item',
      id: 'platform',
      label: 'Platform',
      href,
      current: currentScope.kind === 'platform',
    });
  }

  const accountHref = settingsScopeReturnPath({ kind: 'account' }, '/account/profile');
  entries.push({
    type: 'item',
    id: 'account',
    label: 'Account',
    href: accountHref,
    current: currentScope.kind === 'account',
  });

  if (organizations.length > 0) {
    entries.push({ type: 'separator', id: 'orgs-sep' });
    for (const org of organizations) {
      const scope: SettingsScopeKey = { kind: 'organization', orgId: org.id };
      const href = settingsScopeReturnPath(scope, orgSettingsIndexPath(org.id));
      entries.push({
        type: 'item',
        id: `org:${org.id}`,
        label: org.name,
        href,
        current: currentScope.kind === 'organization' && scopeKeysEqual(currentScope, scope),
      });
    }
  }

  if (workspace) {
    entries.push({ type: 'separator', id: 'workspace-sep' });
    const scope: SettingsScopeKey = { kind: 'workspace', workspaceId: workspace.id };
    entries.push({
      type: 'item',
      id: 'workspace',
      label: `Workspace · ${workspace.name}`,
      href: settingsScopeReturnPath(scope, `/workspace/${workspace.id}/settings`),
      current: false,
      external: true,
    });
  }

  return entries;
}