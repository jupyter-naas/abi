import {
  AppWindow,
  BarChart3,
  Bot,
  BrainCircuit,
  Network,
  Globe,
  HardDrive,
  SlidersHorizontal,
  Cpu,
  KeyRound,
  Users,
  UsersRound,
  Workflow,
  Zap,
  Search,
  Map,
  type LucideIcon,
  Package,
} from 'lucide-react';
import { opensSection, type AccessSection } from '@/components/access/access-sections';
import type { AccessView } from '@/lib/iam-admin/types';
import type { ResourceKind, WorkspaceResources } from '@/lib/workspace-resources';

export type SettingsNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** The Nexus feature the page manages: shown only when the caller holds it here. */
  feature?: string;
  /** The module resources the page lists: shown only when the caller may use one of them. */
  kinds?: ResourceKind[];
  /** An Access page (``AccessSection``): shown to whoever IAM lets open it in the workspace
   *  (`GET /access`, `ACCESS_SECTIONS`), whatever their role. `analytics`: shown to whoever
   *  may read the workspace's analytics (`GET /api/workspaces/{id}/analytics/access`
   *  answers `can_read`). */
  needs?: AccessSection | 'analytics';
};

export type SettingsNavGroup = {
  label: string;
  items: SettingsNavItem[];
};

/**
 * The Workspace level of Settings (`settingsLevels`), and the default landing of
 * /workspace/[id]/settings. Account, Organization and Platform are the other levels, at
 * their own routes; a page belongs to one level only.
 *
 * The Features group is what the caller may use here: an entry whose feature
 * they do not hold, or whose module resources they may use none of, is hidden
 * (`visibleSettingsGroups`), and its page says so.
 */
export const SETTINGS_GROUPS: SettingsNavGroup[] = [
  {
    label: 'General',
    items: [
      { href: '/settings/general', label: 'General', icon: Globe }, // the Organization's and Platform's icon
      { href: '/settings/users', label: 'Users', icon: Users },
      { href: '/settings/analytics', label: 'Analytics', icon: BarChart3, needs: 'analytics' },
    ],
  },
  {
    label: 'Access',
    items: [
      { href: '/settings/groups', label: 'Groups', icon: UsersRound, needs: 'groups' },
      { href: '/settings/policies', label: 'Policies', icon: KeyRound, needs: 'policies' },
      // The workspace's offer ("<W> access"): which features and which modules it offers; the
      // pages under Features then show what is offered.
      { href: '/settings/features', label: 'Features', icon: SlidersHorizontal },
      { href: '/settings/modules', label: 'Modules', icon: Package },
    ],
  },
  {
    label: 'Features',
    items: [
      // Agents the workspace builds itself (a model and a prompt) need no module.
      { href: '/settings/agents', label: 'Agents', icon: Bot, feature: 'agents' },
      { href: '/settings/apps', label: 'Apps', icon: AppWindow, feature: 'apps', kinds: ['apps'] },
      // Every kind of files: shown even when Workspace Files is off, which is turned on here.
      { href: '/settings/files', label: 'Files', icon: HardDrive },
      { href: '/settings/graphs', label: 'Graphs', icon: Network, feature: 'graph' },
      { href: '/settings/maps', label: 'Maps', icon: Map, feature: 'maps' },
      { href: '/settings/models', label: 'Models', icon: Cpu },
      { href: '/settings/ontologies', label: 'Ontologies', icon: BrainCircuit, feature: 'ontology' },
      { href: '/settings/search', label: 'Search', icon: Search, feature: 'search' },
      { href: '/settings/skills', label: 'Skills', icon: Zap, feature: 'skills' },
      {
        href: '/settings/workflows',
        label: 'Workflows',
        icon: Workflow,
        kinds: ['workflows', 'pipelines'],
      },
    ],
  },
];

/** The organization a workspace's IAM scope names: its own, or null for a personal workspace
 *  (in no organization: `abi:nexus:workspace/<ws>`). */
export function workspaceOrganization(workspace: { organizationId?: string } | null | undefined): string | null {
  return workspace?.organizationId || null;
}

/** First settings item, used as the default landing for /settings. */
export const DEFAULT_SETTINGS_PATH = SETTINGS_GROUPS[0].items[0].href;

/** Policies, the page whoever holds only `iam:` rights in a workspace opens first. */
export const POLICIES_SETTINGS_PATH = '/settings/policies';

