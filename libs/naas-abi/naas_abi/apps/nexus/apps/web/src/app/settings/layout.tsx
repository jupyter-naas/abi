'use client';

import { useMemo } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useWorkspaceStore } from '@/stores/workspace';
import { SettingsLayoutNav } from '@/components/settings/settings-layout-nav';
import {
  SettingsLayoutRoot,
  SettingsNavItem,
  useWorkspaceReturnPath,
} from '@/components/settings/settings-shell';
import { SettingsLoading } from '@/components/settings/settings-ui';
import {
  holds,
  parsePlatformSettingsRoute,
  PLATFORM_SETTINGS_INDEX,
  READ_SYSTEM,
  visiblePlatformSettingsGroups,
  type PlatformSettingsNavItem,
} from './lib/nav';
import { PLATFORM_TABLES_PATH, platformTablePath } from './lib/tables';
import { JobFailuresContext, useJobFailures } from './system/jobs/failures';
import { createJobsApi } from './system/jobs/jobs-api';
// Same shell as Organization Settings, so both settings areas look alike.
import '@/app/organizations/[orgId]/settings/org-settings-layout.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import './platform-settings.css';

function NavItem({
  item,
  active,
  badge,
  mobileList,
}: {
  item: PlatformSettingsNavItem;
  active: boolean;
  badge?: string | null;
  mobileList: boolean;
}) {
  return (
    <SettingsNavItem
      href={item.href}
      label={item.label}
      icon={item.icon}
      active={active}
      chevron={mobileList}
      badge={badge}
      badgeTitle={badge ? `${badge} failed runs since you last looked` : undefined}
    />
  );
}

/** No item for this caller, or not this one: the 403 of Platform Settings. */
function PlatformSettingsForbidden({ error }: { error?: boolean }) {
  return (
    <div className="org-settings-empty">
      <div className="org-settings-empty-icon">
        <ShieldCheck size={24} />
      </div>
      <p className="org-settings-empty-title">
        {error ? 'Your access could not be checked' : 'You do not have access to this page'}
      </p>
      <p className="org-settings-empty-body">
        {error
          ? 'Reload the page to try again.'
          : 'Platform Settings shows what your permissions let you open. Ask a platform administrator for access.'}
      </p>
    </div>
  );
}

export default function PlatformSettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? PLATFORM_SETTINGS_INDEX;
  const router = useRouter();
  const { status, actions } = usePlatformSettingsAccess({ fresh: true });
  const isMobile = useIsMobile();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const groups = useMemo(() => visiblePlatformSettingsGroups(actions), [actions]);
  const sectionHrefs = useMemo(
    () => groups.flatMap((group) => group.items.map((item) => item.href)),
    [groups]
  );
  useDevRouteWarmup(sectionHrefs);

  // Runs that failed since the admin last looked: the Jobs item's badge, and the Jobs page.
  const jobsApi = useMemo(() => createJobsApi(), []);
  const jobFailures = useJobFailures(jobsApi, holds(READ_SYSTEM, actions));
  const failures = jobFailures.failures;
  const jobsBadge =
    failures && failures.count > 0 ? (failures.more ? `${failures.count}+` : String(failures.count)) : null;

  const { isDetail, item, table, rowId } = parsePlatformSettingsRoute(pathname);
  const isTables = item?.id === 'tables';
  // System and Roles & permissions lay out their own panes, edge to edge.
  const isFramed = !!item && !isTables;
  // A table page fills the height: the table scrolls, not the page (headers stay visible).
  const fillsHeight = isTables && !!table && !rowId;
  const showMobileList = isMobile && !isDetail;
  const showMobileDetail = isMobile && isDetail;

  const workspaceHref = useWorkspaceReturnPath(
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}/chat` : '/',
    currentWorkspaceId
  );

  const handleBack = () => {
    if (showMobileDetail) {
      // A row goes back to its table, a table to Nexus tables, a page to the list.
      if (rowId && table) router.push(platformTablePath(table));
      else if (table) router.push(PLATFORM_TABLES_PATH);
      else router.push(PLATFORM_SETTINGS_INDEX);
      return;
    }
    router.push(workspaceHref);
  };

  const headerTitle = showMobileDetail
    ? (table ?? item?.label ?? 'Platform Settings')
    : 'Platform Settings';

  const ready = status === 'ready';
  const allowed = ready && (item ? holds(item.needs, actions) : groups.length > 0);

  let content: React.ReactNode;
  if (status === 'checking') content = <SettingsLoading />;
  else if (status === 'error') content = <PlatformSettingsForbidden error />;
  else if (!allowed) content = <PlatformSettingsForbidden />;
  else content = children;

  const nav = (
    <SettingsLayoutNav title="Platform Settings" resizable={!showMobileList}>
      {ready &&
        groups.map((group) => (
          <div key={group.label ?? 'general'} className="platform-settings-nav-group">
            {group.label && <h3 className="platform-settings-nav-group-title">{group.label}</h3>}
            <ul className="settings-layout-nav-list">
              {group.items.map((navItem) => (
                <NavItem
                  key={navItem.id}
                  item={navItem}
                  active={navItem.id === item?.id}
                  badge={navItem.id === 'system-jobs' ? jobsBadge : null}
                  mobileList={showMobileList}
                />
              ))}
            </ul>
          </div>
        ))}
    </SettingsLayoutNav>
  );

  return (
    <JobFailuresContext.Provider value={jobFailures}>
      <SettingsLayoutRoot className="platform-settings-root">
        <div className="org-settings-layout-left">
          <header className="org-settings-layout-header">
            <div className="org-settings-layout-header-inner">
              <button
                type="button"
                onClick={handleBack}
                className="org-settings-back-button"
                aria-label={showMobileDetail ? 'Back' : 'Back to workspace'}
              >
                <ArrowLeft size={20} />
              </button>
              <div className="org-settings-layout-header-meta">
                {!showMobileDetail && (
                  <ShieldCheck size={16} className="org-settings-layout-header-icon" />
                )}
                <h1 className="org-settings-layout-header-title">{headerTitle}</h1>
              </div>
            </div>
          </header>

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
            {/* A phone lists the items on /settings, then opens one at a time. */}
            {!showMobileDetail && nav}

            {!(showMobileList && ready && allowed) && (
              <div
                className={[
                  'org-settings-layout-main',
                  fillsHeight && 'platform-settings-main-fill',
                  isFramed && allowed && 'platform-settings-main-framed',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <div
                  className={[
                    'org-settings-layout-content',
                    isTables && !!table && 'platform-settings-content-wide',
                    fillsHeight && 'platform-settings-content-fill',
                    isFramed && allowed && 'platform-settings-content-framed',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {content}
                </div>
              </div>
            )}
          </div>
        </div>
      </SettingsLayoutRoot>
    </JobFailuresContext.Provider>
  );
}
