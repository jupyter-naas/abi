'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Workflow } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ModuleLink } from '@/components/settings/module-link';
import { SettingsPageHeader, SettingsTableToolbar } from '@/components/settings/settings-ui';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import { Notice } from '@/components/ui/notice';
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
  WORKFLOW_COLUMNS,
  WORKFLOW_EXPORT_HEADERS,
  fetchWorkflowSettings,
  workflowRows,
  workflowCellValues,
  workflowExportRow,
  workflowKey,
  workflowSearchTexts,
  type WorkflowSetting,
} from './workflows-model';

const WORKFLOW_KINDS: OfferKind[] = ['workflows', 'pipelines'];

/**
 * Workspace settings › Workflows: the workflows and pipelines of the workspace's modules, laid out
 * as Settings › Users (a search, columns that sort and filter, pages, an export). Every one the
 * modules bring is listed, enabled or not by the policy picked in the Settings column
 * (`?policy=`): a table of switches, each change saved at once and said, the rows selected
 * enabled or disabled together.
 */
export default function WorkflowsSettingsPage() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const policyId = policyOfSearch(useSearchParams());
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

  const catalog = useModuleItems({
    workspaceId,
    policyId,
    kinds: WORKFLOW_KINDS,
    // What the caller may run changed: the list is read again.
    onSaved: () => void load(),
  });

  // By module then name: rows that tie on the sorted column keep that order.
  const all = useMemo(() => workflowRows(items ?? [], catalog.items), [items, catalog.items]);
  const table = useSettingsTable({
    rows: all,
    columns: WORKFLOW_COLUMNS,
    cellValues: workflowCellValues,
    searchTexts: workflowSearchTexts,
    initialSort: 'module',
  });
  const shown = table.shown;
  // The rows shown, checked for a batch change (select all takes them).
  const selectable = useMemo(
    () => shown.flatMap((row) => (row.item ? [moduleItemKey(row.item)] : [])),
    [shown]
  );
  const selection = useRowSelection(selectable);
  const locked = !catalog.editable || catalog.saving;

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
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/workflows']}
        actions={<UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />}
      />

      {error && <Notice tone="error">{error}</Notice>}
      <ModuleItemsStatus state={catalog} />

      {items === null ? (
        <Loading label="Loading workflows…" />
      ) : all.length === 0 ? (
        <EmptyState framed
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
          <EnableBulkBar state={catalog} selection={selection} noun="workflow" />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={<SelectAllCell selection={selection} keys={selectable} noun="workflow" disabled={locked} />}
              />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={WORKFLOW_COLUMNS.length + 1} noun="workflows" />}
                {table.paged.pageRows.map((item) => (
                  <tr key={workflowKey(item)} data-workflow={workflowKey(item)}>
                    <SelectRowCell
                      selection={selection}
                      rowKey={item.item ? moduleItemKey(item.item) : workflowKey(item)}
                      label={item.display_name}
                      disabled={!item.item || locked}
                    />
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
                    <EnabledCell state={catalog} item={item.item ?? null} label={item.display_name} />
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
