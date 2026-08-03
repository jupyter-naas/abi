'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowLeft, ChevronRight } from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { accountSettingsNavVisible, type AccountSettingsNavItem } from './lib/nav';
import { parseAccountRoute } from './lib/account-route';
import './account-layout.css';

function NavItem({
  item,
  pathname,
  mobileList = false,
}: {
  item: AccountSettingsNavItem;
  pathname: string;
  mobileList?: boolean;
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
        <span className="account-nav-item-label">{item.label}</span>
        {mobileList && <ChevronRight size={18} className="account-nav-item-chevron" />}
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
  const isMobile = useIsMobile();
  const { isDetail, sectionLabel } = parseAccountRoute(pathname);
  const showMobileList = isMobile && !isDetail;
  const showMobileDetail = isMobile && isDetail;
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
    if (showMobileDetail) {
      router.push('/account');
      return;
    }
    if (currentWorkspaceId) {
      router.push(`/workspace/${currentWorkspaceId}/chat`);
    } else {
      router.push('/');
    }
  };

  const headerTitle = showMobileDetail
    ? sectionLabel ?? 'Account'
    : user?.name || 'Account';

  const showNav = !showMobileDetail;
  const showMain = !showMobileList;

  return (
    <div
      className="account-layout-root"
      data-org-branded="true"
      style={themeStyles}
    >
      <header className="account-layout-header">
        <button
          type="button"
          onClick={handleBack}
          className="account-back-button"
          aria-label={showMobileDetail ? 'Back to account settings' : 'Back to workspace'}
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="account-layout-header-title">{headerTitle}</h1>
        </div>
      </header>

      <div
        className={
          showMobileList
            ? 'account-layout-body account-layout-body-mobile-list'
            : showMobileDetail
              ? 'account-layout-body account-layout-body-mobile-detail'
              : 'account-layout-body'
        }
      >
        {showNav && (
          <nav className="account-layout-nav">
            <h2 className="account-layout-nav-title">Account Settings</h2>
            <div className="account-layout-nav-divider" />
            <ul className="account-layout-nav-list">
              {accountSettingsNavVisible.map((item) => (
                <NavItem
                  key={item.href}
                  item={item}
                  pathname={pathname}
                  mobileList={showMobileList}
                />
              ))}
            </ul>
          </nav>
        )}

        {showMain && (
          <div className="account-layout-main">
            <div className="account-layout-content">{children}</div>
          </div>
        )}
      </div>
    </div>
  );
}
