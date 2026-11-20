import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  Archive,
  Blocks,
  Bot,
  Boxes,
  Braces,
  Building2,
  Cable,
  ClipboardList,
  Cpu,
  FlaskConical,
  Gauge,
  GitBranch,
  Globe,
  HardDrive,
  Hash,
  History,
  IdCardLanyard,
  KeyRound,
  Layers,
  LockKeyhole,
  Mail,
  MessagesSquare,
  Network,
  PackageCheck,
  Radar,
  Radio,
  ScrollText,
  Server,
  Sheet,
  Spline,
  Table2,
  TerminalSquare,
  Users,
  UsersRound,
  Waypoints,
  Workflow,
  Zap,
} from 'lucide-react';
import { platformAccessPath } from '@/components/access/access-paths';
import { ACCESS_SECTIONS, type AccessSection } from '@/components/access/access-sections';
import {
  INFRASTRUCTURE_DIAGRAMS_PATH,
  INFRASTRUCTURE_LAYERS_PATH,
  SYSTEM_VIEWS,
  systemViewPath,
  type SystemView,
} from '../system/system-tabs';
import { PLATFORM_DRIVES_PATH } from '../drives/drives-model';
import { PLATFORM_GENERAL_PATH } from '../general/general-model';
import { PLATFORM_ORGANIZATIONS_PATH } from '../organizations/organizations-model';
import { PLATFORM_USERS_PATH } from '../users/users-model';
import { PLATFORM_TABLES_PATH } from './tables';
import { safeDecode } from './page-helpers';
import { SERVICE_PAGES, servicePagePath, servicePagesIn } from './service-pages';

/**
 * The platform's pages, outside any organization or workspace: the Platform tab of
 * Settings. Each item names what opening it takes; the shell shows the items the caller
 * holds (asked of IAM with `GET /api/iam/admin/access`) and a 403 page when there are
 * none. The API checks every call itself: this only decides what is shown.
 *
 * The groups answer one question each, in the order an administrator asks them: what the
 * platform is and who is on it (Administration), who may do what (Access: the policies,
 * where rights come from, then the groups and accounts that hold them), is it running
 * (System, with the map of the code), what happened (Activity), what is connected
 * (Resources), what is stored (Data). Each page has one home.
 */

/** What an item needs: one action, or any of several. */
export type PlatformSettingsNeed = { action: string } | { anyOf: readonly string[] };

export const READ_SYSTEM: PlatformSettingsNeed = { action: 'nexus:ReadSystem' };

export type PlatformSettingsNavItem = {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  needs: PlatformSettingsNeed;
};

export type PlatformSettingsNavGroup = {
  /** Shown above the items; every group has one. */
  label: string;
  items: PlatformSettingsNavItem[];
};

/** The caller's actions, as `GET /api/iam/admin/access` answers them. */
export type PlatformActions = Record<string, boolean>;

export const PLATFORM_SETTINGS_INDEX = '/settings';

const SYSTEM_ICONS: Record<SystemView, LucideIcon> = {
  overview: Gauge,
  services: Server,
  jobs: Workflow,
  agents: Bot,
  modules: Blocks,
  nats: Cable,
  traffic: Radio,
  traces: Waypoints,
  events: Activity,
};

/** The icon of each service's page: its view's icon (services/), one per page of the sidebar. */
export const SERVICE_ICONS: Record<string, LucideIcon> = {
  discovery: Radar,
  bus: MessagesSquare,
  event: History,
  activity_log: ScrollText,
  model_registry: Cpu,
  secret: LockKeyhole,
  email: Mail,
  source_control: GitBranch,
  coding_environment: TerminalSquare,
  triple_store: Network,
  vector_store: Boxes,
  document: Braces,
  dataset: Sheet,
  object_storage: HardDrive,
  keyvalue: Hash,
  cache: Zap,
};

function systemItem(id: SystemView): PlatformSettingsNavItem {
  const view = SYSTEM_VIEWS.find((v) => v.id === id) ?? SYSTEM_VIEWS[0];
  return {
    id: `system-${view.id}`,
    label: view.label,
    href: systemViewPath(view.id),
    icon: SYSTEM_ICONS[view.id],
    needs: READ_SYSTEM,
  };
}

function serviceItem(service: string): PlatformSettingsNavItem {
  const page = SERVICE_PAGES.find((p) => p.service === service);
  return {
    id: `service-${service}`,
    label: page?.label ?? service,
    href: servicePagePath(service),
    icon: SERVICE_ICONS[service],
    needs: READ_SYSTEM,
  };
}

export const NEXUS_TABLES_ITEM: PlatformSettingsNavItem = {
  id: 'tables',
  label: 'Nexus tables',
  href: PLATFORM_TABLES_PATH,
  icon: Table2,
  needs: READ_SYSTEM,
};

/** The site's identity, which every organization on the platform shares. */
export const GENERAL_ITEM: PlatformSettingsNavItem = {
  id: 'general',
  label: 'General',
  href: PLATFORM_GENERAL_PATH,
  icon: Globe,
  needs: READ_SYSTEM,
};

