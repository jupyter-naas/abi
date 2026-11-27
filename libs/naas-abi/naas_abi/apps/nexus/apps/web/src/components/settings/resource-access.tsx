'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { invalidateGraphExplorer } from '@/stores/graph-explorer';
import { useOntologyStore } from '@/stores/ontology';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { SettingsPageHeader, SettingsTableToolbar, countLabel } from '@/components/settings/settings-ui';
import { Loading } from '@/components/ui/spinner';
import { Notice } from '@/components/ui/notice';
import { Card } from '@/components/ui/card';
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
  resourceCellValues,
  resourceColumns,
  resourceExportHeaders,
  resourceExportRow,
  resourceRows,
  resourceSearchTexts,
  type ResourceEntry as Entry,
  type ResourceKind as Kind,
  type ResourcePolicy as Policy,
} from './resource-access-model';

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

export function ResourceAccessEditor({
  workspaceId,
  kind,
}: {
  workspaceId: string;
  kind: Kind;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [draft, setDraft] = useState<Policy>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const pending = useRef<AbortController | undefined>(undefined);
  const title = kind === 'ontologies' ? 'Ontologies' : 'Graphs';
  const endpoint = `${getApiUrl()}/api/workspaces/${encodeURIComponent(workspaceId)}/resource-access/${kind}`;
  const dirty =
    snapshot !== null &&
    JSON.stringify(draft) !== JSON.stringify(snapshot.data);

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
      setDraft(data.data);
    },
    [endpoint],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    setSaved(false);
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

  async function save() {
    if (!snapshot) return;
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      await request('PUT', { revision: snapshot.revision, policy: draft });
      invalidateGraphExplorer();
      window.dispatchEvent(new Event('graph-list-update'));
      useOntologyStore.setState((state) => ({
        items: [],
        graphRefreshTrigger: state.graphRefreshTrigger + 1,
      }));
      setSaved(true);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError'))
        setError(
          e instanceof Error ? e.message : 'Could not save assignments.',
        );
    } finally {
      setSaving(false);
    }
  }

  function changeOptions(changes: Partial<Policy>) {
    setSaved(false);
    setDraft((current) => ({ ...current, ...changes }));
  }

  function toggleOntology(id: string, checked: boolean) {
    setSaved(false);
    setDraft((current) => ({
      ...current,
      enabled: checked
        ? [...(current.enabled || []), id]
        : (current.enabled || []).filter((ref) => ref !== id),
    }));
  }
  function toggleGraph(id: string, access: 'read' | 'write', checked: boolean) {
    setSaved(false);
    setDraft((current) => {
      const read = new Set(current.read),
        write = new Set(current.write);
      if (access === 'read') {
        if (checked) read.add(id);
        else {
          read.delete(id);
          write.delete(id);
        }
      } else if (checked) {
        read.add(id);
        write.add(id);
      } else write.delete(id);
      return { ...current, read: [...read], write: [...write] };
    });
  }
  const catalog = useMemo(() => snapshot?.catalog || [], [snapshot]);
  // Each row under the current (unsaved) draft: the filters read what the checkboxes show.
  const rows = useMemo(() => resourceRows(kind, catalog, draft), [kind, catalog, draft]);
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
  const enabledCount =
    kind === 'ontologies'
      ? (draft.enabled || []).length
      : rows.filter((row) => row.access !== 'none').length;
  const editableCount = kind === 'graphs' ? rows.filter((row) => row.access === 'edit').length : 0;
  const unavailableCount = catalog.filter((item) => !item.available).length;
  const noun = kind === 'ontologies' ? 'ontology' : 'graph';
  const meta = [
    countLabel(shown.length, catalog.length, noun, kind === 'ontologies' ? 'ontologies' : 'graphs'),
    kind === 'ontologies' ? `${enabledCount} enabled` : `${enabledCount} readable · ${editableCount} editable`,
    unavailableCount ? `${unavailableCount} unavailable` : null,
  ]
    .filter(Boolean)
    .join(' · ');

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
        badge={snapshot ? (kind === 'ontologies' ? `${enabledCount} enabled` : `${enabledCount} readable`) : undefined}
        description={
          kind === 'ontologies'
            ? WORKSPACE_PAGE_DESCRIPTIONS['/settings/ontologies']
            : WORKSPACE_PAGE_DESCRIPTIONS['/settings/graphs']
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />
            <Button onClick={() => void save()} disabled={!dirty || saving || loading}>
              {saving ? 'Saving…' : 'Save changes'}
            </Button>
          </>
        }
      />
      {error && (
        <Notice tone="error">
          <span role="alert">{error}</span>
        </Notice>
      )}
      {saved && (
        <Notice tone="success">
          <span role="status">Assignments saved.</span>
        </Notice>
      )}
      {loading ? (
        <Loading label={`Loading ${title.toLowerCase()}…`} />
      ) : (
        snapshot && (
          <>
            {kind === 'graphs' && (
              <Card title="Workspace access">
                <fieldset className="flex flex-col gap-2.5" disabled={saving}>
                  <Checkbox
                    checked={!!draft.read_all}
                    onCheckedChange={(checked) => changeOptions({ read_all: checked })}
                    label="Read all graphs, including future graphs"
                  />
                  <Checkbox
                    checked={!!draft.include_owned}
                    onCheckedChange={(checked) =>
                      changeOptions({
                        include_owned: checked,
                        allow_create: checked && draft.allow_create,
                      })
                    }
                    label="Include graphs created in this workspace"
                  />
                  <Checkbox
                    checked={!!draft.allow_create && !!draft.include_owned}
                    disabled={!draft.include_owned}
                    onCheckedChange={(checked) => changeOptions({ allow_create: checked })}
                    label="Allow members to create graphs"
                  />
                </fieldset>
              </Card>
            )}
            <SettingsTableToolbar
              search={table.search}
              onSearchChange={table.setSearch}
              searchPlaceholder={`Search ${title.toLowerCase()}…`}
              meta={
                <>
                  {meta}
                  <SettingsTableClear table={table} />
                </>
              }
            />
            <div className="org-settings-users-table-wrap">
              <table className="org-settings-users-table">
                <SettingsTableHead table={table} />
                <tbody>
                  {catalog.length === 0 ? (
                    <tr>
                      <td colSpan={columns.length} className="org-settings-users-no-match">
                        No resources available.
                      </td>
                    </tr>
                  ) : (
                    shown.length === 0 && <SettingsTableNoMatch colSpan={columns.length} noun={title.toLowerCase()} />
                  )}
                  {table.paged.pageRows.map((item) => {
                    const owned = item.ownedIncluded;
                    return (
                      <tr key={item.id} data-resource={item.id}>
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
                                  draft.read_all
                                    ? 'Included by Read all graphs'
                                    : owned
                                      ? 'Included as a workspace-owned graph'
                                      : undefined
                                }
                                checked={item.readable}
                                disabled={saving || !!draft.read_all || owned}
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
              Changes apply when saved. Configuration changes do not overwrite saved assignments.
              {kind === 'graphs' && ' Viewers retain read-only access.'}
            </p>
          </>
        )
      )}
    </section>
  );
}
