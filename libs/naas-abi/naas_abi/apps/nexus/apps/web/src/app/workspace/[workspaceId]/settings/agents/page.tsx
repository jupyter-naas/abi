'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, User, Cpu, Plus, Pencil, Trash2, Brain, Sparkles, Zap, Target, Search, CheckCircle, XCircle, Server } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getLogoUrl } from '@/lib/logo-url';
import { useIntegrationsStore } from '@/stores/integrations';
import { SETTINGS_RECONCILE_MS, ensureAgentsSynced, useAgentsStore, type Agent } from '@/stores/agents';
import { useModelsStore, modelDisplayName } from '@/stores/models';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Textarea } from '@/components/ui/input';
import { useSettingsReloadGeneration } from '@/components/settings/settings-reload';
import { usePageState } from '@/hooks/use-page-state';
import {
  SettingsEmpty,
  SettingsField,
  SettingsLoading,
  SettingsPageHeader,
  SettingsSection,
  SettingsTableToolbar,
  countLabel,
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
import type { ColumnFilterState } from '@/lib/graph-query/filters';
import {
  AGENT_COLUMNS,
  AGENT_EXPORT_HEADERS,
  agentCellValues,
  agentExportRow,
  agentModule,
  agentRows,
  agentSearchTexts,
  noModelLabel,
  type AgentColumnId,
} from './agents-model';

const iconMap = {
  bot: Bot,
  user: User,
  cpu: Cpu,
  brain: Brain,
  sparkles: Sparkles,
  zap: Zap,
  target: Target,
  search: Search,
};

const iconOptions: Agent['icon'][] = ['user', 'bot', 'cpu', 'brain', 'sparkles', 'zap', 'target', 'search'];

const NEW_AGENT = {
  name: '',
  description: '',
  icon: 'sparkles' as Agent['icon'],
  systemPrompt: 'You are a helpful AI assistant.',
  providerId: null as string | null,
};

function AgentAvatar({ agent, size = 18 }: { agent: Agent; size?: number }) {
  if (agent.logoUrl) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={getLogoUrl(agent.logoUrl)} alt={agent.name} className="h-full w-full object-cover" />;
  }
  const Icon = iconMap[agent.icon] || Sparkles;
  return <Icon size={size} />;
}

export default function AgentsPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const [mounted, setMounted] = useState(false);
  // Kept for a return to the page (lib/page-state.ts): the search, the filters and an unsaved new agent.
  const pageKey = workspaceId ? { scope: `workspace:${workspaceId}`, page: 'agents' } : null;
  const [showAddForm, setShowAddForm] = usePageState(pageKey && { ...pageKey, detail: 'add-form' }, false);
  const [keptSearch, setKeptSearch] = usePageState(pageKey && { ...pageKey, detail: 'search' }, '');
  const [keptFilters, setKeptFilters] = usePageState<Partial<Record<AgentColumnId, ColumnFilterState>>>(
    pageKey && { ...pageKey, detail: 'filters' },
    {}
  );
  const [newAgent, setNewAgent] = usePageState(pageKey && { ...pageKey, detail: 'new-agent' }, NEW_AGENT);
  // Reload reads the roster and the models again here, without remounting the page.
  const reloadGeneration = useSettingsReloadGeneration();

  const { providers } = useIntegrationsStore();
  const {
    agents,
    addAgent,
    deleteAgent,
    fetchAgents,
  } = useAgentsStore();
  const { models, fetchModels } = useModelsStore();
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();

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

  const handleAddAgent = () => {
    if (!newAgent.name.trim()) return;
    void addAgent({
      name: newAgent.name.trim(),
      description: newAgent.description.trim(),
      icon: newAgent.icon,
      systemPrompt: newAgent.systemPrompt,
      providerId: newAgent.providerId,
      provider: null,
      modelId: null,
      logoUrl: null,
      tools: ['search_knowledge', 'search_files', 'read_ontology'],
      capabilities: { memory: true, reasoning: false, vision: false },
      intentMappings: [],
    });
    setNewAgent(NEW_AGENT);
    setShowAddForm(false);
  };

  const handleOpenAgentEditor = (agentId: string) => {
    if (!workspaceId) return;
    router.push(`/workspace/${workspaceId}/settings/agents/${agentId}`);
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
            (id) => modelDisplayName(models, id) ?? id
          )
        : [],
    [mounted, agents, providers, models]
  );
  const table = useSettingsTable({
    rows,
    columns: AGENT_COLUMNS,
    cellValues: agentCellValues,
    searchTexts: agentSearchTexts,
    initialSort: 'agent',
  });

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
    return <SettingsLoading label="Loading agents…" />;
  }

  const resetNewAgent = () => {
    setShowAddForm(false);
    setNewAgent(NEW_AGENT);
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Agents"
        badge={`${rows.length} ${rows.length === 1 ? 'agent' : 'agents'}`}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/agents']}
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Add Agent
            </Button>
          </>
        }
      />

      {showAddForm && (
        <SettingsSection title="Add New Agent">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <SettingsField label="Name *">
                <Input
                  type="text"
                  value={newAgent.name}
                  onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                  placeholder="Agent name"
                />
              </SettingsField>
              <SettingsField label="Icon">
                <div className="flex gap-2">
                  {iconOptions.map((icon) => {
                    const IconComp = iconMap[icon];
                    return (
                      <Button
                        key={icon}
                        variant="secondary"
                        size="icon"
                        onClick={() => setNewAgent({ ...newAgent, icon })}
                        className={cn(
                          'h-9 w-9',
                          newAgent.icon === icon && 'border-primary bg-primary/10 text-primary hover:bg-primary/10'
                        )}
                      >
                        <IconComp size={16} />
                      </Button>
                    );
                  })}
                </div>
              </SettingsField>
            </div>
            <SettingsField label="Description">
              <Input
                type="text"
                value={newAgent.description}
                onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                placeholder="Brief description"
              />
            </SettingsField>
            <SettingsField label="System Prompt">
              <Textarea
                value={newAgent.systemPrompt}
                onChange={(e) => setNewAgent({ ...newAgent, systemPrompt: e.target.value })}
                placeholder="You are a helpful AI assistant..."
                rows={3}
                className="resize-none"
              />
            </SettingsField>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={resetNewAgent}>
                Cancel
              </Button>
              <Button onClick={handleAddAgent} disabled={!newAgent.name.trim()}>
                Add Agent
              </Button>
            </div>
          </div>
        </SettingsSection>
      )}

      {rows.length === 0 ? (
        <SettingsEmpty
          icon={<Bot size={40} className="opacity-40" />}
          title="No agents configured"
          description="Use Add Agent at the top right to create your first agent."
        />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search agents..."
            meta={
              <>
                {countLabel(table.shown.length, rows.length, 'agent')}
                <SettingsTableClear table={table} />
              </>
            }
          />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} trailing={<th aria-label="Actions" className="w-24" />} />
              <tbody>
                {table.shown.length === 0 && (
                  <SettingsTableNoMatch colSpan={AGENT_COLUMNS.length + 1} noun="agents" />
                )}
                {table.paged.pageRows.map(({ agent, models: agentModels }) => (
                  <tr
                    key={agent.id}
                    data-agent={agent.id}
                    onClick={() => handleOpenAgentEditor(agent.id)}
                    className="cursor-pointer"
                  >
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
                            <p className="pb-0.5 text-micro italic text-muted-foreground">{agentModule(agent)}</p>
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
                  </tr>
                ))}
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
