import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  Blocks,
  Bot,
  Database,
  Gauge,
  KeyRound,
  Network,
  Radio,
  Server,
  Table2,
  Waypoints,
  Workflow,
} from 'lucide-react';
import {
  ROLES_PATH,
  SYSTEM_VIEWS,
  systemViewPath,
  type SystemView,
} from '../system/system-tabs';
import { PLATFORM_TABLES_PATH } from './tables';

/**
 * Platform Settings, outside any organization or workspace. Each item names what
 * opening it takes; the shell shows the items the caller holds (asked of IAM with
 * `GET /api/iam/admin/access`) and a 403 page when there are none. The API checks
 * every call itself: this only decides what is shown.
 */

/** What an item needs: one action, or any platform-level `iam:` action. */
export type PlatformSettingsNeed = { action: string } | { anyOf: 'iam' };

export const READ_SYSTEM: PlatformSettingsNeed = { action: 'nexus:ReadSystem' };
export const ANY_IAM_ACTION: PlatformSettingsNeed = { anyOf: 'iam' };

export type PlatformSettingsNavItem = {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  needs: PlatformSettingsNeed;
};

export type PlatformSettingsNavGroup = {
  /** Shown above the items; the first group has no heading. */
  label: string | null;
  items: PlatformSettingsNavItem[];
};

/** The caller's actions, as `GET /api/iam/admin/access` answers them. */
export type PlatformActions = Record<string, boolean>;

export const PLATFORM_SETTINGS_INDEX = '/settings';

const SYSTEM_ICONS: Record<SystemView, LucideIcon> = {
  overview: Gauge,
  services: Server,
  data: Database,
  jobs: Workflow,
  agents: Bot,
  modules: Blocks,
  nats: Network,
  traffic: Radio,
  traces: Waypoints,
  events: Activity,
};

export const NEXUS_TABLES_ITEM: PlatformSettingsNavItem = {
  id: 'tables',
  label: 'Nexus tables',
  href: PLATFORM_TABLES_PATH,
  icon: Table2,
  needs: READ_SYSTEM,
};

export const ROLES_ITEM: PlatformSettingsNavItem = {
  id: 'roles',
  label: 'Roles & permissions',
  href: ROLES_PATH,
  icon: KeyRound,
  needs: ANY_IAM_ACTION,
};

export const platformSettingsGroups: PlatformSettingsNavGroup[] = [
  { label: null, items: [NEXUS_TABLES_ITEM] },
  {
    label: 'System',
    items: SYSTEM_VIEWS.map((view) => ({
      id: `system-${view.id}`,
      label: view.label,
      href: systemViewPath(view.id),
      icon: SYSTEM_ICONS[view.id],
      needs: READ_SYSTEM,
    })),
  },
  { label: 'Access', items: [ROLES_ITEM] },
];

export const platformSettingsNav: PlatformSettingsNavItem[] = platformSettingsGroups.flatMap(
  (group) => group.items
);

export function holds(needs: PlatformSettingsNeed, actions: PlatformActions | null): boolean {
  if (!actions) return false;
  if ('action' in needs) return actions[needs.action] === true;
  return Object.entries(actions).some(([action, allowed]) => allowed && action.startsWith('iam:'));
}

/** The groups the caller may open, empty groups left out. */
export function visiblePlatformSettingsGroups(
  actions: PlatformActions | null
): PlatformSettingsNavGroup[] {
  return platformSettingsGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => holds(item.needs, actions)) }))
    .filter((group) => group.items.length > 0);
}

/** Where `/settings` lands: the first item the caller may open, or null (403). */
export function firstPlatformSettingsPath(actions: PlatformActions | null): string | null {
  return platformSettingsNav.find((item) => holds(item.needs, actions))?.href ?? null;
}

/** The item a path belongs to: the longest href it is, or is under. */
export function platformSettingsItemFor(pathname: string): PlatformSettingsNavItem | null {
  const path = pathname.replace(/[?#].*$/, '').replace(/\/+$/, '') || '/';
  let best: PlatformSettingsNavItem | null = null;
  for (const item of platformSettingsNav) {
    if (path === item.href || path.startsWith(`${item.href}/`)) {
      if (!best || item.href.length > best.href.length) best = item;
    }
  }
  return best;
}

export interface PlatformSettingsRoute {
  isPlatformSettingsRoute: boolean;
  /** An item's page is open (as opposed to the index, which lists them on a phone). */
  isDetail: boolean;
  item: PlatformSettingsNavItem | null;
  /** The table on `/settings/tables/<name>[/<row id>]`, decoded. */
  table: string | null;
  /** The row on `/settings/tables/<name>/<row id>`, decoded. */
  rowId: string | null;
}

const PLATFORM_SETTINGS_PATH = /^\/settings(?:\/([^?#]*?))?\/?(?:[?#]|$)/;

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function parsePlatformSettingsRoute(
  pathname: string | null | undefined
): PlatformSettingsRoute {
  const match = pathname ? PLATFORM_SETTINGS_PATH.exec(pathname) : null;
  if (!match) {
    return { isPlatformSettingsRoute: false, isDetail: false, item: null, table: null, rowId: null };
  }
  const segments = (match[1] || '').split('/').filter(Boolean);
  const item = platformSettingsItemFor(`/settings/${segments.join('/')}`);
  const [section, table, ...rest] = segments;
  const isTables = section === 'tables';
  const encodedRowId = isTables ? rest.join('/') : '';
  return {
    isPlatformSettingsRoute: true,
    isDetail: segments.length > 0,
    item,
    table: isTables && table ? safeDecode(table) : null,
    rowId: encodedRowId ? safeDecode(encodedRowId) : null,
  };
}
