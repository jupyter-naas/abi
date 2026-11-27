'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { AppWindow, Globe, Tag, ExternalLink } from 'lucide-react';
import { useAppsStore, type AppItem } from '@/stores/apps';
import { Badge } from '@/components/ui/badge';
import { SettingsPageHeader, SettingsTableToolbar, countLabel } from '@/components/settings/settings-ui';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import {
  SettingsTableClear,
  SettingsTableHead,
  SettingsTableNoMatch,
  useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import {
  APP_COLUMNS,
  APP_EXPORT_HEADERS,
  appCellValues,
  appExportRow,
  appSearchTexts,
  appSource,
  installedApps as installedOf,
} from './apps-model';

const CATEGORY_BADGE: Record<string, 'primary' | 'warning' | 'neutral'> = {
  core: 'primary',
  alpha: 'warning',
};

function AppLogo({ app }: { app: AppItem }) {
  const [failed, setFailed] = useState(false);
  if (app.avatar_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={app.avatar_url}
        alt={app.name}
        className="h-9 w-9 object-cover"
        onError={() => setFailed(true)}
      />
    );
  }
  if (app.icon_emoji) {
    return (
      <div className="flex h-9 w-9 items-center justify-center bg-muted text-xl">
        {app.icon_emoji}
      </div>
    );
  }
  return (
    <div className="flex h-9 w-9 items-center justify-center bg-muted">
      <Globe size={18} className="text-muted-foreground" />
    </div>
  );
}

/**
 * Settings › Apps, laid out as Settings › Users: a search, columns that sort and filter (the
 * category from its column), 20 rows a page, an export of the rows shown.
 */
export default function AppsSettingsPage() {
  const params = useParams();
  const workspaceId = params?.workspaceId as string | undefined;
  const [mounted, setMounted] = useState(false);

  const { apps, loading, fetchApps } = useAppsStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    void fetchApps(workspaceId);
  }, [workspaceId, fetchApps]);

  const installedApps = useMemo(() => installedOf(apps), [apps]);
  const table = useSettingsTable({
    rows: installedApps,
    columns: APP_COLUMNS,
    cellValues: appCellValues,
    searchTexts: appSearchTexts,
    initialSort: 'app',
  });
  const shown = table.shown;

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(APP_EXPORT_HEADERS, shown.map(appExportRow), format, `apps_${date}`, 'Apps');
  };

  if (!mounted) {
    return <Loading label="Loading apps…" />;
  }

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Apps"
        badge={`${installedApps.length} ${installedApps.length === 1 ? 'app' : 'apps'}`}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/apps']}
        actions={<UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />}
      />

      {loading && installedApps.length === 0 ? (
        <Loading label="Loading apps…" />
      ) : installedApps.length === 0 ? (
        <EmptyState framed
          icon={<AppWindow size={40} className="opacity-40" />}
          title="No apps in this workspace"
          description="No module of this workspace has an app you may open. Policies on Roles & permissions decide who opens which app."
        />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search apps..."
            meta={
              <>
                {countLabel(shown.length, installedApps.length, 'app')}
                <SettingsTableClear table={table} />
              </>
            }
          />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={APP_COLUMNS.length} noun="apps" />}
                {table.paged.pageRows.map((app) => (
                  <tr key={app.app_id} data-app={app.app_id}>
                    <td className="align-top">
                      <div className="flex min-h-[3.25rem] items-center gap-3">
                        <AppLogo app={app} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{app.name}</p>
                            {app.url && (
                              <a
                                href={app.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-muted-foreground hover:text-foreground"
                                title="Open in new tab"
                              >
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                          <p
                            className="line-clamp-2 min-h-[2rem] text-xs text-muted-foreground"
                            title={app.description || undefined}
                          >
                            {app.description || ' '}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td>
                      <Badge variant={CATEGORY_BADGE[app.category] ?? 'neutral'}>
                        <Tag size={9} />
                        {app.category}
                      </Badge>
                    </td>
                    <td className="truncate text-muted-foreground">{appSource(app)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <TablePager total={shown.length} paged={table.paged} />
        </div>
      )}
    </div>
  );
}
