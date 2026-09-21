'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Search, RefreshCw } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { invalidateGraphExplorer } from '@/stores/graph-explorer';
import { useOntologyStore } from '@/stores/ontology';
import './resource-access.css';

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
  const rows = catalog.filter((item) =>
    `${item.name} ${item.description}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const enabledCount =
    kind === 'ontologies'
      ? (draft.enabled || []).length
      : catalog.filter(
          (item) =>
            draft.read_all ||
            (draft.include_owned && item.owned) ||
            draft.read?.includes(item.id) ||
            draft.write?.includes(item.id),
        ).length;

  return (
    <section className="resource-access" aria-busy={loading || saving}>
      <header className="resource-access-heading">
        <div>
          <h1>{title}</h1>
          <p>
            {kind === 'ontologies'
              ? 'Choose the ontologies available in this workspace.'
              : 'Choose the named graphs this workspace can read and edit.'}
          </p>
        </div>
        <div className="resource-access-actions">
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading || saving}
            title="Reload assignments"
          >
            <RefreshCw size={14} /> Reload
          </button>
          <button
            type="button"
            className="resource-access-save"
            onClick={() => void save()}
            disabled={!dirty || saving || loading}
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </header>
      {error && (
        <div className="resource-access-error" role="alert">
          {error}
        </div>
      )}
      {saved && <p role="status">Assignments saved.</p>}
      {loading ? (
        <p role="status">Loading {title.toLowerCase()}…</p>
      ) : (
        snapshot && (
          <>
            {kind === 'graphs' && (
              <fieldset className="resource-access-options" disabled={saving}>
                <legend>Workspace access</legend>
                <label>
                  <input
                    type="checkbox"
                    checked={!!draft.read_all}
                    onChange={(e) =>
                      changeOptions({ read_all: e.target.checked })
                    }
                  />{' '}
                  Read all graphs, including future graphs
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={!!draft.include_owned}
                    onChange={(e) =>
                      changeOptions({
                        include_owned: e.target.checked,
                        allow_create: e.target.checked && draft.allow_create,
                      })
                    }
                  />{' '}
                  Include graphs created in this workspace
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={!!draft.allow_create && !!draft.include_owned}
                    disabled={!draft.include_owned}
                    onChange={(e) =>
                      changeOptions({ allow_create: e.target.checked })
                    }
                  />{' '}
                  Allow members to create graphs
                </label>
              </fieldset>
            )}
            <div className="resource-access-toolbar">
              <label className="resource-access-search">
                <Search size={14} />
                <input
                  aria-label={`Search ${title.toLowerCase()}`}
                  placeholder={`Search ${title.toLowerCase()}…`}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <span>
                {enabledCount} enabled · {catalog.length} listed
              </span>
            </div>
            <div className="resource-access-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>
                      {kind === 'ontologies' ? 'Ontology' : 'Named graph'}
                    </th>
                    <th>{kind === 'ontologies' ? 'Enabled' : 'Read'}</th>
                    {kind === 'graphs' && <th>Edit</th>}
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
                      <tr key={item.id}>
                        <td>
                          <strong>{item.name}</strong>
                          <span>{item.description}</span>
                          {!item.available && (
                            <small>
                              Unavailable · remove the assignment if no longer
                              needed
                            </small>
                          )}
                        </td>
                        {kind === 'ontologies' ? (
                          <td>
                            <input
                              type="checkbox"
                              aria-label={`Enable ${item.name}`}
                              checked={!!draft.enabled?.includes(item.id)}
                              disabled={saving}
                              onChange={(e) =>
                                toggleOntology(item.id, e.target.checked)
                              }
                            />
                          </td>
                        ) : (
                          <>
                            <td>
                              <input
                                type="checkbox"
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
                                onChange={(e) =>
                                  toggleGraph(item.id, 'read', e.target.checked)
                                }
                              />
                            </td>
                            <td>
                              <input
                                type="checkbox"
                                aria-label={`Edit ${item.name}`}
                                title={
                                  item.read_only
                                    ? 'The schema graph is read-only'
                                    : owned
                                      ? 'Included as a workspace-owned graph'
                                      : undefined
                                }
                                checked={
                                  !item.read_only &&
                                  (owned || !!draft.write?.includes(item.id))
                                }
                                disabled={saving || item.read_only || owned}
                                onChange={(e) =>
                                  toggleGraph(
                                    item.id,
                                    'write',
                                    e.target.checked,
                                  )
                                }
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
                <p className="resource-access-empty">
                  {search
                    ? 'No matching resources.'
                    : 'No resources available.'}
                </p>
              )}
            </div>
            <p className="resource-access-note">
              {snapshot.updated_by
                ? 'Admin changes are saved for this workspace.'
                : 'Initial assignments come from configuration.'}{' '}
              Changes apply when saved. Configuration changes do not overwrite
              saved assignments.
              {kind === 'graphs' && ' Viewers retain read-only access.'}
            </p>
          </>
        )
      )}
    </section>
  );
}
