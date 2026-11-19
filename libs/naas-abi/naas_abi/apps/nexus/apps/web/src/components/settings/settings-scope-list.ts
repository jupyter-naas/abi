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

/**
 * Pure list for the header scope switcher (Vitest covers access rules).
 *
 * Scopes go by what they are, from the narrowest to the widest, as in the avatar
 * menu: Account, Organization, Platform. An organization's name shows only when
 * several are listed: it is then what tells them apart.
 */
export function buildSettingsScopeMenuEntries({
  currentScope,
  showPlatform,
  platformActions,
  organizations,
}: {
  currentScope: SettingsScopeKey;
  showPlatform: boolean;
  platformActions: PlatformActions | null;
  organizations: OpenableOrganization[];
}): SettingsScopeMenuEntry[] {
  const entries: SettingsScopeMenuEntry[] = [];

  entries.push({
    type: 'item',
    id: 'account',
    label: 'Account',
    href: settingsScopeReturnPath({ kind: 'account' }, '/account/profile'),
    current: currentScope.kind === 'account',
  });

  const several = organizations.length > 1;
  if (several) entries.push({ type: 'separator', id: 'orgs-sep' });
  for (const org of organizations) {
    const scope: SettingsScopeKey = { kind: 'organization', orgId: org.id };
    entries.push({
      type: 'item',
      id: `org:${org.id}`,
      label: several ? `Organization · ${org.name}` : 'Organization',
      href: settingsScopeReturnPath(scope, orgSettingsIndexPath(org.id)),
      current: currentScope.kind === 'organization' && scopeKeysEqual(currentScope, scope),
    });
  }

  if (showPlatform) {
    if (several) entries.push({ type: 'separator', id: 'platform-sep' });
    entries.push({
      type: 'item',
      id: 'platform',
      label: 'Platform',
      href: settingsScopeReturnPath(
        { kind: 'platform' },
        firstPlatformSettingsPath(platformActions) ?? PLATFORM_SETTINGS_INDEX
      ),
      current: currentScope.kind === 'platform',
    });
  }

  return entries;
}