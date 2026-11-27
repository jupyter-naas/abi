'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { invalidateGraphExplorer } from '@/stores/graph-explorer';
import { useOntologyStore } from '@/stores/ontology';
import { Checkbox } from '@/components/ui/checkbox';
import {
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  SettingsSection,
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
  BulkBar,
  SelectAllCell,
  SelectRowCell,
  onOffActions,
  useRowSelection,
  type BulkAction,
} from '@/components/settings/bulk-access';
import {
  GRAPH_LEVEL_LABELS,
  graphLevelFits,
  resourceCellValues,
  resourceColumns,
  resourceExportHeaders,
  resourceExportRow,
  resourceRows,
  resourceSearchTexts,
  withGraphLevel,
  withOntologies,
  type GraphLevel,
  type ResourceEntry as Entry,
  type ResourceKind as Kind,
  type ResourcePolicy as Policy,
} from './resource-access-model';

/** The batch actions on ontologies: enable or disable the rows selected. */
const ONTOLOGY_ACTIONS = onOffActions({ on: 'Enable', off: 'Disable' });
/** The batch actions on graphs: one level for the rows selected. */
const GRAPH_ACTIONS: BulkAction[] = (['read', 'edit', 'none'] as const).map((level) => ({
  id: level,
  label: GRAPH_LEVEL_LABELS[level],
  question: (count, plural) => `Give ${GRAPH_LEVEL_LABELS[level]} to ${count} ${plural}?`,
  detail: () => 'Their access changes in one save.',
  confirm: GRAPH_LEVEL_LABELS[level],
}));

type Snapshot = {
  data: Policy;
  revision: number;
  updated_by: string | null;
  catalog: Entry[];
};

export function ResourceAccessPage({ kind }: { kind: Kind }) {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  return (
    <ResourceAccessEditor
      key={`${workspaceId}:${kind}`}
      workspaceId={workspaceId}
      kind={kind}
    />
  );
}

/**
 * Settings › Ontologies and Settings › Graphs: what the workspace is given, a table of switches.
 * Each change (a row, an option) is saved at once with the revision read, and said; the rows
 * selected change together, asked first.
 */
