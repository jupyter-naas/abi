import {
  AccountingSettingsIcon,
  AppearanceIcon,
  AuditLogsIcon,
  IntegrationsIcon,
  PerimetersIcon,
  UsersIcon,
  WorkflowsIcon,
} from '@/components/layout/SidebarGroupIcons';

/**
 * The Administration tree. Unlike the finance pages — declared in config.yaml
 * and rendered by the `[pageId]` route — administration screens are
 * configuration-oriented, live at absolute `/admin/*` routes, and are visible
 * to admins only. This module is their single source of truth: the secondary
 * sidebar panel, the page titles and the analytics keys all read it.
 */
export type AdminSection =
  // Organizations
  | 'entities'
  | 'business-units'
  | 'cost-centers'
  // Users & Roles
  | 'users'
  | 'roles'
  | 'permissions'
  // Accounting Settings
  | 'chart-of-accounts'
  | 'fiscal-years'
  | 'accounting-periods'
  | 'journals'
  // Workflows
  | 'approval-flows'
  | 'notifications'
  | 'validation-rules'
  // Integrations
  | 'integrations-erp'
  | 'integrations-banking'
  | 'integrations-api'
  | 'imports-exports'
  // Audit Logs
  | 'user-activity'
  | 'system-logs'
  | 'sync-history'
  // Appearance
  | 'theme';

type IconComponent = React.ComponentType<{ className?: string }>;

export type AdminNavItem = {
  id: AdminSection;
  href: string;
  label: string;
};

export type AdminNavGroup = {
  id: string;
  label: string;
  icon: IconComponent;
  items: readonly AdminNavItem[];
};

export const ADMIN_NAV_GROUPS: readonly AdminNavGroup[] = [
  {
    id: 'organizations',
    label: 'Organizations',
    icon: PerimetersIcon,
    items: [
      { id: 'entities', href: '/admin', label: 'Entities' },
      { id: 'business-units', href: '/admin/business-units', label: 'Business Units' },
      { id: 'cost-centers', href: '/admin/cost-centers', label: 'Cost Centers' },
    ],
  },
  {
    id: 'users-roles',
    label: 'Users & Roles',
    icon: UsersIcon,
    items: [
      { id: 'users', href: '/admin/users', label: 'Users' },
      { id: 'roles', href: '/admin/roles', label: 'Roles' },
      { id: 'permissions', href: '/admin/permissions', label: 'Permissions' },
    ],
  },
  {
    id: 'accounting-settings',
    label: 'Accounting Settings',
    icon: AccountingSettingsIcon,
    items: [
      { id: 'chart-of-accounts', href: '/admin/chart-of-accounts', label: 'Chart of Accounts' },
      { id: 'fiscal-years', href: '/admin/fiscal-years', label: 'Fiscal Years' },
      { id: 'accounting-periods', href: '/admin/accounting-periods', label: 'Accounting Periods' },
      { id: 'journals', href: '/admin/journals', label: 'Journals' },
    ],
  },
  {
    id: 'workflows',
    label: 'Workflows',
    icon: WorkflowsIcon,
    items: [
      { id: 'approval-flows', href: '/admin/approval-flows', label: 'Approval Flows' },
      { id: 'notifications', href: '/admin/notifications', label: 'Notifications' },
      { id: 'validation-rules', href: '/admin/validation-rules', label: 'Validation Rules' },
    ],
  },
  {
    id: 'integrations',
    label: 'Integrations',
    icon: IntegrationsIcon,
    items: [
      { id: 'integrations-erp', href: '/admin/integrations/erp', label: 'ERP' },
      { id: 'integrations-banking', href: '/admin/integrations/banking', label: 'Banking' },
      { id: 'integrations-api', href: '/admin/integrations/api', label: 'API' },
      { id: 'imports-exports', href: '/admin/integrations/imports-exports', label: 'Imports / Exports' },
    ],
  },
  {
    id: 'audit-logs',
    label: 'Audit Logs',
    icon: AuditLogsIcon,
    items: [
      { id: 'user-activity', href: '/admin/analytics', label: 'User Activity' },
      { id: 'system-logs', href: '/admin/system-logs', label: 'System Logs' },
      { id: 'sync-history', href: '/admin/sync-history', label: 'Synchronization History' },
    ],
  },
  {
    id: 'appearance',
    label: 'Appearance',
    icon: AppearanceIcon,
    items: [{ id: 'theme', href: '/admin/theme', label: 'Theme' }],
  },
];

/** Flat view of the tree, in sidebar order. */
export const ADMIN_NAV: readonly AdminNavItem[] = ADMIN_NAV_GROUPS.flatMap(
  (group) => group.items,
);

/**
 * The admin screen a pathname belongs to. Longest matching href wins, so
 * `/admin/users` beats the `/admin` catch-all and nested integration routes
 * resolve to their own entry.
 */
export function adminSectionFor(pathname: string): AdminSection | null {
  let match: AdminNavItem | null = null;
  for (const item of ADMIN_NAV) {
    const isMatch = pathname === item.href || pathname.startsWith(`${item.href}/`);
    if (isMatch && (match === null || item.href.length > match.href.length)) {
      match = item;
    }
  }
  return match?.id ?? null;
}

/** The group owning a screen — used to auto-expand it in the sidebar panel. */
export function adminGroupFor(section: AdminSection | null): string | null {
  if (!section) return null;
  return (
    ADMIN_NAV_GROUPS.find((group) =>
      group.items.some((item) => item.id === section),
    )?.id ?? null
  );
}
