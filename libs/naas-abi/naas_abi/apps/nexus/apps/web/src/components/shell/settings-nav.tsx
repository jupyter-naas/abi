import {
  AppWindow,
  Bot,
  BrainCircuit,
  Network,
  SlidersHorizontal,
  Cpu,
  Download,
  HardDrive,
  KeyRound,
  Shield,
  Users,
  Workflow,
  Zap,
  Search,
  Map,
  type LucideIcon,
} from 'lucide-react';
import type { ResourceKind, WorkspaceResources } from '@/lib/workspace-resources';

export type SettingsNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** The Nexus feature the page manages: shown only when the workspace's set has it. */
  feature?: string;
  /** The module resources the page lists: shown only when the set has one of them. */
  kinds?: ResourceKind[];
  /** `iam`: shown to whoever holds an `iam:` action in the workspace (IAM says, `GET /access`). */
  needs?: 'iam';
};

export type SettingsNavGroup = {
  label: string;
  items: SettingsNavItem[];
};

/**
 * Workspace settings categories, shown both in the Settings sub-panel and
 * driving the default redirect for /workspace/[id]/settings.
 *
 * Account and Organization live in standalone routes (linked from the
 * top-right user menu), and are not duplicated here.
 *
 * The Features group is what the workspace has: an entry whose feature or
 * module resources are outside the workspace's set is hidden
 * (`visibleSettingsGroups`), and its page says so.
 */
export const SETTINGS_GROUPS: SettingsNavGroup[] = [
  {
    label: 'General',
    items: [
      { href: '/settings/general', label: 'General', icon: SlidersHorizontal },
      { href: '/settings/members', label: 'Members', icon: Users },
      { href: '/settings/permissions', label: 'Roles & permissions', icon: KeyRound, needs: 'iam' },
      { href: '/settings/secrets', label: 'Secrets', icon: Shield },
      { href: '/settings/export', label: 'Data Export', icon: Download },
    ],
  },
  {
    label: 'Features',
    items: [
      // Agents the workspace builds itself (a model and a prompt) need no module.
      { href: '/settings/agents', label: 'Agents', icon: Bot, feature: 'agents' },
      { href: '/settings/apps', label: 'Apps', icon: AppWindow, feature: 'apps', kinds: ['apps'] },
      { href: '/settings/drives', label: 'Drives', icon: HardDrive, feature: 'files' },
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

/** The organization a workspace's IAM scope names: its own, or `_none`, the reserved org of a
 *  personal workspace. */
export function workspaceOrganization(workspace: { organizationId?: string } | null | undefined): string {
  return workspace?.organizationId || '_none';
}

/** First settings item, used as the default landing for /settings. */
export const DEFAULT_SETTINGS_PATH = SETTINGS_GROUPS[0].items[0].href;

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

/**
 * The groups with only the entries the workspace has, and the ones the caller may open: an
 * entry that needs `iam` only for whoever holds an `iam:` action there (`holdsIam`). An empty
 * group is left out.
 */
export function visibleSettingsGroups(
  resources: WorkspaceResources | null,
  flags?: Partial<Record<string, boolean>>,
  groups: SettingsNavGroup[] = SETTINGS_GROUPS,
  { holdsIam = false }: { holdsIam?: boolean } = {}
): SettingsNavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => (item.needs !== 'iam' || holdsIam) && settingsItemShown(item, resources, flags)
      ),
    }))
    .filter((group) => group.items.length > 0);
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