export function ResourceAccessEditor({
  workspaceId,
  kind,
}: {
  workspaceId: string;
  kind: Kind;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const pending = useRef<AbortController | undefined>(undefined);
  const title = kind === 'ontologies' ? 'Ontologies' : 'Graphs';
  const noun = kind === 'ontologies' ? 'ontology' : 'graph';
  const plural = (count: number) => (count === 1 ? noun : kind === 'ontologies' ? 'ontologies' : 'graphs');
  const endpoint = `${getApiUrl()}/api/workspaces/${encodeURIComponent(workspaceId)}/resource-access/${kind}`;

  const request = useCallback(
    async (method: 'GET' | 'PUT', body?: object) => {
      pending.current?.abort();
      const controller = new AbortController();
      pending.current = controller;
      const response = await authFetch(endpoint, {
        method,
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        if (response.status === 409)
          throw new Error(
            'Another admin saved changes. Reload the assignments before editing again.',
          );
        const payload = await response.json().catch(() => ({}));
        const detail = typeof payload.detail === 'string' ? payload.detail : null;
        // A refusal that names what may not be assigned (an ontology, a graph) says so.
        if (response.status === 403)
          throw new Error(detail ?? 'Only workspace owners and admins can manage assignments.');
        throw new Error(detail ?? 'Could not save or load assignments.');
      }
      const data: Snapshot = await response.json();
      if (controller.signal.aborted)
        throw new DOMException('Aborted', 'AbortError');
      setSnapshot(data);
    },
    [endpoint],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      await request('GET');
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError'))
        setError(
          e instanceof Error ? e.message : 'Could not load assignments.',
        );
    } finally {
      setLoading(false);
    }
  }, [request]);
  useEffect(() => {
    void load();
    return () => pending.current?.abort();
  }, [load]);

  const policy: Policy = useMemo(() => snapshot?.data ?? {}, [snapshot]);

  /** One write of `next` at the revision read, then what it did said in `done`. */
  async function commit(next: Policy, done: string) {
    if (!snapshot) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await request('PUT', { revision: snapshot.revision, policy: next });
      invalidateGraphExplorer();
      window.dispatchEvent(new Event('graph-list-update'));
      useOntologyStore.setState((state) => ({
        items: [],
        graphRefreshTrigger: state.graphRefreshTrigger + 1,
      }));
      setNotice(done);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError'))
        setError(
          e instanceof Error ? e.message : 'Could not save assignments.',
        );
    } finally {
      setSaving(false);
    }
  }

  const changeOption = (changes: Partial<Policy>, done: string) => void commit({ ...policy, ...changes }, done);
  const catalog = useMemo(() => snapshot?.catalog || [], [snapshot]);
  const rows = useMemo(() => resourceRows(kind, catalog, policy), [kind, catalog, policy]);
  const nameOf = (id: string) => catalog.find((item) => item.id === id)?.name ?? id;
  const toggleOntology = (id: string, checked: boolean) =>
    void commit(withOntologies(policy, [id], checked), `${nameOf(id)} ${checked ? 'enabled' : 'disabled'}.`);
  /** Read unticked: no access; Edit ticked: read and edit; Edit unticked: read only. */
  const toggleGraph = (id: string, access: 'read' | 'write', checked: boolean) => {
    const level: GraphLevel = access === 'read' ? (checked ? 'read' : 'none') : checked ? 'edit' : 'read';
    void commit(withGraphLevel(policy, [id], level), `${nameOf(id)}: ${GRAPH_LEVEL_LABELS[level]}.`);
  };
  const columns = resourceColumns(kind);
  // 20 a page: the search and the filters reach every row, and a change of them goes back to
  // the first page (a checkbox ticked under a filter does not).
  const table = useSettingsTable({
    rows,
    columns,
    cellValues: resourceCellValues,
    searchTexts: resourceSearchTexts,
    initialSort: 'name',
  });
  const shown = table.shown;
  // One total: how many ontologies or graphs (the columns say which are enabled, read, edited).
  const total = `${catalog.length} ${plural(catalog.length)}`;
  // The rows checked for a batch change (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => shown.map((row) => row.id), [shown]));
  const selectedRows = () => rows.filter((row) => selection.selected.has(row.id));
  /** The selected rows an action fits (a graph read through "every graph" or owned: none). */
  const fitting = (id: string) =>
    kind === 'ontologies' ? selectedRows() : selectedRows().filter((row) => graphLevelFits(row, id as GraphLevel, policy));
  const applyBulk = async (id: string) => {
    const picked = fitting(id);
    if (kind === 'ontologies') {
      const on = id === 'on';
      const changed = picked.filter((row) => row.enabled !== on).length;
      await commit(
        withOntologies(policy, picked.map((row) => row.id), on),
        `${changed} ${plural(changed)} ${on ? 'enabled' : 'disabled'}.`,
      );
      return;
    }
    const level = id as GraphLevel;
    await commit(
      withGraphLevel(policy, picked.map((row) => row.id), level),
      `${picked.length} ${plural(picked.length)}: ${GRAPH_LEVEL_LABELS[level]}.`,
    );
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(
      resourceExportHeaders(kind),
      shown.map((row) => resourceExportRow(kind, row)),
      format,
      `${kind}_${date}`,
      title,
    );
  };

  return (
    <section className="space-y-4" aria-busy={loading || saving}>
      <SettingsPageHeader
        title={title}
        badge={snapshot ? total : undefined}
        description={
          kind === 'ontologies'
            ? 'Choose the ontologies available in this workspace.'
            : 'Choose the named graphs this workspace can read and edit.'
        }
        actions={<UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />}
      />
      {error && (
        <SettingsNotice tone="error">
          <span role="alert">{error}</span>
        </SettingsNotice>
      )}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-resource-notice="">
          {notice}
        </p>
      )}
      {loading ? (
        <SettingsLoading label={`Loading ${title.toLowerCase()}…`} />
      ) : (
        snapshot && (
          <>
            {kind === 'graphs' && (
              <SettingsSection title="Options">
                <fieldset className="flex flex-col gap-2.5" disabled={saving}>
                  <Checkbox
                    checked={!!policy.read_all}
                    onCheckedChange={(checked) =>
                      changeOption({ read_all: checked }, `Read all graphs: ${checked ? 'on' : 'off'}.`)
                    }
                    label="Read all graphs, including future graphs"
                  />
                  <Checkbox
                    checked={!!policy.include_owned}
                    onCheckedChange={(checked) =>
                      changeOption(
                        { include_owned: checked, allow_create: checked && policy.allow_create },
                        `Graphs created in this workspace: ${checked ? 'included' : 'excluded'}.`,
                      )
                    }
                    label="Include graphs created in this workspace"
                  />
                  <Checkbox
                    checked={!!policy.allow_create && !!policy.include_owned}
                    disabled={!policy.include_owned}
                    onCheckedChange={(checked) =>
                      changeOption({ allow_create: checked }, `Members ${checked ? 'may' : 'may not'} create graphs.`)
                    }
                    label="Allow members to create graphs"
                  />
                </fieldset>
              </SettingsSection>
            )}
            <SettingsTableToolbar
              search={table.search}
              onSearchChange={table.setSearch}
              searchPlaceholder={`Search ${title.toLowerCase()}…`}
              // No count above the search: the badge says how many, the pager how many are shown.
              meta={<SettingsTableClear table={table} />}
            />
            <BulkBar
              selection={selection}
              noun={noun}
              plural={plural(2)}
              actions={kind === 'ontologies' ? ONTOLOGY_ACTIONS : GRAPH_ACTIONS}
              onApply={applyBulk}
              skippedFor={(id) => selection.selected.size - fitting(id).length}
              change="this change"
              disabled={saving}
            />
            <div className="org-settings-users-table-wrap">
              <table className="org-settings-users-table">
                <SettingsTableHead
                  table={table}
                  leading={
                    <SelectAllCell
                      selection={selection}
                      keys={shown.map((row) => row.id)}
                      noun={noun}
                      disabled={saving}
                    />
                  }
                />
                <tbody>
                  {catalog.length === 0 ? (
                    <tr>
                      <td colSpan={columns.length + 1} className="org-settings-users-no-match">
                        No resources available.
                      </td>
                    </tr>
                  ) : (
                    shown.length === 0 && <SettingsTableNoMatch colSpan={columns.length + 1} noun={title.toLowerCase()} />
                  )}
                  {table.paged.pageRows.map((item) => {
                    const owned = item.ownedIncluded;
                    return (
                      <tr key={item.id} data-resource={item.id}>
                        <SelectRowCell selection={selection} rowKey={item.id} label={item.name} disabled={saving} />
                        <td>
                          <p className="break-words font-medium">{item.name}</p>
                          <p className="break-words text-xs text-muted-foreground">{item.description}</p>
                          {!item.available && (
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                              Unavailable · remove the assignment if no longer needed
                            </p>
                          )}
                        </td>
                        {kind === 'ontologies' ? (
                          <td>
                            <Checkbox
                              aria-label={`Enable ${item.name}`}
                              checked={item.enabled}
                              disabled={saving}
                              onCheckedChange={(checked) => toggleOntology(item.id, checked)}
                            />
                          </td>
                        ) : (
                          <>
                            <td>
                              <Checkbox
                                aria-label={`Read ${item.name}`}
                                title={
                                  policy.read_all
                                    ? 'Included by Read all graphs'
                                    : owned
                                      ? 'Included as a workspace-owned graph'
                                      : undefined
                                }
                                checked={item.readable}
                                disabled={saving || !!policy.read_all || owned}
                                onCheckedChange={(checked) => toggleGraph(item.id, 'read', checked)}
                              />
                            </td>
                            <td>
                              <Checkbox
                                aria-label={`Edit ${item.name}`}
                                title={
                                  item.read_only
                                    ? 'The schema graph is read-only'
                                    : owned
                                      ? 'Included as a workspace-owned graph'
                                      : undefined
                                }
                                checked={item.editable}
                                disabled={saving || item.read_only || owned}
                                onCheckedChange={(checked) => toggleGraph(item.id, 'write', checked)}
                              />
                            </td>
                          </>
                        )}
                        <td className={item.available ? 'text-muted-foreground' : 'text-amber-600 dark:text-amber-400'}>
                          {item.available ? 'Available' : 'Unavailable'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <TablePager total={shown.length} paged={table.paged} />
            <p className="text-xs leading-relaxed text-muted-foreground">
              {snapshot.updated_by
                ? 'Admin changes are saved for this workspace.'
                : 'Initial assignments come from configuration.'}{' '}
              Each change is saved at once. Configuration changes do not overwrite saved assignments.
              {kind === 'graphs' && ' Viewers retain read-only access.'}
            </p>
          </>
        )
      )}
    </section>
  );
}
