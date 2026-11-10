'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Workflow } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import {
  SettingsEmpty,
  SettingsFilterSelect,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  countLabel,
  settingsTable,
} from '@/components/settings/settings-ui';
import {
  fetchWorkflowSettings,
  filterWorkflows,
  workflowKey,
  type WorkflowSetting,
} from './workflows-model';

/**
 * Workspace settings › Workflows: the workflows and pipelines of the workspace's modules,
 * read-only. Who may run each is decided by policies alone, on Roles & permissions: there is
 * no workspace on/off switch.
 */
export default function WorkflowsSettingsPage() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const [items, setItems] = useState<WorkflowSetting[] | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [type, setType] = useState('all');

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

  const all = useMemo(() => items ?? [], [items]);
  const shown = useMemo(() => filterWorkflows(all, { query, type }), [all, query, type]);

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Workflows"
        badge={items ? countLabel(all.length, all.length, 'item') : undefined}
        description="The workflows and pipelines of this workspace's modules. Who runs each is decided by policies, on Roles & permissions."
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
            search={query}
            onSearchChange={setQuery}
            searchPlaceholder="Search workflows..."
            filters={
              <SettingsFilterSelect
                label="Type"
                value={type}
                onChange={setType}
                options={[
                  { value: 'all', label: 'All types' },
                  { value: 'workflow', label: 'Workflows' },
                  { value: 'pipeline', label: 'Pipelines' },
                ]}
              />
            }
            meta={countLabel(shown.length, all.length, 'item')}
          />

          <div className={settingsTable.wrapper}>
            <table className={settingsTable.table}>
              <thead>
                <tr className={settingsTable.headRow}>
                  <th className={settingsTable.th}>Name</th>
                  <th className={settingsTable.th}>Type</th>
                  <th className={settingsTable.th}>Module</th>
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="p-8 text-center text-muted-foreground">
                      No workflows match the current search and filters
                    </td>
                  </tr>
                ) : (
                  shown.map((item) => (
                    <tr key={workflowKey(item)} className={settingsTable.row}>
                      <td className={cn(settingsTable.td, 'align-top')}>
                        <p className="font-medium">{item.display_name}</p>
                        {item.description ? (
                          <p className="line-clamp-2 text-xs text-muted-foreground" title={item.description}>
                            {item.description}
                          </p>
                        ) : null}
                      </td>
                      <td className={settingsTable.td}>
                        <Badge variant={item.type === 'pipeline' ? 'warning' : 'primary'}>{item.type}</Badge>
                      </td>
                      <td className={cn(settingsTable.td, 'truncate text-muted-foreground')}>{item.module_id}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
