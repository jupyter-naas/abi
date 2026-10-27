import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  Paintbrush,
  Users,
  Globe,
  FolderKanban,
  CreditCard,
  Shield,
  KeyRound,
  Server,
  Boxes,
  Blocks,
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
  { slug: 'branding', label: 'Branding', icon: Paintbrush, adminOnly: true },
  { slug: 'workspaces', label: 'Workspaces', icon: FolderKanban },
  // Not admin-only: IAM decides who reads the sets, and the page says when the caller may not.
  { slug: 'modules', label: 'Modules & features', icon: Blocks },
  { slug: 'users', label: 'Users', icon: Users, adminOnly: true },
  { slug: 'roles', label: 'Roles', icon: Shield, adminOnly: true },
  { slug: 'access', label: 'Access', icon: KeyRound, adminOnly: true },
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

/** The organization's Modules & features page, scrolled to one workspace's column when given. */
export function orgModulesPath(orgId: string, workspaceId?: string | null): string {
  const path = orgSettingsSectionPath(orgId, 'modules');
  return workspaceId ? `${path}?workspace=${encodeURIComponent(workspaceId)}` : path;
}
