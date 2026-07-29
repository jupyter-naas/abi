import type { LucideIcon } from 'lucide-react';
import { User, Palette, Key, Shield, Bell } from 'lucide-react';

export type AccountSettingsNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** When false, keep the route but hide the item from account nav. */
  enabled?: boolean;
};

export const accountSettingsNav: AccountSettingsNavItem[] = [
  { href: '/account/profile', label: 'Profile', icon: User },
  { href: '/account/appearance', label: 'Appearance', icon: Palette },
  // Deactivated (not implemented yet):
  { href: '/account/api-keys', label: 'API Keys', icon: Key, enabled: false },
  { href: '/account/security', label: 'Security', icon: Shield, enabled: false },
  { href: '/account/notifications', label: 'Notifications', icon: Bell, enabled: false },
];

export const accountSettingsNavVisible = accountSettingsNav.filter(
  (item) => item.enabled !== false
);
