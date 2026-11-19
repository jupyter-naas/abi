import { PLATFORM_SETTINGS_INDEX, firstPlatformSettingsPath, type PlatformActions } from '@/app/settings/lib/nav';
import { orgSettingsIndexPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import {
  settingsScopeReturnPath,
  type SettingsScopeKey,
  scopeKeysEqual,
} from '@/lib/settings-scope-path';

export type SettingsScopeMenuEntry =
  | { type: 'item'; id: string; label: string; href: string; current: boolean }
  | { type: 'separator'; id: string };

export type OpenableOrganization = { id: string; name: string };

/** Whether following ``href`` from ``pathname`` loads another page (query and hash aside). */
export function opensAnotherPage(href: string, pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return href.split(/[?#]/, 1)[0] !== pathname;
}

/** Pure list for the header scope switcher (Vitest covers access rules). */
export function buildSettingsScopeMenuEntries({
  currentScope,
  showPlatform,
  platformActions,
  organizations,
  accountName,
}: {
  currentScope: SettingsScopeKey;
  showPlatform: boolean;
  platformActions: PlatformActions | null;
  organizations: OpenableOrganization[];
  /** The signed-in user's name, the Account entry's label ("Account" without one). */
  accountName?: string | null;
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
    label: accountName?.trim() || 'Account',
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
        label: `Organization · ${org.name}`,
        href,
        current: currentScope.kind === 'organization' && scopeKeysEqual(currentScope, scope),
      });
    }
  }

  return entries;
}