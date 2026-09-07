import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  Paintbrush,
  Users,
  Globe,
  FolderKanban,
  CreditCard,
  Shield,
} from 'lucide-react';

export type OrgSettingsNavItem = {
  slug: string;
  label: string;
  icon: LucideIcon;
};

export const orgSettingsNav: OrgSettingsNavItem[] = [
  { slug: 'general', label: 'General', icon: Building2 },
  { slug: 'workspaces', label: 'Workspaces', icon: FolderKanban },
  { slug: 'branding', label: 'Branding', icon: Paintbrush },
  { slug: 'users', label: 'Users', icon: Users },
  { slug: 'roles', label: 'Roles', icon: Shield },
  { slug: 'domains', label: 'Domains', icon: Globe },
  { slug: 'billing', label: 'Billing', icon: CreditCard },
];

export function orgSettingsIndexPath(orgId: string): string {
  return `/organizations/${orgId}/settings`;
}

export function orgSettingsSectionPath(orgId: string, slug: string): string {
  return `/organizations/${orgId}/settings/${slug}`;
}
