'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Workflow } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ModuleLink } from '@/components/settings/module-link';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
} from '@/components/settings/settings-ui';
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
  WORKFLOW_COLUMNS,
  WORKFLOW_EXPORT_HEADERS,
  fetchWorkflowSettings,
  sortedWorkflows,
  workflowCellValues,
  workflowExportRow,
  workflowKey,
  workflowSearchTexts,
  type WorkflowSetting,
} from './workflows-model';

/**
 * Workspace settings › Workflows: the workflows and pipelines of the workspace's modules,
 * read-only, laid out as Settings › Users (a search, columns that sort and filter, pages, an
 * export). Who may run each is decided by policies alone, in Access › Policies: there is no
 * workspace on/off switch.
 */
export default function WorkflowsSettingsPage() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const [items, setItems] = useState<WorkflowSetting[] | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!workspaceId) return;
    setError('');
    try {
      setItems(await fetchWorkflowSettings(workspaceId));
    } catch (err) {
      setItems([]);
      setError(err instanceof Error ? err.message : 'Could not load the workflows.');
    }
  }, [workspaceId]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  // By module then name: rows that tie on the sorted column keep that order.
  const all = useMemo(() => sortedWorkflows(items ?? []), [items]);
  const table = useSettingsTable({
    rows: all,
    columns: WORKFLOW_COLUMNS,
    cellValues: workflowCellValues,
    searchTexts: workflowSearchTexts,
    initialSort: 'module',
  });
  const shown = table.shown;

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(
      WORKFLOW_EXPORT_HEADERS,
      shown.map(workflowExportRow),
      format,
      `workflows_${date}`,
      'Workflows'
    );
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Workflows"
        // One total: workflows and pipelines alike.
        badge={items ? `${all.length} workflow${all.length === 1 ? '' : 's'}` : undefined}
        description="The workflows and pipelines of this workspace's modules. Who runs each is decided by policies, on Roles & permissions."
        actions={<UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />}
      />

      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}

      {items === null ? (
        <SettingsLoading label="Loading workflows…" />
      ) : all.length === 0 ? (
        <SettingsEmpty
          icon={<Workflow size={40} className="opacity-40" />}
          title="No workflows in this workspace"
          description="The modules of this workspace run no workflow or pipeline."
        />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search workflows..."
            // No count above the search: the badge says how many, the pager how many are shown.
            meta={<SettingsTableClear table={table} />}
          />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={WORKFLOW_COLUMNS.length} noun="workflows" />}
                {table.paged.pageRows.map((item) => (
                  <tr key={workflowKey(item)} data-workflow={workflowKey(item)}>
                    <td className="align-top">
                      <p className="font-medium">{item.display_name}</p>
                      {item.description ? (
                        <p className="line-clamp-2 text-xs text-muted-foreground" title={item.description}>
                          {item.description}
                        </p>
                      ) : null}
                    </td>
                    <td>
                      <Badge variant={item.type === 'pipeline' ? 'warning' : 'primary'}>{item.type}</Badge>
                    </td>
                    <td className="truncate text-muted-foreground">
                      {/* Its row in Access › Modules, where the workspace offers it. */}
                      <ModuleLink workspaceId={workspaceId ?? ''} module={item.module_id} />
                    </td>
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
