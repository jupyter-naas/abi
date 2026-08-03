'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Building2, ChevronRight } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  orgSettingsIndexPath,
  orgSettingsNav,
  orgSettingsSectionPath,
  type OrgSettingsNavItem,
} from './lib/nav';
import { parseOrgSettingsRoute } from './lib/org-settings-route';
import './org-settings-layout.css';

function NavItem({
  item,
  pathname,
  orgId,
  mobileList = false,
}: {
  item: OrgSettingsNavItem;
  pathname: string;
  orgId: string;
  mobileList?: boolean;
}) {
  const fullHref = orgSettingsSectionPath(orgId, item.slug);
  const isActive = pathname === fullHref;
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={fullHref}
        className={
          isActive
            ? 'org-settings-nav-item org-settings-nav-item-active'
            : 'org-settings-nav-item'
        }
      >
        <Icon size={18} />
        <span className="org-settings-nav-item-label">{item.label}</span>
        {mobileList && (
          <ChevronRight size={18} className="org-settings-nav-item-chevron" />
        )}
      </Link>
    </li>
  );
}

export default function OrganizationSettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const params = useParams();
  const orgId = params.orgId as string;
  const isMobile = useIsMobile();
  const { isDetail, sectionLabel } = parseOrgSettingsRoute(pathname);
  const showMobileList = isMobile && !isDetail;
  const showMobileDetail = isMobile && isDetail;
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  const [orgName, setOrgName] = useState('');
  const [borderRadius, setBorderRadius] = useState('0');
  const [orgCount, setOrgCount] = useState<number | null>(null);
  const [layoutKey, setLayoutKey] = useState(0);

  useEffect(() => {
    const fetchOrg = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');

        const response = await authFetch(`/api/organizations/${orgId}`);
        if (response.ok) {
          const data = await response.json();
          setOrgName(data.name);
          const radius = data.loginBorderRadius ?? data.login_border_radius ?? '0';
          setBorderRadius(radius);
        }

        const orgsResponse = await authFetch('/api/organizations/');
        if (orgsResponse.ok) {
          const orgs = await orgsResponse.json();
          setOrgCount(orgs.length);
        }
      } catch (error) {
        console.error('Failed to fetch organization:', error);
      }
    };

    if (orgId) {
      fetchOrg();
    }

    const handleBrandingUpdate = () => {
      fetchOrg();
      setLayoutKey((prev) => prev + 1);
    };

    window.addEventListener('org-branding-updated', handleBrandingUpdate);
    return () => window.removeEventListener('org-branding-updated', handleBrandingUpdate);
  }, [orgId]);

  const themeStyles = {
    '--org-border-radius': `${borderRadius}px`,
  } as React.CSSProperties;

  const handleBack = () => {
    if (showMobileDetail) {
      router.push(orgSettingsIndexPath(orgId));
      return;
    }
    if (orgCount === 1) {
      if (currentWorkspaceId) {
        router.push(`/workspace/${currentWorkspaceId}/maps/presence`);
      } else {
        router.push('/');
      }
      return;
    }
    router.push('/organizations');
  };

  const headerTitle = showMobileDetail
    ? sectionLabel ?? 'Organization Settings'
    : orgName || 'Organization Settings';

  const showNav = !showMobileDetail;
  const showMain = !showMobileList;

  return (
    <div
      className="org-settings-layout-root"
      data-org-branded="true"
      style={themeStyles}
      key={layoutKey}
    >
      <header className="org-settings-layout-header">
        <div className="org-settings-layout-header-inner">
          <button
            type="button"
            onClick={handleBack}
            className="org-settings-back-button"
            aria-label={
              showMobileDetail
                ? 'Back to organization settings'
                : orgCount === 1
                  ? 'Back to workspace'
                  : 'Back to organizations'
            }
          >
            <ArrowLeft size={20} />
          </button>
          <div className="org-settings-layout-header-meta">
            {!showMobileDetail && <Building2 size={16} className="org-settings-layout-header-icon" />}
            <h1 className="org-settings-layout-header-title">{headerTitle}</h1>
          </div>
        </div>
      </header>

      <div
        className={
          showMobileList
            ? 'org-settings-layout-body org-settings-layout-body-mobile-list'
            : showMobileDetail
              ? 'org-settings-layout-body org-settings-layout-body-mobile-detail'
              : 'org-settings-layout-body'
        }
      >
        {showNav && (
          <nav className="org-settings-layout-nav">
            <h2 className="org-settings-layout-nav-title">Organization Settings</h2>
            <div className="org-settings-layout-nav-divider" />
            <ul className="org-settings-layout-nav-list">
              {orgSettingsNav.map((item) => (
                <NavItem
                  key={item.slug}
                  item={item}
                  pathname={pathname}
                  orgId={orgId}
                  mobileList={showMobileList}
                />
              ))}
            </ul>
          </nav>
        )}

        {showMain && (
          <div className="org-settings-layout-main">
            <div className="org-settings-layout-content">{children}</div>
          </div>
        )}
      </div>
    </div>
  );
}
