'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useRememberSettingsPath } from '@/hooks/use-remember-settings-scope';
import { useSettingsTabs } from '@/hooks/use-settings-levels';
import { loadOrgBranding, resolveWorkspaceOrgId } from '@/lib/org-branding';
import { SettingsLevelsNav } from '@/components/settings/settings-levels-nav';
import { SettingsLayoutRoot, useWorkspaceReturnPath } from '@/components/settings/settings-shell';
import { SettingsShellHeader } from '@/components/settings/settings-shell-header';
import { parseAccountRoute } from './lib/account-route';
import '@/app/organizations/[orgId]/settings/org-settings-layout.css';

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
  const { tabs, level } = useSettingsTabs({ mobile: isMobile });

  // Every account page opens; the index is the phone's list, never reopened.
  useRememberSettingsPath(sectionLabel ? pathname : null);

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
          detailTitle={showMobileDetail ? sectionLabel : null}
          tabs={showMobileDetail ? undefined : tabs}
          onBack={handleBack}
          backAriaLabel={showMobileDetail ? 'Back to settings' : 'Back to workspace'}
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
          {showNav && <SettingsLevelsNav level={level} mobileList={showMobileList} />}

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
