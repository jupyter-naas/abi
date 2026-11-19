import { Building2, type LucideIcon } from 'lucide-react';
import type { AccountSettingsNavItem } from '@/app/account/lib/nav';
import {
  orgSettingsIndexPath,
  orgSettingsSectionPath,
  type OrgSettingsNavItem,
} from '@/app/organizations/[orgId]/settings/lib/nav';
import type { PlatformSettingsNavItem } from '@/app/settings/lib/nav';
import type { SettingsNavGroup } from '@/components/shell/settings-nav';

/**
 * Settings, one column for every level, from the narrowest to the widest: what a change
 * there touches. Account is the caller alone, Workspace this workspace, Organization all
 * of its workspaces, Platform the whole instance. A level shows only what the caller may
 * open there, and a level with nothing is left out: a member sees Account and Workspace.
 */

export type SettingsLink = { href: string; label: string; icon: LucideIcon };

/** `label` null: the level's first group, named by the level itself. */
export type SettingsLinkGroup = { label: string | null; links: SettingsLink[] };

export type SettingsLevel = { id: string; label: string; groups: SettingsLinkGroup[] };

export type SettingsOrganization = { id: string; name: string; items: OrgSettingsNavItem[] };

export type SettingsLevelsInput = {
  account: AccountSettingsNavItem[];
  /** The current workspace and its groups the caller may open; null without one. */
  workspace: { id: string; groups: SettingsNavGroup[] } | null;
  /** The organization of the page (or of the current workspace), and the other ones the caller opens. */
  organization: SettingsOrganization | null;
  otherOrganizations: { id: string; name: string }[];
  platform: PlatformSettingsNavItem[];
};

function link(item: { href: string; label: string; icon: LucideIcon }, href = item.href): SettingsLink {
  return { href, label: item.label, icon: item.icon };
}

export function settingsLevels(input: SettingsLevelsInput): SettingsLevel[] {
  const levels: SettingsLevel[] = [
    { id: 'account', label: 'Account', groups: [{ label: null, links: input.account.map((item) => link(item)) }] },
  ];

  const { workspace } = input;
  const workspaceGroups = (workspace?.groups ?? []).filter((group) => group.items.length > 0);
  if (workspace && workspaceGroups.length > 0) {
    levels.push({
      id: 'workspace',
      label: 'Workspace',
      groups: workspaceGroups.map((group, index) => ({
        label: index === 0 ? null : group.label,
        links: group.items.map((item) => link(item, `/workspace/${workspace.id}${item.href}`)),
      })),
    });
  }

  const others = input.otherOrganizations.map((org) => ({
    href: orgSettingsIndexPath(org.id),
    label: org.name,
    icon: Building2,
  }));
  const organization = input.organization && input.organization.items.length > 0 ? input.organization : null;
  if (organization) {
    const groups: SettingsLinkGroup[] = [
      {
        label: null,
        links: organization.items.map((item) => link({ ...item, href: orgSettingsSectionPath(organization.id, item.slug) })),
      },
    ];
    if (others.length > 0) groups.push({ label: 'Other organizations', links: others });
    levels.push({
      id: 'organization',
      label: others.length > 0 ? `Organization · ${organization.name}` : 'Organization',
      groups,
    });
  } else if (others.length > 0) {
    levels.push({ id: 'organization', label: 'Organizations', groups: [{ label: null, links: others }] });
  }

  if (input.platform.length > 0) {
    levels.push({ id: 'platform', label: 'Platform', groups: [{ label: null, links: input.platform.map((item) => link(item)) }] });
  }
  return levels;
}

/** The link a path opens: the longest one it is, or is under. */
export function activeSettingsHref(levels: SettingsLevel[], pathname: string): string | null {
  const path = pathname.replace(/[?#].*$/, '').replace(/\/+$/, '') || '/';
  let best: string | null = null;
  for (const level of levels) {
    for (const group of level.groups) {
      for (const { href } of group.links) {
        if ((path === href || path.startsWith(`${href}/`)) && (!best || href.length > best.length)) best = href;
      }
    }
  }
  return best;
}
