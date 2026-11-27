'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useState, useEffect, useMemo } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { AppWindow, Globe, Tag, ExternalLink } from 'lucide-react';
import { useAppsStore, type AppItem } from '@/stores/apps';
import { Badge } from '@/components/ui/badge';
import { ModuleLink } from '@/components/settings/module-link';
import { SettingsPageHeader, SettingsTableToolbar } from '@/components/settings/settings-ui';
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
import { SelectAllCell, SelectRowCell, useRowSelection } from '@/components/settings/bulk-access';
import { EnableBulkBar, EnabledCell, ModuleItemsStatus } from '@/components/settings/module-items';
import { moduleItemKey } from '@/components/settings/module-items-model';
import { policyOfSearch } from '@/components/settings/settings-policy';
import { useModuleItems } from '@/components/settings/use-module-items';
import type { OfferKind } from '@/lib/access-model/workspace-offer';
import {
  APP_COLUMNS,
  APP_EXPORT_HEADERS,
  appCellValues,
  appExportRow,
  appRows,
  appSearchTexts,
  appSource,
} from './apps-model';

const APP_KINDS: OfferKind[] = ['apps'];

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
 * category from its column), 20 rows a page, an export of the rows shown. Every app the
 * workspace's modules bring is listed, enabled or not by the policy picked in the Settings column
 * (`?policy=`): a table of switches, each change saved at once and said, the apps selected
 * enabled or disabled together.
 */
export default function AppsSettingsPage() {
  const params = useParams();
  const workspaceId = params?.workspaceId as string | undefined;
  const [mounted, setMounted] = useState(false);

  const { apps, loading, fetchApps } = useAppsStore();
  const policyId = policyOfSearch(useSearchParams());
  const catalog = useModuleItems({
    workspaceId,
    policyId,
    kinds: APP_KINDS,
    // What the caller may open changed: the apps are read again.
    onSaved: () => {
      if (workspaceId) void fetchApps(workspaceId);
    },
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    void fetchApps(workspaceId);
  }, [workspaceId, fetchApps]);

  const rows = useMemo(() => appRows(apps, catalog.items), [apps, catalog.items]);
  const table = useSettingsTable({
    rows,
    columns: APP_COLUMNS,
    cellValues: appCellValues,
    searchTexts: appSearchTexts,
    initialSort: 'app',
  });
  const shown = table.shown;
  // The module apps shown, checked for a batch change (select all takes the rows shown).
  const selectable = useMemo(
    () => shown.flatMap((row) => (row.item ? [moduleItemKey(row.item)] : [])),
    [shown]
  );
  const selection = useRowSelection(selectable);
  const locked = !catalog.editable || catalog.saving;

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
        badge={`${rows.length} ${rows.length === 1 ? 'app' : 'apps'}`}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/apps']}
        actions={<UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />}
      />

      <ModuleItemsStatus state={catalog} />

      {loading && rows.length === 0 ? (
        <Loading label="Loading apps…" />
      ) : rows.length === 0 ? (
        <EmptyState framed
          icon={<AppWindow size={40} className="opacity-40" />}
          title="No apps in this workspace"
          description="No module of this workspace has an app you may open. Policies, in Access › Policies, decide who opens which app."
        />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search apps..."
            // No count above the search: the badge says how many, the pager how many are shown.
            meta={<SettingsTableClear table={table} />}
          />
          <EnableBulkBar state={catalog} selection={selection} noun="app" />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={<SelectAllCell selection={selection} keys={selectable} noun="app" disabled={locked} />}
              />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={APP_COLUMNS.length + 1} noun="apps" />}
                {table.paged.pageRows.map((app) => (
                  <tr key={app.key ?? app.app_id} data-app={app.key ?? app.app_id}>
                    <SelectRowCell
                      selection={selection}
                      rowKey={app.item ? moduleItemKey(app.item) : (app.key ?? app.app_id)}
                      label={app.name}
                      disabled={!app.item || locked}
                    />
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
                      {/* An app the caller may not open: what the catalog says, no category. */}
                      {app.category ? (
                        <Badge variant={CATEGORY_BADGE[app.category] ?? 'neutral'}>
                          <Tag size={9} />
                          {app.category}
                        </Badge>
                      ) : null}
                    </td>
                    <td className="truncate text-muted-foreground">
                      {/* Its module links to its row in Access › Modules, where the workspace offers it. */}
                      {app.module_name && app.module_name === appSource(app) ? (
                        <ModuleLink workspaceId={workspaceId ?? ''} module={app.module_name} />
                      ) : (
                        <>
                          {appSource(app)}
                          {app.module_name ? (
                            <p className="text-micro italic">
                              <ModuleLink workspaceId={workspaceId ?? ''} module={app.module_name} />
                            </p>
                          ) : null}
                        </>
                      )}
                    </td>
                    <EnabledCell state={catalog} item={app.item ?? null} label={app.name} />
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
