'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { RefreshCw } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { invalidateGraphExplorer } from '@/stores/graph-explorer';
import { useOntologyStore } from '@/stores/ontology';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsFilterSelect,
  SettingsTableToolbar,
  countLabel,
  SettingsSection,
  settingsTable,
} from '@/components/settings/settings-ui';

type Kind = 'ontologies' | 'graphs';
type Policy = {
  enabled?: string[];
  read?: string[];
  write?: string[];
  read_all?: boolean;
  include_owned?: boolean;
  allow_create?: boolean;
};
type Entry = {
  id: string;
  name: string;
  description: string;
  available: boolean;
  owned?: boolean;
  read_only?: boolean;
};
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
  const [search, setSearch] = useState('');
  const [accessFilter, setAccessFilter] = useState('all');
  const [availabilityFilter, setAvailabilityFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const pending = useRef<AbortController>();
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
        if (response.status === 403)
          throw new Error(
            'Only workspace owners and admins can manage assignments.',
          );
        if (response.status === 409)
          throw new Error(
            'Another admin saved changes. Reload the assignments before editing again.',
          );
        const payload = await response.json().catch(() => ({}));
        throw new Error(
          typeof payload.detail === 'string'
            ? payload.detail
            : 'Could not save or load assignments.',
        );
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
  const catalog = snapshot?.catalog || [];
  // Effective access of a row under the current (unsaved) draft.
  const accessOf = (item: Entry): 'enabled' | 'disabled' | 'edit' | 'read' | 'none' => {
    if (kind === 'ontologies') return draft.enabled?.includes(item.id) ? 'enabled' : 'disabled';
    const owned = !!draft.include_owned && !!item.owned;
    if (!item.read_only && (owned || draft.write?.includes(item.id))) return 'edit';
    if (draft.read_all || owned || draft.read?.includes(item.id)) return 'read';
    return 'none';
  };
  const rows = catalog.filter((item) => {
    if (accessFilter !== 'all' && accessOf(item) !== accessFilter) return false;
    if (availabilityFilter === 'available' && !item.available) return false;
    if (availabilityFilter === 'unavailable' && item.available) return false;
    return `${item.name} ${item.description}`.toLowerCase().includes(search.toLowerCase());
  });
  const enabledCount =
    kind === 'ontologies'
      ? (draft.enabled || []).length
      : catalog.filter((item) => accessOf(item) !== 'none').length;
  const editableCount = kind === 'graphs' ? catalog.filter((item) => accessOf(item) === 'edit').length : 0;
  const unavailableCount = catalog.filter((item) => !item.available).length;
  const noun = kind === 'ontologies' ? 'ontology' : 'graph';
  const meta = [
    countLabel(rows.length, catalog.length, noun, kind === 'ontologies' ? 'ontologies' : 'graphs'),
    kind === 'ontologies' ? `${enabledCount} enabled` : `${enabledCount} readable · ${editableCount} editable`,
    unavailableCount ? `${unavailableCount} unavailable` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const th = settingsTable.th;
  const checkCol = 'w-20 text-center';

  return (
    <section className="space-y-4" aria-busy={loading || saving}>
      <SettingsPageHeader
        title={title}
        badge={snapshot ? (kind === 'ontologies' ? `${enabledCount} enabled` : `${enabledCount} readable`) : undefined}
        description={
          kind === 'ontologies'
            ? 'Choose the ontologies available in this workspace.'
            : 'Choose the named graphs this workspace can read and edit.'
        }
        actions={
          <>
            <Button variant="secondary" onClick={() => void load()} disabled={loading || saving} title="Reload assignments">
              <RefreshCw size={14} /> Reload
            </Button>
            <Button onClick={() => void save()} disabled={!dirty || saving || loading}>
              {saving ? 'Saving…' : 'Save changes'}
            </Button>
          </>
        }
      />
      {error && (
        <SettingsNotice tone="error">
          <span role="alert">{error}</span>
        </SettingsNotice>
      )}
      {saved && (
        <SettingsNotice tone="success">
          <span role="status">Assignments saved.</span>
        </SettingsNotice>
      )}
      {loading ? (
        <SettingsLoading label={`Loading ${title.toLowerCase()}…`} />
      ) : (
        snapshot && (
          <>
            {kind === 'graphs' && (
              <SettingsSection title="Workspace access">
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
              </SettingsSection>
            )}
            <SettingsTableToolbar
              search={search}
              onSearchChange={setSearch}
              searchPlaceholder={`Search ${title.toLowerCase()}…`}
              filters={
                <>
                  <SettingsFilterSelect
                    label={kind === 'ontologies' ? 'Status' : 'Access'}
                    value={accessFilter}
                    onChange={setAccessFilter}
                    options={
                      kind === 'ontologies'
                        ? [
                            { value: 'all', label: 'All statuses' },
                            { value: 'enabled', label: 'Enabled' },
                            { value: 'disabled', label: 'Disabled' },
                          ]
                        : [
                            { value: 'all', label: 'All access' },
                            { value: 'edit', label: 'Read & edit' },
                            { value: 'read', label: 'Read only' },
                            { value: 'none', label: 'No access' },
                          ]
                    }
                  />
                  <SettingsFilterSelect
                    label="Availability"
                    value={availabilityFilter}
                    onChange={setAvailabilityFilter}
                    options={[
                      { value: 'all', label: 'All availability' },
                      { value: 'available', label: 'Available' },
                      { value: 'unavailable', label: 'Unavailable' },
                    ]}
                  />
                </>
              }
              meta={meta}
            />
            <div className={settingsTable.wrapper}>
              <table className={settingsTable.table}>
                <thead>
                  <tr className={settingsTable.headRow}>
                    <th className={th}>{kind === 'ontologies' ? 'Ontology' : 'Named graph'}</th>
                    <th className={cn(th, checkCol)}>{kind === 'ontologies' ? 'Enabled' : 'Read'}</th>
                    {kind === 'graphs' && <th className={cn(th, checkCol)}>Edit</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((item) => {
                    const owned = !!draft.include_owned && !!item.owned;
                    const readable =
                      !!draft.read_all ||
                      owned ||
                      !!draft.read?.includes(item.id) ||
                      !!draft.write?.includes(item.id);
                    return (
                      <tr key={item.id} className={settingsTable.row}>
                        <td className={settingsTable.td}>
                          <p className="break-words font-medium">{item.name}</p>
                          <p className="break-words text-xs text-muted-foreground">{item.description}</p>
                          {!item.available && (
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                              Unavailable · remove the assignment if no longer needed
                            </p>
                          )}
                        </td>
                        {kind === 'ontologies' ? (
                          <td className={cn(settingsTable.td, checkCol)}>
                            <Checkbox
                              aria-label={`Enable ${item.name}`}
                              checked={!!draft.enabled?.includes(item.id)}
                              disabled={saving}
                              onCheckedChange={(checked) => toggleOntology(item.id, checked)}
                            />
                          </td>
                        ) : (
                          <>
                            <td className={cn(settingsTable.td, checkCol)}>
                              <Checkbox
                                aria-label={`Read ${item.name}`}
                                title={
                                  draft.read_all
                                    ? 'Included by Read all graphs'
                                    : owned
                                      ? 'Included as a workspace-owned graph'
                                      : undefined
                                }
                                checked={readable}
                                disabled={saving || !!draft.read_all || owned}
                                onCheckedChange={(checked) => toggleGraph(item.id, 'read', checked)}
                              />
                            </td>
                            <td className={cn(settingsTable.td, checkCol)}>
                              <Checkbox
                                aria-label={`Edit ${item.name}`}
                                title={
                                  item.read_only
                                    ? 'The schema graph is read-only'
                                    : owned
                                      ? 'Included as a workspace-owned graph'
                                      : undefined
                                }
                                checked={!item.read_only && (owned || !!draft.write?.includes(item.id))}
                                disabled={saving || item.read_only || owned}
                                onCheckedChange={(checked) => toggleGraph(item.id, 'write', checked)}
                              />
                            </td>
                          </>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {rows.length === 0 && (
                <p className="p-6 text-center text-sm text-muted-foreground">
                  {catalog.length ? 'No resources match the current search and filters.' : 'No resources available.'}
                </p>
              )}
            </div>
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