export const ORGANIZATIONS_ITEM: PlatformSettingsNavItem = {
  id: 'organizations',
  label: 'Organizations',
  href: PLATFORM_ORGANIZATIONS_PATH,
  icon: Building2,
  needs: READ_SYSTEM,
};

/** The accounts, and each person's page: what they hold, at every level. Whoever may list
 *  who holds what (`iam:ListAttachments`) opens it too: the people who hold something. */
export const USERS_ITEM: PlatformSettingsNavItem = {
  id: 'users',
  label: 'Users',
  href: PLATFORM_USERS_PATH,
  icon: Users,
  needs: { anyOf: ['nexus:ListUsers', 'iam:ListAttachments'] },
};

/** The storage backends: where the platform stores files (read-only). */
export const DRIVES_ITEM: PlatformSettingsNavItem = {
  id: 'drives',
  label: 'Drives',
  href: PLATFORM_DRIVES_PATH,
  icon: Archive,
  needs: { action: 'nexus:ListDrives' },
};

const ACCESS_ICONS: Record<AccessSection, LucideIcon> = {
  policies: KeyRound,
  groups: UsersRound,
  'service-accounts': IdCardLanyard,
  approvals: PackageCheck,
  simulator: FlaskConical,
  audit: ClipboardList,
};

/** Each page of Access, opened by the action that lists what it shows (`ACCESS_SECTIONS`). */
export const ACCESS_ITEMS: PlatformSettingsNavItem[] = ACCESS_SECTIONS.map((section) => ({
  id: `access-${section.id}`,
  label: section.label,
  href: platformAccessPath(section.id),
  icon: ACCESS_ICONS[section.id],
  needs: { anyOf: section.needs },
}));

/** The ABI code as layered planes, then as a diagram: the same snapshot, two views. */
export const LAYERS_ITEM: PlatformSettingsNavItem = {
  id: 'system-layers',
  label: 'Layers',
  href: INFRASTRUCTURE_LAYERS_PATH,
  icon: Layers,
  needs: READ_SYSTEM,
};

export const DIAGRAMS_ITEM: PlatformSettingsNavItem = {
  id: 'system-diagrams',
  label: 'Diagrams',
  href: INFRASTRUCTURE_DIAGRAMS_PATH,
  icon: Spline,
  needs: READ_SYSTEM,
};

// Discovery sits by Modules, Bus by NATS and the Event store by Events: each shows the
// same things as its neighbour, until the two pages are one.
/** Pages that keep the shell's padding (Administration: General, Organizations, Users,
 * Drives; and Access). The other pages (System, Activity, Resources, Data)
 * lay out their own panes with their own padding; Nexus tables have their own layout.
 * No page is width-capped anymore: the centered column is retired everywhere. */
const PADDED_ITEM_IDS: ReadonlySet<string> = new Set([
  GENERAL_ITEM.id,
  ORGANIZATIONS_ITEM.id,
  USERS_ITEM.id,
  DRIVES_ITEM.id,
  ...ACCESS_ITEMS.map((item) => item.id),
]);

/** Whether a page lays out its own panes (its own padding, no shell padding). */
export function laysOutOwnPanes(item: Pick<PlatformSettingsNavItem, 'id'>): boolean {
  return item.id !== NEXUS_TABLES_ITEM.id && !PADDED_ITEM_IDS.has(item.id);
}

export const platformSettingsGroups: PlatformSettingsNavGroup[] = [
  {
    label: 'Administration',
    items: [GENERAL_ITEM, ORGANIZATIONS_ITEM, USERS_ITEM, DRIVES_ITEM],
  },
  { label: 'Access', items: ACCESS_ITEMS },
  {
    label: 'System',
    items: [
      systemItem('overview'),
      systemItem('services'),
      systemItem('modules'),
      serviceItem('discovery'),
      systemItem('agents'),
      systemItem('jobs'),
      systemItem('nats'),
      serviceItem('bus'),
      LAYERS_ITEM,
      DIAGRAMS_ITEM,
    ],
  },
  {
    label: 'Activity',
    items: [
      systemItem('traffic'),
      systemItem('traces'),
      systemItem('events'),
      serviceItem('event'),
      serviceItem('activity_log'),
    ],
  },
  { label: 'Resources', items: servicePagesIn('resources').map((page) => serviceItem(page.service)) },
  {
    label: 'Data',
    items: [NEXUS_TABLES_ITEM, ...servicePagesIn('data').map((page) => serviceItem(page.service))],
  },
];

export const platformSettingsNav: PlatformSettingsNavItem[] = platformSettingsGroups.flatMap(
  (group) => group.items
);

export function holds(needs: PlatformSettingsNeed, actions: PlatformActions | null): boolean {
  if (!actions) return false;
  if ('action' in needs) return actions[needs.action] === true;
  return needs.anyOf.some((action) => actions[action] === true);
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
