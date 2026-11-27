'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Plus, Pencil, Trash2, CheckCircle, XCircle, Server } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useIntegrationsStore } from '@/stores/integrations';
import { SETTINGS_RECONCILE_MS, ensureAgentsSynced, useAgentsStore } from '@/stores/agents';
import { useModelsStore, modelDisplayName } from '@/stores/models';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { useSettingsReloadGeneration } from '@/components/settings/settings-reload';
import { ModuleLink } from '@/components/settings/module-link';
import { usePageState } from '@/hooks/use-page-state';
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
import type { ColumnFilterState } from '@/lib/graph-query/filters';
import { SelectAllCell, SelectRowCell, useRowSelection } from '@/components/settings/bulk-access';
import { EnableBulkBar, EnabledCell, ModuleItemsStatus } from '@/components/settings/module-items';
import { moduleItemKey } from '@/components/settings/module-items-model';
import { policyOfSearch } from '@/components/settings/settings-policy';
import { useModuleItems } from '@/components/settings/use-module-items';
import type { OfferKind } from '@/lib/access-model/workspace-offer';
import {
  AGENT_COLUMNS,
  AGENT_EXPORT_HEADERS,
  agentCellValues,
  agentExportRow,
  agentModule,
  agentRows,
  agentSearchTexts,
  builtHere,
  noModelLabel,
  type AgentColumnId,
} from './agents-model';

import { AgentAvatar } from './agent-icons';
import { usePolicyHref } from '@/components/settings/use-policy-href';

const AGENT_KINDS: OfferKind[] = ['agents'];

