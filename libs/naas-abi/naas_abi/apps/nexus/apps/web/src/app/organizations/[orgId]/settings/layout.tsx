'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname, useParams, useRouter } from 'next/navigation';
import { Building2 } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { useRememberSettingsScope } from '@/hooks/use-remember-settings-scope';
import { useWorkspaceStore } from '@/stores/workspace';
import { opensRolesAndPermissions } from '@/components/access/access-sections';
import { organizationContainer } from '@/components/access/access-scope';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { useReadsAnalytics } from '@/hooks/use-analytics-access';
import { SettingsLayoutNav } from '@/components/settings/settings-layout-nav';
import {
  SettingsLayoutRoot,
  SettingsNavItem,
  useWorkspaceReturnPath,
} from '@/components/settings/settings-shell';
import { SettingsShellHeader } from '@/components/settings/settings-shell-header';
import { SettingsNoAccess } from '@/components/settings/settings-no-access';
import {
  orgSectionRedirect,
  orgSettingsAccess,
  orgSettingsIndexPath,
  orgSettingsNavForRole,
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
  const isActive = pathname === fullHref || pathname.startsWith(`${fullHref}/`);
  return (
    <SettingsNavItem
      href={fullHref}
      label={item.label}
      icon={item.icon}
      active={isActive}
      chevron={mobileList}
    />
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
  // The caller's role, for the organization it was read for: a client-side move to
  // another organization knows no role there until its own read answers.
  const [viewer, setViewer] = useState<{ orgId: string; role: string | null } | null>(null);
  // Whether the organization was read (its answer, or a refusal): the role is known.
  const roleKnown = !!orgId && viewer?.orgId === orgId;
  const viewerRole = roleKnown ? viewer.role : null;
  // Roles & permissions is shown to whoever would see a section of it at the organization.
  const { access, loading: accessLoading } = useIamAccess(orgId ? organizationContainer(orgId) : undefined, undefined, {
    skip: !orgId,
  });
  const holdsIam = opensRolesAndPermissions(access);
  // The account menu's rule, for this organization: its owners and admins, or whoever IAM
  // shows a Roles & permissions section here. Anyone else sees no section.
  const settingsAccess = orgSettingsAccess({
    role: viewerRole,
    roleKnown,
    holdsIam,
    accessSettled: !accessLoading,
  });
  // Analytics is shown once the API says the caller may read the organization's.
  const readsAnalytics = useReadsAnalytics(orgId ? { kind: 'organization', orgId } : null);
  const visibleNav = useMemo(
    () => orgSettingsNavForRole(viewerRole, { holdsIam, readsAnalytics }),
    [viewerRole, holdsIam, readsAnalytics]
  );
  const sectionHrefs = useMemo(
    () => (orgId ? visibleNav.map((item) => orgSettingsSectionPath(orgId, item.slug)) : []),
    [orgId, visibleNav]
  );
  useDevRouteWarmup(sectionHrefs);
  const isMobile = useIsMobile();
  const { isDetail, section, sectionLabel } = parseOrgSettingsRoute(pathname);
  const showMobileList = isMobile && !isDetail;
  const showMobileDetail = isMobile && isDetail;
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  const [borderRadius, setBorderRadius] = useState('0');
  // The organization's colours, not the last workspace's (see SettingsLayoutRoot).
  const [orgColors, setOrgColors] = useState<{ primary: string | null; accent: string | null }>({
    primary: null,
    accent: null,
  });
  const [layoutKey, setLayoutKey] = useState(0);

  useRememberSettingsScope(pathname);

  useEffect(() => {
    const fetchOrg = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');

        const response = await authFetch(`/api/organizations/${orgId}`);
        if (response.ok) {
          const data = await response.json();
          setViewer({ orgId, role: data.current_user_role ?? null });
          const radius = data.loginBorderRadius ?? data.login_border_radius ?? '0';
          setBorderRadius(radius);
          setOrgColors({
            primary: data.primary_color ?? data.primaryColor ?? null,
            accent: data.accent_color ?? data.accentColor ?? null,
          });
        }

      } catch (error) {
        console.error('Failed to fetch organization:', error);
      } finally {
        // A refused or failed read leaves no role: decided as no role.
        setViewer((current) => (current?.orgId === orgId ? current : { orgId, role: null }));
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

  useEffect(() => {
    if (!orgId) return;
    const target = orgSectionRedirect({
      section,
      role: viewerRole,
      roleKnown,
      holdsIam,
      accessSettled: !accessLoading,
    });
    if (target) router.replace(orgSettingsSectionPath(orgId, target));
  }, [orgId, viewerRole, roleKnown, section, holdsIam, accessLoading, router]);

  const workspaceHref = useWorkspaceReturnPath(
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}/maps` : '/',
    currentWorkspaceId
  );

  const handleBack = () => {
    if (showMobileDetail) {
      router.push(orgSettingsIndexPath(orgId));
      return;
    }
    router.push(workspaceHref);
  };

  const showNav = !showMobileDetail;
  // On a phone the section list is the index; with no section, the refusal is shown instead.
  const showMain = !showMobileList || settingsAccess === 'none';

  return (
    <SettingsLayoutRoot key={layoutKey} brand={orgColors} borderRadius={borderRadius}>
      <div className="org-settings-layout-left">
      <SettingsShellHeader
        scopeTitle="Organization"
        detailTitle={sectionLabel}
        showScopeSwitcher={!showMobileDetail}
        icon={Building2}
        onBack={handleBack}
        backAriaLabel={
          showMobileDetail ? 'Back to organization settings' : 'Back to workspace'
        }
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
          <SettingsLayoutNav title="Organization Settings" resizable={!showMobileList}>
            <ul className="settings-layout-nav-list">
              {visibleNav.map((item) => (
                <NavItem
                  key={item.slug}
                  item={item}
                  pathname={pathname}
                  orgId={orgId}
                  mobileList={showMobileList}
                />
              ))}
            </ul>
          </SettingsLayoutNav>
        )}

        {showMain && (
          <div className="org-settings-layout-main">
            <div className="org-settings-layout-content">
              {settingsAccess === 'none' ? (
                <SettingsNoAccess of="organization" />
              ) : settingsAccess === 'unknown' ? null : (
                children
              )}
            </div>
          </div>
        )}
      </div>
      </div>
    </SettingsLayoutRoot>
  );
}
