import type { LucideIcon } from 'lucide-react';
import { User, Palette, Key, Shield, Bell } from 'lucide-react';

export type AccountSettingsNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export const accountSettingsNav: AccountSettingsNavItem[] = [
  { href: '/account/profile', label: 'Profile', icon: User },
  { href: '/account/appearance', label: 'Appearance', icon: Palette },
  { href: '/account/api-keys', label: 'API Keys', icon: Key },
  { href: '/account/security', label: 'Security', icon: Shield },
  { href: '/account/notifications', label: 'Notifications', icon: Bell },
];
