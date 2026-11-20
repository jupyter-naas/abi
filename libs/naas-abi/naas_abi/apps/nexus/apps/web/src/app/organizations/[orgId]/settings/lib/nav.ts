import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  Paintbrush,
  Users,
  UsersRound,
  Globe,
  FolderKanban,
  CreditCard,
  KeyRound,
  Server,
  Boxes,
} from 'lucide-react';
import { opensSection, type AccessSection } from '@/components/access/access-sections';
import type { AccessView } from '@/lib/iam-admin/types';

export type OrgSettingsNavItem = {
  slug: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  /** An Access page (``AccessSection``): shown to whoever IAM lets open it at the
   *  organization (`ACCESS_SECTIONS`), whatever their role. `analytics`: shown to whoever may
   *  read the organization's analytics (`GET /api/organizations/{id}/analytics/access`
   *  answers `can_read`). */
  needs?: AccessSection | 'analytics';
  /** The heading it sits under, after the organization's own pages. */
  group?: 'Access';
  /** Kept for deep-link labels; omitted from the settings sidebar. */
  hidden?: boolean;
};

export const orgSettingsNav: OrgSettingsNavItem[] = [
  { slug: 'general', label: 'General', icon: Globe }, // Platform › General's icon
  { slug: 'branding', label: 'Branding', icon: Paintbrush, adminOnly: true },
  { slug: 'workspaces', label: 'Workspaces', icon: FolderKanban },
  { slug: 'users', label: 'Members', icon: Users, adminOnly: true },
  // IAM decides (the access of the organization's scope), not the membership role.
  // The API decides (`ReadOrganizationAnalytics`, its owners and admins by default).
  { slug: 'analytics', label: 'Analytics', icon: BarChart3, needs: 'analytics' },
  { slug: 'policies', label: 'Policies', icon: KeyRound, needs: 'policies', group: 'Access' },
  { slug: 'groups', label: 'Groups', icon: UsersRound, needs: 'groups', group: 'Access' },
  { slug: 'domains', label: 'Domains', icon: Globe, adminOnly: true, hidden: true },
  { slug: 'servers', label: 'Servers', icon: Server, adminOnly: true, hidden: true },
  { slug: 'services', label: 'Services', icon: Boxes, adminOnly: true, hidden: true },
  { slug: 'billing', label: 'Billing', icon: CreditCard, adminOnly: true, hidden: true },
];

export function isOrgAdminRole(role: string | null | undefined): boolean {
  return role === 'owner' || role === 'admin';
}

/**
 * Whether Organization settings opens for the caller here, as the Settings tabs decide
 * it (`hooks/use-organization-settings-access.ts`, `opensOrganization`): `admin` for its
 * owners and admins (every section), `iam` for someone else IAM shows a page of Access (those
 * pages alone, and a member's page from them), `none` for anyone else (no section: the pages
 * say so), `unknown` until the role (and, for a non-admin, the access) is read.
 */
export type OrgSettingsAccess = 'admin' | 'iam' | 'none' | 'unknown';

export function orgSettingsAccess({
  role,
  roleKnown,
  holdsIam,
  accessSettled,
}: {
  role: string | null | undefined;
  roleKnown: boolean;
  holdsIam: boolean;
  accessSettled: boolean;
}): OrgSettingsAccess {
  if (isOrgAdminRole(role)) return 'admin';
  if (!roleKnown || !accessSettled) return 'unknown';
  return holdsIam ? 'iam' : 'none';
}

/** The sections the caller sees, from their role there and IAM's access at its container:
 *  the Access pages for whoever IAM lets open each, the rest for its owners and admins. */
export function orgSettingsNavForRole(
  role: string | null | undefined,
  { access = null, readsAnalytics = false }: { access?: AccessView | null; readsAnalytics?: boolean } = {}
): OrgSettingsNavItem[] {
  const admin = isOrgAdminRole(role);
  return orgSettingsNav.filter((item) => {
    if (item.hidden) return false;
    // Shown to an owner or admin only once the API said yes: a role IAM stripped of it sees no entry.
    if (item.needs === 'analytics') return admin && readsAnalytics;
    return item.needs ? opensSection(access, item.needs) : admin;
  });
}

/**
 * Where a section someone may not open sends them, or null to stay: an organization's
 * owners and admins stay anywhere; someone who holds only `iam:` rights there goes to the
 * first page of Access they hold, with a role below admin or with none (a platform admin who
 * is no member), and stays on those pages and on a member's page (``memberPage``, which shows
 * them what that person holds); anyone else stays, and the layout shows that they have no
 * access. Nothing is decided before the role is known (``roleKnown``: read, or refused, which
 * is no role) and, for a non-admin, before the access was read (``accessSettled``): a member
 * who holds `iam:` rights through a group is not bounced off Access while that read is in flight.
 */
export function orgSectionRedirect({
  section,
  memberPage = false,
  role,
  roleKnown,
  access,
  accessSettled,
}: {
  section: string | null;
  memberPage?: boolean;
  role: string | null;
  roleKnown: boolean;
  access: AccessView | null;
  accessSettled: boolean;
}): string | null {
  if (!section || !roleKnown || isOrgAdminRole(role) || !accessSettled) return null;
  const held = orgSettingsNavForRole(role, { access }).map((item) => item.slug);
  if (held.length === 0 || held.includes(section) || (section === 'users' && memberPage)) return null;
  return held[0];
}

export function orgSettingsIndexPath(orgId: string): string {
  return `/organizations/${orgId}/settings`;
}

export function orgSettingsSectionPath(orgId: string, slug: string): string {
  return `/organizations/${orgId}/settings/${slug}`;
}
