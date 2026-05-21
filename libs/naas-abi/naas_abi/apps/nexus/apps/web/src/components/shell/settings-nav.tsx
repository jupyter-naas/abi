import {
  AppWindow,
  Bot,
  BrainCircuit,
  Brush,
  Cpu,
  Download,
  HardDrive,
  Network,
  Server,
  Shield,
  Users,
  type LucideIcon,
} from 'lucide-react';

export type SettingsNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export type SettingsNavGroup = {
  label: string;
  items: SettingsNavItem[];
};

/**
 * Workspace settings categories — shown both in the Settings sub-panel and
 * driving the default redirect for /workspace/[id]/settings.
 *
 * Account and Organization live in standalone routes (linked from the
 * top-right user menu), and are not duplicated here.
 *
 * Visibility of this entire section is gated by the `settings.workspace`
 * feature flag (applied at the sidebar icon and the route guard).
 */
export const SETTINGS_GROUPS: SettingsNavGroup[] = [
  {
    label: 'General',
    items: [
      { href: '/settings/theme', label: 'Theme', icon: Brush },
      { href: '/settings/members', label: 'Members', icon: Users },
      { href: '/settings/servers', label: 'Servers', icon: Server },
      { href: '/settings/drives', label: 'Drives', icon: HardDrive },
      { href: '/settings/secrets', label: 'Secrets', icon: Shield },
      { href: '/settings/export', label: 'Data Export', icon: Download },
    ],
  },
  {
    label: 'Components',
    items: [
      { href: '/settings/agents', label: 'Agents', icon: Bot },
      { href: '/settings/apps', label: 'Apps', icon: AppWindow },
      { href: '/settings/ontologies', label: 'Ontologies', icon: BrainCircuit },
      { href: '/settings/graphs', label: 'Graphs', icon: Network },
      { href: '/settings/models', label: 'Models', icon: Cpu },
    ],
  },
];

/** First settings item — used as the default landing for /settings. */
export const DEFAULT_SETTINGS_PATH = SETTINGS_GROUPS[0].items[0].href;
