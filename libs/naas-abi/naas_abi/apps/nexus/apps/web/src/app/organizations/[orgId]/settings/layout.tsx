'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname, useParams, useRouter } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { useRememberSettingsPath } from '@/hooks/use-remember-settings-scope';
import { useSettingsTabs } from '@/hooks/use-settings-levels';
import { useWorkspaceStore } from '@/stores/workspace';
import { opensAccess } from '@/components/access/access-sections';
import { organizationContainer } from '@/components/access/access-scope';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { readOrganization } from '@/lib/organization-resource';
import { useAnalyticsAccess } from '@/hooks/use-analytics-access';
import { SettingsLevelsNav } from '@/components/settings/settings-levels-nav';
import { SettingsLayoutRoot, useWorkspaceReturnPath } from '@/components/settings/settings-shell';
import { SettingsShellHeader } from '@/components/settings/settings-shell-header';
import { SettingsNoAccess } from '@/components/settings/settings-no-access';
import {
  orgSectionRedirect,
  orgSettingsAccess,
  orgSettingsIndexPath,
  orgSettingsNavForRole,
  orgSettingsSectionPath,
} from './lib/nav';
import { parseOrgSettingsRoute } from './lib/org-settings-route';
import './org-settings-layout.css';

const MEMBER_PAGE = /^\/organizations\/[^/]+\/settings\/users\/(?!new(?:[/?#]|$))[^/?#]+/;

export default function OrganizationSettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const params = useParams();
  const orgId = params.orgId as string;
  // The list already carries the caller's role: the tabs use it without waiting for this
  // organization's own read (colours, and a role the list does not have yet).
  const { status: orgsStatus, orgs } = useOpenableOrganizations();
  const listed = orgs.find((org) => org.id === orgId);
  // The caller's role, for the organization it was read for: a client-side move to
  // another organization knows no role there until its own read answers.
  const [viewer, setViewer] = useState<{ orgId: string; role: string | null } | null>(null);
  const fetched = !!orgId && viewer?.orgId === orgId;
  const roleKnown = fetched || (orgsStatus !== 'checking' && !!listed);
  const viewerRole = fetched ? viewer.role : (listed?.role ?? null);
  const isMobile = useIsMobile();
  // The organization list is the permission read for these tabs. An owner or admin sees
  // Analytics and Access at once; a read that says no takes the entry off, and the page
  // loads on its own.
  const listReady = orgsStatus !== 'checking';
  const { access, loading: accessLoading } = useIamAccess(orgId ? organizationContainer(orgId) : undefined, undefined, {
    skip: !listReady || !orgId,
  });
  const holdsIam = opensAccess(access, 'organization');
  const settingsAccess = orgSettingsAccess({
    role: viewerRole,
    roleKnown,
    holdsIam,
    accessSettled: listReady && !accessLoading,
  });
  const analyticsScope = listReady && orgId ? { kind: 'organization' as const, orgId } : null;
  const analyticsEntry = useAnalyticsAccess(analyticsScope);
  const readsAnalytics = analyticsEntry.access?.can_read === true;
  const visibleNav = useMemo(
    () =>
      orgSettingsNavForRole(viewerRole, {
        access,
        readsAnalytics,
        accessKnown: listReady && !!orgId && !accessLoading,
        analyticsKnown: !!analyticsScope && analyticsEntry.status !== 'checking',
      }),
    [viewerRole, access, readsAnalytics, listReady, orgId, accessLoading, analyticsScope, analyticsEntry.status]
  );
  const navOrganization = useMemo(() => ({ id: orgId, items: visibleNav }), [orgId, visibleNav]);
  const { tabs, level, pagesReady } = useSettingsTabs({ organization: navOrganization, mobile: isMobile });
  const { isDetail, section, sectionLabel } = parseOrgSettingsRoute(pathname);
  // A member's page (`users/<id>`): whoever opens Access here sees what they hold there.
  const memberPage = section === 'users' && MEMBER_PAGE.test(pathname ?? '');
  const showMobileList = isMobile && !isDetail;
  const showMobileDetail = isMobile && isDetail;
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  const [borderRadius, setBorderRadius] = useState('0');
  // The organization's colours, not the last workspace's (see SettingsLayoutRoot).
  const [orgColors, setOrgColors] = useState<{ primary: string | null; accent: string | null }>({
    primary: null,
    accent: null,
  });

  // Reopened only once its section opens: not while the role or the access is read, not
  // refused, not the index, nor a section that sends the caller to Access.
  const sectionOpens =
    !!sectionLabel &&
    (settingsAccess === 'admin' || settingsAccess === 'iam') &&
    !orgSectionRedirect({ section, memberPage, role: viewerRole, roleKnown, access, accessSettled: !accessLoading });
  useRememberSettingsPath(sectionOpens ? pathname : null);

  useEffect(() => {
    const fetchOrg = async (force = false) => {
      try {
        const response = await readOrganization(orgId, { force });
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

    if (orgId && pagesReady) {
      fetchOrg();
    }

    // New colours and corners: read again and restyle in place. The page under it is not
    // remounted, so what it shows (filters, unsaved edits, scroll) stays.
    const handleBrandingUpdate = () => {
      void fetchOrg(true);
    };

    window.addEventListener('org-branding-updated', handleBrandingUpdate);
    return () => window.removeEventListener('org-branding-updated', handleBrandingUpdate);
  }, [orgId, pagesReady]);

  useEffect(() => {
    if (!orgId) return;
    const target = orgSectionRedirect({
      section,
      memberPage,
      role: viewerRole,
      roleKnown,
      access,
      accessSettled: !accessLoading,
    });
    if (target) router.replace(orgSettingsSectionPath(orgId, target));
  }, [orgId, viewerRole, roleKnown, section, memberPage, access, accessLoading, router]);

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
    <SettingsLayoutRoot brand={orgColors} borderRadius={borderRadius}>
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