export default function AgentsPage() {
  // Links keep the policy picked in the Settings column (`?policy=`).
  const policyHref = usePolicyHref();
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const [mounted, setMounted] = useState(false);
  // Kept for a return to the page (lib/page-state.ts): the search and the filters.
  const pageKey = workspaceId ? { scope: `workspace:${workspaceId}`, page: 'agents' } : null;
  const [keptSearch, setKeptSearch] = usePageState(pageKey && { ...pageKey, detail: 'search' }, '');
  const [keptFilters, setKeptFilters] = usePageState<Partial<Record<AgentColumnId, ColumnFilterState>>>(
    pageKey && { ...pageKey, detail: 'filters' },
    {}
  );
  // Reload reads the roster and the models again here, without remounting the page.
  const reloadGeneration = useSettingsReloadGeneration();

  const { providers } = useIntegrationsStore();
  const { agents, deleteAgent, fetchAgents } = useAgentsStore();
  const { models, fetchModels } = useModelsStore();
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();
  // Every agent the workspace's modules bring, enabled or not by the policy picked in the Settings
  // column (`?policy=`); a change is saved at once, then the roster is read again.
  const policyId = policyOfSearch(useSearchParams());
  const catalog = useModuleItems({
    workspaceId,
    policyId,
    kinds: AGENT_KINDS,
    generation: reloadGeneration,
    onSaved: () => void fetchAgents(workspaceId, false, { reread: true }),
  });

  // The roster, reconciled with the code's agents when the last reconciliation is older
  // than SETTINGS_RECONCILE_MS (or Reload was pressed), else as held.
  useEffect(() => {
    const loadAgents = async () => {
      try {
        if (!workspaceId) return;
        await ensureAgentsSynced(workspaceId, SETTINGS_RECONCILE_MS);
        await fetchAgents(workspaceId);
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      }
    };

    void loadAgents();
  }, [fetchAgents, workspaceId, reloadGeneration]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels, reloadGeneration]);

  const handleOpenAgentEditor = (agentId: string) => {
    if (!workspaceId) return;
    router.push(policyHref(`/workspace/${workspaceId}/settings/agents/${agentId}`));
  };

  const handleDeleteAgent = async (id: string) => {
    const ok = await confirmDelete({
      title: 'Delete agent?',
      description: 'Are you sure you want to delete this agent?',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (ok) deleteAgent(id);
  };

  // The rows, A to Z (rows that tie on the sorted column stay so), and the table over them.
  const rows = useMemo(
    () =>
      mounted
        ? agentRows(
            agents,
            providers.filter((p) => p.enabled),
            (id) => modelDisplayName(models, id) ?? id,
            catalog.items
          )
        : [],
    [mounted, agents, providers, models, catalog.items]
  );
  const table = useSettingsTable({
    rows,
    columns: AGENT_COLUMNS,
    cellValues: agentCellValues,
    searchTexts: agentSearchTexts,
    initialSort: 'agent',
  });
  // The module agents shown, checked for a batch change (select all takes the rows shown).
  const selectable = useMemo(
    () => table.shown.flatMap((row) => (row.item ? [moduleItemKey(row.item)] : [])),
    [table.shown]
  );
  const selection = useRowSelection(selectable);
  const locked = !catalog.editable || catalog.saving;

  // A return to the page finds the search and the filters again: restored once a workspace, then
  // kept.
  const restoredFor = useRef<string | null>(null);
  useEffect(() => {
    if (restoredFor.current !== workspaceId) {
      restoredFor.current = workspaceId;
      table.clear();
      table.setSearch(keptSearch);
      for (const column of AGENT_COLUMNS) {
        const state = keptFilters[column.id];
        if (state) table.setFilter(column.id, state);
      }
      return;
    }
    setKeptSearch(table.search);
    setKeptFilters(table.filters);
    // The kept values are read once; the table's state decides after.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, table.search, table.filters]);

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(AGENT_EXPORT_HEADERS, table.shown.map(agentExportRow), format, `agents_${date}`, 'Agents');
  };

  if (!mounted) {
    return <Loading label="Loading agents…" />;
  }

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Agents"
        badge={`${rows.length} ${rows.length === 1 ? 'agent' : 'agents'}`}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/agents']}
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
            {/* A page, as Create workspace: the agent's page opens once it is created. */}
            <Button onClick={() => router.push(policyHref(`/workspace/${workspaceId}/settings/agents/new`))} data-action="create">
              <Plus size={16} />
              Create agent
            </Button>
          </>
        }
      />

      <ModuleItemsStatus state={catalog} />

      {rows.length === 0 ? (
        <EmptyState framed
          icon={<Bot size={40} className="opacity-40" />}
          title="No agents configured"
          description="Use Create agent at the top right to create your first agent."
        />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search agents..."
            // No count above the search: the badge says how many, the pager how many are shown.
            meta={<SettingsTableClear table={table} />}
          />
          <EnableBulkBar state={catalog} selection={selection} noun="agent" />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={<SelectAllCell selection={selection} keys={selectable} noun="agent" disabled={locked} />}
                trailing={<th aria-label="Actions" className="w-24" />}
              />
              <tbody>
                {table.shown.length === 0 && (
                  <SettingsTableNoMatch colSpan={AGENT_COLUMNS.length + 2} noun="agents" />
                )}
                {table.paged.pageRows.map((row) => {
                  const { agent, models: agentModels, item } = row;
                  return (
                    <tr
                      key={row.key}
                      data-agent={row.key}
                      onClick={agent ? () => handleOpenAgentEditor(agent.id) : undefined}
                      className={agent ? 'cursor-pointer' : undefined}
                    >
                      <SelectRowCell
                        selection={selection}
                        rowKey={item ? moduleItemKey(item) : row.key}
                        label={row.name}
                        // An agent the workspace builds is always enabled: nothing to select.
                        disabled={!item || locked}
                      />
                      {!agent ? (
                        <>
                          {/* A module agent the roster does not hold: what the catalog says of it. */}
                          <td className="align-top">
                            <div className="flex min-h-[3.25rem] items-center gap-3">
                              <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden bg-muted">
                                <Bot size={18} />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="font-medium">{row.name}</p>
                                <p className="pb-0.5 text-micro italic text-muted-foreground">
                                  <ModuleLink workspaceId={workspaceId} module={row.module} />
                                </p>
                              </div>
                            </div>
                          </td>
                          <td data-field="models" />
                          <EnabledCell state={catalog} item={item} label={row.name} />
                          <td />
                        </>
                      ) : (
                        <>
                          <td className="align-top">
                            <div className="flex min-h-[3.25rem] items-center gap-3">
                              <div
                                className={cn(
                                  'flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden',
                                  agent.logoUrl ? 'bg-transparent' : 'bg-muted'
                                )}
                              >
                                <AgentAvatar agent={agent} />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="font-medium">{agent.name}</p>
                                {agent.class_name ? (
                                  <p className="pb-0.5 text-micro italic text-muted-foreground">
                                    <ModuleLink workspaceId={workspaceId} module={agentModule(agent)} />
                                  </p>
                                ) : null}
                                <p
                                  className="line-clamp-2 min-h-[2rem] text-xs text-muted-foreground"
                                  title={agent.description || undefined}
                                >
                                  {agent.description || '\u00A0'}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td data-field="models">
                            {agentModels.length === 0 ? (
                              <div className="flex items-center gap-2 text-muted-foreground">
                                <XCircle size={14} />
                                <span>{noModelLabel(agent)}</span>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-1">
                                {agentModels.map(({ id, label }) => (
                                  <div key={id} className="flex items-center gap-2">
                                    {agent.provider === 'abi' ? (
                                      <Server size={14} className="shrink-0 text-muted-foreground" />
                                    ) : (
                                      <CheckCircle size={14} className="shrink-0 text-primary" />
                                    )}
                                    <span className={cn(agent.provider === 'abi' && 'italic text-muted-foreground')} title={id}>
                                      {label}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                          <EnabledCell state={catalog} item={item} label={row.name} builtHere={builtHere(row)} />
                          <td className="whitespace-nowrap text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenAgentEditor(agent.id);
                                }}
                                title="Edit"
                              >
                                <Pencil size={14} />
                              </Button>
                              <Button
                                variant="destructive-ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteAgent(agent.id);
                                }}
                                title="Delete"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </div>
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <TablePager total={table.shown.length} paged={table.paged} />
        </div>
      )}
      {confirmDialog}
    </div>
  );
}
