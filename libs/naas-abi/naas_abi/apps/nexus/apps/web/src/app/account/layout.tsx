'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  User,
  Palette,
  Key,
  Shield,
  Bell,
  ArrowLeft,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import './account-layout.css';

const accountSettingsNav = [
  { href: '/account/profile', label: 'Profile', icon: User },
  { href: '/account/appearance', label: 'Appearance', icon: Palette },
  { href: '/account/api-keys', label: 'API Keys', icon: Key },
  { href: '/account/security', label: 'Security', icon: Shield },
  { href: '/account/notifications', label: 'Notifications', icon: Bell },
];

function NavItem({
  item,
  pathname,
}: {
  item: typeof accountSettingsNav[0];
  pathname: string;
}) {
  const isActive = pathname === item.href;
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
        className={
          isActive
            ? 'account-nav-item account-nav-item-active'
            : 'account-nav-item'
        }
      >
        <Icon size={18} />
        {item.label}
      </Link>
    </li>
  );
}

export default function AccountLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const user = useAuthStore((state) => state.user);
  const [orgBorderRadius, setOrgBorderRadius] = useState('0');

  useEffect(() => {
    const fetchOrgBranding = async () => {
      if (!currentWorkspaceId) {
        setOrgBorderRadius('0');
        return;
      }

      try {
        const { authFetch } = await import('@/stores/auth');
        const wsResponse = await authFetch(`/api/workspaces/${currentWorkspaceId}`);
        if (!wsResponse.ok) return;

        const wsData = await wsResponse.json();
        if (!wsData.organization_id) return;

        const orgResponse = await authFetch(`/api/organizations/${wsData.organization_id}`);
        if (!orgResponse.ok) return;

        const orgData = await orgResponse.json();
        const radius = orgData.loginBorderRadius ?? orgData.login_border_radius ?? '0';
        setOrgBorderRadius(radius);
      } catch (error) {
        console.error('Failed to fetch org branding for account layout:', error);
      }
    };

    fetchOrgBranding();

    const handleBrandingUpdate = () => {
      fetchOrgBranding();
    };

    window.addEventListener('org-branding-updated', handleBrandingUpdate);
    return () => window.removeEventListener('org-branding-updated', handleBrandingUpdate);
  }, [currentWorkspaceId]);

  const themeStyles = {
    '--org-border-radius': `${orgBorderRadius}px`,
  } as React.CSSProperties;

  const handleBack = () => {
    if (currentWorkspaceId) {
      router.push(`/workspace/${currentWorkspaceId}/chat`);
    } else {
      router.push('/');
    }
  };

  return (
    <div
      className="flex h-screen flex-col bg-background"
      data-org-branded="true"
      style={themeStyles}
    >
      <header className="flex h-14 items-center border-b bg-card/50 px-4">
        <button
          type="button"
          onClick={handleBack}
          className="account-back-button"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-sm font-semibold">{user?.name || 'Account'}</h1>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <nav className="w-56 flex-shrink-0 border-r bg-card/50 p-4 overflow-y-auto">
          <h2 className="mb-3 px-3 text-sm font-semibold text-foreground">
            Account Settings
          </h2>
          <div className="mb-4 border-b border-border/50" />
          <ul className="space-y-1">
            {accountSettingsNav.map((item) => (
              <NavItem key={item.href} item={item} pathname={pathname} />
            ))}
          </ul>
        </nav>

        <div className="flex-1 overflow-auto p-6">
          <div className="mx-auto max-w-4xl">{children}</div>
        </div>
      </div>
    </div>
  );
}
