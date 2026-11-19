'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { User } from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useRememberSettingsScope } from '@/hooks/use-remember-settings-scope';
import { loadOrgBranding, resolveWorkspaceOrgId } from '@/lib/org-branding';
import { SettingsLayoutNav } from '@/components/settings/settings-layout-nav';
import {
  SettingsLayoutRoot,
  SettingsNavItem,
  useWorkspaceReturnPath,
} from '@/components/settings/settings-shell';
import { SettingsShellHeader } from '@/components/settings/settings-shell-header';
import { accountSettingsNavVisible, type AccountSettingsNavItem } from './lib/nav';
import { parseAccountRoute } from './lib/account-route';
import '@/app/organizations/[orgId]/settings/org-settings-layout.css';

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
    <SettingsNavItem
      href={item.href}
      label={item.label}
      icon={Icon}
      active={isActive}
      chevron={mobileList}
    />
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
  const workspaceOrgId = useWorkspaceStore(
    (state) => state.workspaces.find((w) => w.id === state.currentWorkspaceId)?.organizationId,
  );
  const [borderRadius, setBorderRadius] = useState('0');

  useRememberSettingsScope(pathname);

  useEffect(() => {
    let cancelled = false;
    const fetchOrgBranding = async () => {
      if (!currentWorkspaceId) {
        setBorderRadius('0');
        return;
      }
      const orgId = await resolveWorkspaceOrgId(currentWorkspaceId, workspaceOrgId);
      const branding = orgId ? await loadOrgBranding(orgId) : null;
      if (!cancelled) setBorderRadius(branding?.borderRadius ?? '0');
    };

    fetchOrgBranding();

    const handleBrandingUpdate = () => {
      fetchOrgBranding();
    };

    window.addEventListener('org-branding-updated', handleBrandingUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener('org-branding-updated', handleBrandingUpdate);
    };
  }, [currentWorkspaceId, workspaceOrgId]);

  const workspaceHref = useWorkspaceReturnPath(
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}/chat` : '/',
    currentWorkspaceId
  );

  const handleBack = () => {
    if (showMobileDetail) {
      router.push('/account');
      return;
    }
    router.push(workspaceHref);
  };

  const showNav = !showMobileDetail;
  const showMain = !showMobileList;

  return (
    <SettingsLayoutRoot borderRadius={borderRadius}>
      <div className="org-settings-layout-left">
        <SettingsShellHeader
          scopeTitle="Account"
          detailTitle={sectionLabel}
          showScopeSwitcher={!showMobileDetail}
          icon={User}
          onBack={handleBack}
          backAriaLabel={showMobileDetail ? 'Back to account settings' : 'Back to workspace'}
        />

        <div
          data-org-settings-body=""
          className={
            showMobileList
              ? 'org-settings-layout-body org-settings-layout-body-mobile-list'
              : showMobileDetail
                ? 'org-settings-layout-body org-settings-layout-body-mobile-detail'
                : 'org-settings-layout-body'
          }
        >
          {showNav && (
            <SettingsLayoutNav title="Account Settings" resizable={!showMobileList}>
              <ul className="settings-layout-nav-list">
                {accountSettingsNavVisible.map((item) => (
                  <NavItem
                    key={item.href}
                    item={item}
                    pathname={pathname ?? ''}
                    mobileList={showMobileList}
                  />
                ))}
              </ul>
            </SettingsLayoutNav>
          )}

          {showMain && (
            <div className="org-settings-layout-main">
              <div className="org-settings-layout-content">{children}</div>
            </div>
          )}
        </div>
      </div>
    </SettingsLayoutRoot>
  );
}