/** A person's page under Users (`/settings/users/<IAM id>`). */
const PERSON_PAGE = /\/settings\/users\/[^/?#]+/;

/**
 * Whether the workspace has what an entry manages. With the workspace's resources
 * unknown (still loading, or the caller may not read them), the caller's own
 * feature flags decide the feature, and module resources are assumed; so are those
 * of a kind whose source did not answer (`unavailable`).
 */
export function settingsItemShown(
  item: SettingsNavItem,
  resources: WorkspaceResources | null,
  flags?: Partial<Record<string, boolean>>
): boolean {
  if (resources) {
    if (item.feature && !resources.features.includes(item.feature)) return false;
    if (item.kinds) {
      // A kind whose source did not answer may have items: never hidden for it.
      const unknown = item.kinds.some((kind) => resources.unavailable?.includes(kind));
      if (!unknown && !item.kinds.some((kind) => (resources.totals[kind] ?? 0) > 0)) return false;
    }
    return true;
  }
  if (item.feature && flags && flags[item.feature] === false) return false;
  return true;
}

/** Whether the caller may open an entry: what it `needs` (an entry that needs nothing: yes).
 *  ``roleOpens``: the role already brings these pages, so Analytics and Access stay listed
 *  until their own read has answered (``accessKnown`` / ``analyticsKnown``). */
export function settingsItemNeedsMet(
  item: SettingsNavItem,
  {
    access = null,
    readsAnalytics = false,
    roleOpens = false,
    accessKnown = true,
    analyticsKnown = true,
  }: {
    access?: AccessView | null;
    readsAnalytics?: boolean;
    roleOpens?: boolean;
    accessKnown?: boolean;
    analyticsKnown?: boolean;
  } = {}
): boolean {
  if (!item.needs) return true;
  if (item.needs === 'analytics') return readsAnalytics || (roleOpens && !analyticsKnown);
  return opensSection(access, item.needs) || (roleOpens && !accessKnown);
}

/**
 * The groups with only the entries the workspace has, and the ones the caller may open: a page
 * of Access only for whoever IAM lets open it there (``access``, `GET /access`), Analytics only
 * for whoever may read the workspace's analytics (``readsAnalytics``). An empty group is left out.
 */
export function visibleSettingsGroups(
  resources: WorkspaceResources | null,
  flags?: Partial<Record<string, boolean>>,
  groups: SettingsNavGroup[] = SETTINGS_GROUPS,
  held: {
    access?: AccessView | null;
    readsAnalytics?: boolean;
    roleOpens?: boolean;
    accessKnown?: boolean;
    analyticsKnown?: boolean;
  } = {}
): SettingsNavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => settingsItemNeedsMet(item, held) && settingsItemShown(item, resources, flags)
      ),
    }))
    .filter((group) => group.items.length > 0);
}

/** The pages of Access the caller opens in the workspace, in order. */
export function accessSettingsItems(access: AccessView | null, groups: SettingsNavGroup[] = SETTINGS_GROUPS): SettingsNavItem[] {
  return groups
    .flatMap((group) => group.items)
    .filter((item) => !!item.needs && item.needs !== 'analytics' && opensSection(access, item.needs));
}

/**
 * Whether a workspace's settings open for the caller, the rule the dock, the mobile sheet and
 * the settings pages share: `all` when their role there brings the settings
 * (`settings.workspace`, its owners and admins), `iam` when it does not but IAM shows them a
 * page of Access there (those pages alone, and a member's page from them), `none` otherwise
 * (no page: they say so), `unknown` until the access is read.
 */
export type WorkspaceSettingsAccess = 'all' | 'iam' | 'none' | 'unknown';

export function workspaceSettingsAccess({
  settingsByRole,
  holdsIam,
  accessSettled,
}: {
  settingsByRole: boolean;
  holdsIam: boolean;
  accessSettled: boolean;
}): WorkspaceSettingsAccess {
  if (settingsByRole) return 'all';
  if (!accessSettled) return 'unknown';
  return holdsIam ? 'iam' : 'none';
}

/** Whether the settings page at `path` opens under `access`: null while unknown. For an `iam`
 *  holder, the pages of Access IAM lets them open (``iam``, its answer there) and a member's
 *  page, which shows what that person holds. */
export function settingsPageOpens(
  access: WorkspaceSettingsAccess,
  path: string,
  groups: SettingsNavGroup[] = SETTINGS_GROUPS,
  iam: AccessView | null = null
): boolean | null {
  if (access === 'unknown') return null;
  if (access === 'all') return true;
  if (access === 'none') return false;
  if (PERSON_PAGE.test(path)) return true;
  // An Access page opens to an iam: holder; Analytics is a settings page of the role's.
  const needs = settingsItemFor(path, groups)?.needs;
  return !!needs && needs !== 'analytics' && opensSection(iam, needs);
}

/** Where the settings land for `access`: General, or for an `iam:` holder the first page of
 *  Access they hold (Policies while that is not known). */
export function settingsLandingPath(access: WorkspaceSettingsAccess, iam: AccessView | null = null): string {
  if (access !== 'iam') return DEFAULT_SETTINGS_PATH;
  return accessSettingsItems(iam)[0]?.href ?? POLICIES_SETTINGS_PATH;
}

/** The entry a settings path belongs to (`/settings/apps/...` is Apps), if any. */
export function settingsItemFor(
  path: string,
  groups: SettingsNavGroup[] = SETTINGS_GROUPS
): SettingsNavItem | undefined {
  const at = path.indexOf('/settings/');
  if (at < 0) return undefined;
  const rest = path.slice(at);
  return groups
    .flatMap((group) => group.items)
    .find((item) => rest === item.href || rest.startsWith(`${item.href}/`));
}
