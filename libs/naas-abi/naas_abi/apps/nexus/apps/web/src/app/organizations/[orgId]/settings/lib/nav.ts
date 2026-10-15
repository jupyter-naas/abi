import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  Paintbrush,
  Users,
  Globe,
  FolderKanban,
  CreditCard,
  Shield,
  Server,
  Boxes,
} from 'lucide-react';

export type OrgSettingsNavItem = {
  slug: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  /** Kept for deep-link labels; omitted from the settings sidebar. */
  hidden?: boolean;
};

export const orgSettingsNav: OrgSettingsNavItem[] = [
  { slug: 'general', label: 'General', icon: Building2 },
  { slug: 'workspaces', label: 'Workspaces', icon: FolderKanban },
  { slug: 'branding', label: 'Branding', icon: Paintbrush, adminOnly: true, hidden: true },
  { slug: 'users', label: 'Users', icon: Users, adminOnly: true },
  { slug: 'roles', label: 'Roles', icon: Shield, adminOnly: true },
  { slug: 'domains', label: 'Domains', icon: Globe, adminOnly: true, hidden: true },
  { slug: 'servers', label: 'Servers', icon: Server, adminOnly: true, hidden: true },
  { slug: 'services', label: 'Services', icon: Boxes, adminOnly: true, hidden: true },
  { slug: 'billing', label: 'Billing', icon: CreditCard, adminOnly: true, hidden: true },
];

export function isOrgAdminRole(role: string | null | undefined): boolean {
  return role === 'owner' || role === 'admin';
}

export function orgSettingsNavForRole(
  role: string | null | undefined
): OrgSettingsNavItem[] {
  const visible = orgSettingsNav.filter((item) => !item.hidden);
  if (isOrgAdminRole(role)) return visible;
  return visible.filter((item) => !item.adminOnly);
}

export function orgSettingsIndexPath(orgId: string): string {
  return `/organizations/${orgId}/settings`;
}

export function orgSettingsSectionPath(orgId: string, slug: string): string {
  return `/organizations/${orgId}/settings/${slug}`;
}
