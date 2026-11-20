'use client';

import { useMemo } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { RefreshCw, ShieldCheck } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useRememberSettingsPath } from '@/hooks/use-remember-settings-scope';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { useSettingsTabs } from '@/hooks/use-settings-levels';
import { useWorkspaceStore } from '@/stores/workspace';
import { SettingsLevelsNav } from '@/components/settings/settings-levels-nav';
import { SettingsLayoutRoot, useWorkspaceReturnPath } from '@/components/settings/settings-shell';
import { SettingsShellHeader } from '@/components/settings/settings-shell-header';
import { SettingsLoading } from '@/components/settings/settings-ui';
import {
  holds,
  laysOutOwnPanes,
  parsePlatformSettingsRoute,
  PLATFORM_SETTINGS_INDEX,
  READ_SYSTEM,
  visiblePlatformSettingsGroups,
} from './lib/nav';
import { PLATFORM_TABLES_PATH, platformTablePath } from './lib/tables';
import { useTablesView } from './lib/tables-view';
import { JobFailuresContext, useJobFailures } from './system/jobs/failures';
import { createJobsApi } from './system/jobs/jobs-api';
import { systemViewPath } from './system/system-tabs';
// Same shell as Organization Settings, so both settings areas look alike.
import '@/app/organizations/[orgId]/settings/org-settings-layout.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import '@/app/organizations/[orgId]/settings/users/users.css';
import './platform-settings.css';

/** No item for this caller, or not this one: the 403 of Platform Settings. */
function PlatformSettingsForbidden({ onRetry }: { onRetry?: () => void }) {
  const error = !!onRetry;
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
          ? 'The permission service did not answer. Try again in a moment.'
          : 'The platform shows what your permissions let you open. Ask a platform administrator for access.'}
      </p>
      {error && (
        <button
          type="button"
          className="org-settings-users-secondary-button platform-settings-retry"
          onClick={onRetry}
        >
          <RefreshCw size={16} />
          Try again
        </button>
      )}
    </div>
  );
}

export default function PlatformSettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? PLATFORM_SETTINGS_INDEX;
  const router = useRouter();
  const { status, actions, retry } = usePlatformSettingsAccess({ fresh: true });
  const isMobile = useIsMobile();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const groups = useMemo(() => visiblePlatformSettingsGroups(actions), [actions]);
  const { tabs, level } = useSettingsTabs({ mobile: isMobile });

  // Runs that failed since the admin last looked: the Jobs item's badge, and the Jobs page.
  const jobsApi = useMemo(() => createJobsApi(), []);
  const jobFailures = useJobFailures(jobsApi, holds(READ_SYSTEM, actions));
  const failures = jobFailures.failures;
  const jobsBadge =
    failures && failures.count > 0 ? (failures.more ? `${failures.count}+` : String(failures.count)) : null;
  const badges = useMemo(
    () =>
      jobsBadge
        ? { [systemViewPath('jobs')]: { text: jobsBadge, title: `${jobsBadge} failed runs since you last looked` } }
        : undefined,
    [jobsBadge]
  );

  const { isDetail, item, table, rowId } = parsePlatformSettingsRoute(pathname);
  const isTables = item?.id === 'tables';
  // System, Activity, Resources and Data lay out their own panes, edge to edge; the
  // Administration pages keep the organization pages' margins.
  const isFramed = !!item && laysOutOwnPanes(item);
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
      // A row goes back to its table, a table to Nexus tables, a setting to the list.
      if (rowId && table) router.push(platformTablePath(table));
      else if (table) router.push(PLATFORM_TABLES_PATH);
      else router.push(PLATFORM_SETTINGS_INDEX);
      return;
    }
    router.push(workspaceHref);
  };

  const tableLabel = useTablesView((state) => (table ? state.labels[table] : undefined));
  const detailTitle = table ? (tableLabel ?? table) : (item?.label ?? 'Platform');

  const ready = status === 'ready';
  const allowed = ready && (item ? holds(item.needs, actions) : groups.length > 0);
  // Reopened only once the page opens: not while the access is read, refused, or the index.
  useRememberSettingsPath(item && allowed ? pathname : null);

  let content: React.ReactNode;
  if (status === 'checking') content = <SettingsLoading />;
  else if (status === 'error') content = <PlatformSettingsForbidden onRetry={retry} />;
  else if (!allowed) content = <PlatformSettingsForbidden />;
  else content = children;

  return (
    <JobFailuresContext.Provider value={jobFailures}>
      <SettingsLayoutRoot className="platform-settings-root">
        <div className="org-settings-layout-left">
          <SettingsShellHeader
            detailTitle={showMobileDetail ? detailTitle : null}
            tabs={showMobileDetail ? undefined : tabs}
            onBack={handleBack}
            backAriaLabel={showMobileDetail ? 'Back' : 'Back to workspace'}
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
            {/* A phone lists the items on /settings, then opens one at a time. */}
            {!showMobileDetail && <SettingsLevelsNav level={level} mobileList={showMobileList} badges={badges} />}

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
