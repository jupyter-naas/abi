'use client';

import { useMemo } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { useSuperadminAccess } from '@/hooks/use-superadmin-access';
import { useWorkspaceStore } from '@/stores/workspace';
import { SettingsLayoutNav } from '@/components/settings/settings-layout-nav';
import {
  SettingsLayoutRoot,
  SettingsNavItem,
  useWorkspaceReturnPath,
} from '@/components/settings/settings-shell';
import { SettingsLoading } from '@/components/settings/settings-ui';
import {
  PLATFORM_SETTINGS_INDEX,
  parsePlatformSettingsRoute,
  platformSettingsGroups,
  platformSettingsNav,
  platformSettingsSectionPath,
  type PlatformSettingsNavItem,
} from './lib/nav';
// Same shell as Organization Settings, so both settings areas look alike.
import '@/app/organizations/[orgId]/settings/org-settings-layout.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import './platform-settings.css';

function NavItem({
  item,
  pathname,
}: {
  item: PlatformSettingsNavItem;
  pathname: string;
}) {
  const fullHref = platformSettingsSectionPath(item.slug);
  // The dashboard (/settings) is active only on itself, not on every table page.
  const isActive = item.slug
    ? pathname === fullHref || pathname.startsWith(`${fullHref}/`)
    : pathname === fullHref || pathname === `${fullHref}/`;
  return <SettingsNavItem href={fullHref} label={item.label} icon={item.icon} active={isActive} />;
}

function PlatformSettingsForbidden() {
  return (
    <div className="org-settings-empty">
      <div className="org-settings-empty-icon">
        <ShieldCheck size={24} />
      </div>
      <p className="org-settings-empty-title">Platform superadmins only</p>
      <p className="org-settings-empty-body">
        Ask a platform superadmin for access.
      </p>
    </div>
  );
}

export default function PlatformSettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? PLATFORM_SETTINGS_INDEX;
  const router = useRouter();
  const access = useSuperadminAccess();
  const isMobile = useIsMobile();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const sectionHrefs = useMemo(
    () => platformSettingsNav.map((item) => platformSettingsSectionPath(item.slug)),
    []
  );
  useDevRouteWarmup(sectionHrefs);

  const { isDetail, section, sectionLabel, rowId } = parsePlatformSettingsRoute(pathname);
  // Table and row pages show many columns, so they use the full width of the page.
  const isTablePage = isDetail;
  // A table page fills the height: the table scrolls, not the page (headers stay visible).
  const fillsHeight = isDetail && !rowId;
  // On mobile the dashboard is the list of tables, so the nav is not shown.
  const showMobileTablePage = isMobile && isDetail;

  const workspaceHref = useWorkspaceReturnPath(
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}/chat` : '/',
    currentWorkspaceId
  );

  const handleBack = () => {
    if (showMobileTablePage) {
      // A row page goes back to its table, a table page to the dashboard.
      router.push(
        rowId && section ? platformSettingsSectionPath(section) : PLATFORM_SETTINGS_INDEX
      );
      return;
    }
    router.push(workspaceHref);
  };

  const headerTitle =
    showMobileTablePage ? sectionLabel ?? 'Platform Settings' : 'Platform Settings';

  return (
    <SettingsLayoutRoot className="platform-settings-root">
      <div className="org-settings-layout-left">
        <header className="org-settings-layout-header">
          <div className="org-settings-layout-header-inner">
            <button
              type="button"
              onClick={handleBack}
              className="org-settings-back-button"
              aria-label={showMobileTablePage ? 'Back to platform settings' : 'Back to workspace'}
            >
              <ArrowLeft size={20} />
            </button>
            <div className="org-settings-layout-header-meta">
              {!showMobileTablePage && (
                <ShieldCheck size={16} className="org-settings-layout-header-icon" />
              )}
              <h1 className="org-settings-layout-header-title">{headerTitle}</h1>
            </div>
          </div>
        </header>

        <div
          data-org-settings-body=""
          className={
            isMobile
              ? 'org-settings-layout-body org-settings-layout-body-mobile-detail'
              : 'org-settings-layout-body'
          }
        >
          {!isMobile && (
            <SettingsLayoutNav title="Platform Settings">
              {access === 'authorized' &&
                platformSettingsGroups.map((group) => (
                  <div key={group.label ?? 'general'} className="platform-settings-nav-group">
                    {group.label && (
                      <h3 className="platform-settings-nav-group-title">{group.label}</h3>
                    )}
                    <ul className="settings-layout-nav-list">
                      {group.items.map((item) => (
                        <NavItem
                          key={item.slug}
                          item={item}
                          pathname={pathname}
                        />
                      ))}
                    </ul>
                  </div>
                ))}
            </SettingsLayoutNav>
          )}

          <div
            className={
              fillsHeight
                ? 'org-settings-layout-main platform-settings-main-fill'
                : 'org-settings-layout-main'
            }
          >
            <div
              className={[
                'org-settings-layout-content',
                isTablePage && 'platform-settings-content-wide',
                fillsHeight && 'platform-settings-content-fill',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              {access === 'checking' ? (
                <SettingsLoading />
              ) : access === 'denied' ? (
                <PlatformSettingsForbidden />
              ) : (
                children
              )}
            </div>
          </div>
        </div>
      </div>
    </SettingsLayoutRoot>
  );
}
