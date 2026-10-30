import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  Paintbrush,
  Users,
  Globe,
  FolderKanban,
  CreditCard,
  KeyRound,
  Server,
  Boxes,
} from 'lucide-react';

export type OrgSettingsNavItem = {
  slug: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  /** `iam`: shown to whoever holds an `iam:` action at the organization, whatever their role. */
  needs?: 'iam';
  /** Kept for deep-link labels; omitted from the settings sidebar. */
  hidden?: boolean;
};

export const orgSettingsNav: OrgSettingsNavItem[] = [
  { slug: 'general', label: 'General', icon: Building2 },
  { slug: 'branding', label: 'Branding', icon: Paintbrush, adminOnly: true },
  { slug: 'workspaces', label: 'Workspaces', icon: FolderKanban },
  { slug: 'users', label: 'Users', icon: Users, adminOnly: true },
  // IAM decides (the access of the organization's scope), not the membership role.
  { slug: 'roles', label: 'Roles & permissions', icon: KeyRound, needs: 'iam' },
  { slug: 'domains', label: 'Domains', icon: Globe, adminOnly: true, hidden: true },
  { slug: 'servers', label: 'Servers', icon: Server, adminOnly: true, hidden: true },
  { slug: 'services', label: 'Services', icon: Boxes, adminOnly: true, hidden: true },
  { slug: 'billing', label: 'Billing', icon: CreditCard, adminOnly: true, hidden: true },
];

export function isOrgAdminRole(role: string | null | undefined): boolean {
  return role === 'owner' || role === 'admin';
}

export function orgSettingsNavForRole(
  role: string | null | undefined,
  { holdsIam = false }: { holdsIam?: boolean } = {}
): OrgSettingsNavItem[] {
  return orgSettingsNav.filter(
    (item) =>
      !item.hidden &&
      (item.needs === 'iam' ? holdsIam : !item.adminOnly || isOrgAdminRole(role))
  );
}

/**
 * Where a section someone may not open sends them: General, or null to stay. Nothing is
 * decided before the role is known and, for the IAM item, before the caller's access was read
 * (``accessSettled``): an org member who holds `iam:` rights through a group is not bounced
 * off Roles & permissions while that read is in flight.
 */
export function orgSectionRedirect({
  section,
  role,
  holdsIam,
  accessSettled,
}: {
  section: string | null;
  role: string | null;
  holdsIam: boolean;
  accessSettled: boolean;
}): string | null {
  if (!section || role === null || isOrgAdminRole(role)) return null;
  const item = orgSettingsNav.find((entry) => entry.slug === section);
  if (item?.needs === 'iam' && !accessSettled) return null;
  return orgSettingsNavForRole(role, { holdsIam }).some((entry) => entry.slug === section)
    ? null
    : 'general';
}

export function orgSettingsIndexPath(orgId: string): string {
  return `/organizations/${orgId}/settings`;
}

export function orgSettingsSectionPath(orgId: string, slug: string): string {
  return `/organizations/${orgId}/settings/${slug}`;
}
