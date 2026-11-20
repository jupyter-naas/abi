import { Building2, type LucideIcon } from 'lucide-react';
import type { AccountSettingsNavItem } from '@/app/account/lib/nav';
import {
  orgSettingsIndexPath,
  orgSettingsSectionPath,
  type OrgSettingsNavItem,
} from '@/app/organizations/[orgId]/settings/lib/nav';
import { PLATFORM_SETTINGS_INDEX, type PlatformSettingsNavGroup } from '@/app/settings/lib/nav';
import type { SettingsNavGroup } from '@/components/shell/settings-nav';
import { settingsScopeFromPathname, type SettingsLevelId } from '@/lib/settings-scope-path';

/**
 * Settings, one tab per level, from the widest to the narrowest: what a change there
 * touches. Platform is the whole instance, Organization all of its workspaces, Workspace
 * this workspace, Account the caller alone. A level shows only what the caller may open
 * there, and a level with nothing is left out: a plain member has Account alone.
 */

export type SettingsLink = { href: string; label: string; icon: LucideIcon };

/** `label` null: the level's first group, named by its tab. */
export type SettingsLinkGroup = { label: string | null; links: SettingsLink[] };

/** `index`: the level's own URL, where a phone lists its pages. */
export type SettingsLevel = { id: SettingsLevelId; label: string; index: string; groups: SettingsLinkGroup[] };

/** `current`: the current workspace's organization. Any other is named in its tab, so
 *  "Organization" never stands for one the workspace is not in. */
export type SettingsOrganization = { id: string; name: string; items: OrgSettingsNavItem[]; current: boolean };

export type SettingsLevelsInput = {
  account: AccountSettingsNavItem[];
  /** The current workspace and its groups the caller may open; null without one. */
  workspace: { id: string; groups: SettingsNavGroup[] } | null;
  /** The organization of the page (or of the current workspace), and the other ones the caller opens. */
  organization: SettingsOrganization | null;
  otherOrganizations: { id: string; name: string }[];
  /** The platform's groups the caller may open. */
  platform: PlatformSettingsNavGroup[];
};

function link(item: { href: string; label: string; icon: LucideIcon }, href = item.href): SettingsLink {
  return { href, label: item.label, icon: item.icon };
}

export function settingsLevels(input: SettingsLevelsInput): SettingsLevel[] {
  const levels: SettingsLevel[] = [];

  const platformGroups = input.platform.filter((group) => group.items.length > 0);
  if (platformGroups.length > 0) {
    levels.push({
      id: 'platform',
      label: 'Platform',
      index: PLATFORM_SETTINGS_INDEX,
      groups: platformGroups.map((group) => ({ label: group.label, links: group.items.map((item) => link(item)) })),
    });
  }

  const others = input.otherOrganizations.map((org) => ({
    href: orgSettingsIndexPath(org.id),
    label: org.name,
    icon: Building2,
  }));
  const organization = input.organization && input.organization.items.length > 0 ? input.organization : null;
  if (organization) {
    // Its own pages, then those under a heading (Access); the first group is named by the tab.
    const headings = [null, ...new Set(organization.items.flatMap((item) => (item.group ? [item.group] : [])))];
    const groups: SettingsLinkGroup[] = headings
      .map((heading) => ({
        heading,
        links: organization.items
          .filter((item) => (item.group ?? null) === heading)
          .map((item) => link({ ...item, href: orgSettingsSectionPath(organization.id, item.slug) })),
      }))
      .filter((group) => group.links.length > 0)
      .map((group, index) => ({ label: index === 0 ? null : group.heading, links: group.links }));
    if (others.length > 0) groups.push({ label: 'Other organizations', links: others });
    levels.push({
      id: 'organization',
      label: others.length > 0 || !organization.current ? `Organization · ${organization.name}` : 'Organization',
      index: orgSettingsIndexPath(organization.id),
      groups,
    });
  } else if (others.length > 0) {
    levels.push({ id: 'organization', label: 'Organizations', index: others[0].href, groups: [{ label: null, links: others }] });
  }

  const { workspace } = input;
  const workspaceGroups = (workspace?.groups ?? []).filter((group) => group.items.length > 0);
  if (workspace && workspaceGroups.length > 0) {
    levels.push({
      id: 'workspace',
      label: 'Workspace',
      index: `/workspace/${workspace.id}/settings`,
      groups: workspaceGroups.map((group, index) => ({
        label: index === 0 ? null : group.label,
        links: group.items.map((item) => link(item, `/workspace/${workspace.id}${item.href}`)),
      })),
    });
  }

  levels.push({
    id: 'account',
    label: 'Account',
    index: '/account',
    groups: [{ label: null, links: input.account.map((item) => link(item)) }],
  });
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

/** The level the column lists: the page's, or the only one the caller opens. */
export function currentSettingsLevel(levels: SettingsLevel[], pathname: string): SettingsLevel | null {
  const id = settingsScopeFromPathname(pathname)?.kind;
  return levels.find((level) => level.id === id) ?? (levels.length === 1 ? levels[0] : null);
}

export type SettingsTab = { id: SettingsLevelId; label: string; href: string; active: boolean };

/**
 * One tab per level, none when there is only one. A tab opens its level where the caller
 * left it (`lastVisited`, while that is still one of the level's pages), else at its first
 * page; on a phone, at its list. The tab of the page's level stays on the page.
 */
export function settingsTabs(
  levels: SettingsLevel[],
  pathname: string,
  { mobile, lastVisited }: { mobile: boolean; lastVisited: (level: SettingsLevelId) => string | null }
): SettingsTab[] {
  if (levels.length < 2) return [];
  const current = currentSettingsLevel(levels, pathname);
  return levels.map((level) => {
    const active = level === current;
    let href = level.index;
    if (active) {
      href = pathname;
    } else if (!mobile) {
      const last = lastVisited(level.id);
      href = last && activeSettingsHref([level], last) ? last : (level.groups[0]?.links[0]?.href ?? level.index);
    }
    return { id: level.id, label: level.label, href, active };
  });
}
