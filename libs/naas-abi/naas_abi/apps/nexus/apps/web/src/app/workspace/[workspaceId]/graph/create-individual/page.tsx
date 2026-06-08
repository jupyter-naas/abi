'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, Check, ChevronDown, GitBranch, Loader2, Tag, UserPlus, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { getBfoBucket } from '@/lib/bfo-buckets';
import { authFetch } from '@/stores/auth';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';

interface ApiGraphInfo {
  id: string;
  uri: string;
  label: string;
  role_label: string;
}

interface ApiGraphPack {
  role_label: string;
  graphs: ApiGraphInfo[];
}

interface ApiDiscoveryClass {
  uri: string;
  label: string;
  count: number;
}

interface ApiDiscoveryProperty {
  uri: string;
  label: string;
  kind: string;
}

interface ApiClassMeta {
  class_uri: string;
  class_label: string;
  bfo_parent_iri: string;
  bfo_parent_label: string;
}

interface CreatedIndividual {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, string>;
}

function isAdminGraph(graph: ApiGraphInfo): boolean {
  const role = (graph.role_label ?? '').trim().toLowerCase();
  if (role === 'admin') return true;
  const id = graph.id.trim().toLowerCase();
  const name = (graph.label ?? '').trim().toLowerCase();
  return (
    id === 'schema' ||
    id === 'nexus' ||
    id.endsWith('/schema') ||
    id.endsWith('/nexus') ||
    name === 'schema' ||
    name === 'nexus'
  );
}

function ClassPicker({
  value,
  options,
  disabled,
  onChange,
}: {
  value: string;
  options: ApiDiscoveryClass[];
  disabled?: boolean;
  onChange: (classUri: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number; width: number } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const selectedClass = useMemo(
    () => options.find((c) => c.uri === value) ?? null,
    [options, value],
  );

  useEffect(() => {
    if (open) {
      setQuery('');
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setPopoverPos(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const reposition = () => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (c) => c.label.toLowerCase().includes(q) || c.uri.toLowerCase().includes(q),
    );
  }, [options, query]);

  const handlePick = (classUri: string) => {
    setOpen(false);
    if (classUri !== value) onChange(classUri);
  };

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          setOpen((v) => !v);
        }}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-background px-4 py-2 text-sm outline-none',
          'focus:ring-2 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <span className={cn('truncate text-left', !selectedClass && 'text-muted-foreground')}>
          {selectedClass ? `${selectedClass.label} (${selectedClass.count})` : 'Select a class'}
        </span>
        <ChevronDown size={16} className={cn('shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>

      {open && popoverPos && typeof document !== 'undefined' && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <div
            style={{ top: popoverPos.top, left: popoverPos.left, width: popoverPos.width }}
            className="fixed z-[9999] rounded-md border border-border bg-popover p-1 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (filtered.length > 0) handlePick(filtered[0].uri);
                } else if (e.key === 'Escape') {
                  setOpen(false);
                }
              }}
              placeholder="Search classes..."
              className="mb-1 w-full rounded border-0 bg-muted px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary/30"
            />
            <div className="max-h-60 overflow-y-auto">
              <button
                type="button"
                onClick={() => handlePick('')}
                className="flex w-full items-center justify-between gap-2 rounded px-3 py-2 text-left text-sm hover:bg-accent"
              >
                <span className="text-muted-foreground">Clear selection</span>
                {!value && <Check size={14} className="text-muted-foreground" />}
              </button>
              {filtered.map((cls) => {
                const isSelected = cls.uri === value;
                return (
                  <button
                    key={cls.uri}
                    type="button"
                    onClick={() => handlePick(cls.uri)}
                    title={cls.uri}
                    className="flex w-full items-center justify-between gap-2 rounded px-3 py-2 text-left text-sm hover:bg-accent"
                  >
                    <span className="truncate">
                      {cls.label}
                      <span className="ml-1 text-muted-foreground">({cls.count})</span>
                    </span>
                    {isSelected && <Check size={14} className="shrink-0 text-muted-foreground" />}
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="px-3 py-2 text-sm text-muted-foreground">No matching class</p>
              )}
            </div>
          </div>
        </>,
        document.body,
      )}
    </div>
  );
}

function BfoBucketMeta({ bfoParentIri, bfoParentLabel }: { bfoParentIri: string; bfoParentLabel: string }) {
  const bucket = getBfoBucket(bfoParentIri);
  if (!bfoParentIri && !bfoParentLabel) {
    return (
      <p className="text-xs text-muted-foreground">BFO bucket: not classified</p>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>BFO bucket:</span>
      {bucket ? (
        <span
          className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-medium text-foreground"
          style={{ borderColor: bucket.border, backgroundColor: `${bucket.color}18` }}
        >
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: bucket.color }} />
          {bucket.label}
          <span className="font-normal text-muted-foreground">({bucket.type})</span>
        </span>
      ) : (
        <span className="rounded-full border px-2 py-0.5 text-foreground">
          {bfoParentLabel || bfoParentIri}
        </span>
      )}
    </div>
  );
}

export default function CreateIndividualPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const { selectedGraphId, selectGraph, setVisibleGraphs } = useKnowledgeGraphStore();

  const [graphs, setGraphs] = useState<ApiGraphInfo[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [classes, setClasses] = useState<ApiDiscoveryClass[]>([]);
  const [classesLoading, setClassesLoading] = useState(true);
  const [classMeta, setClassMeta] = useState<ApiClassMeta | null>(null);
  const [classMetaLoading, setClassMetaLoading] = useState(false);
  const [datatypeProperties, setDatatypeProperties] = useState<ApiDiscoveryProperty[]>([]);
  const [propertiesLoading, setPropertiesLoading] = useState(false);

  const [label, setLabel] = useState('');
  const [classUri, setClassUri] = useState('');
  const [graphUri, setGraphUri] = useState('');
  const [propertyValues, setPropertyValues] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedIndividual | null>(null);

  const writableGraphs = useMemo(
    () => graphs.filter((g) => !isAdminGraph(g)),
    [graphs],
  );

  const loadGraphs = useCallback(async () => {
    setGraphsLoading(true);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) throw new Error(`Failed to load graphs (${res.status})`);
      const packs = (await res.json()) as ApiGraphPack[];
      const all: ApiGraphInfo[] = [];
      const seen = new Set<string>();
      for (const pack of Array.isArray(packs) ? packs : []) {
        for (const g of pack.graphs ?? []) {
          if (seen.has(g.uri)) continue;
          seen.add(g.uri);
          all.push(g);
        }
      }
      setGraphs(all);
    } catch {
      setGraphs([]);
    } finally {
      setGraphsLoading(false);
    }
  }, [workspaceId]);

  const loadClasses = useCallback(async () => {
    setClassesLoading(true);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/discovery/classes/all?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) throw new Error(`Failed to load classes (${res.status})`);
      const data = (await res.json()) as ApiDiscoveryClass[];
      setClasses(Array.isArray(data) ? data : []);
    } catch {
      setClasses([]);
    } finally {
      setClassesLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadGraphs();
    void loadClasses();
  }, [loadGraphs, loadClasses]);

  useEffect(() => {
    if (writableGraphs.length === 0) {
      setGraphUri('');
      return;
    }
    const preferred =
      writableGraphs.find((g) => g.id === selectedGraphId) ??
      writableGraphs[0];
    setGraphUri((prev) => {
      if (prev && writableGraphs.some((g) => g.uri === prev)) return prev;
      return preferred.uri;
    });
  }, [writableGraphs, selectedGraphId]);

  useEffect(() => {
    if (!classUri) {
      setClassMeta(null);
      setDatatypeProperties([]);
      setPropertyValues({});
      return;
    }
    let cancelled = false;
    (async () => {
      setClassMetaLoading(true);
      setPropertiesLoading(true);
      try {
        const params = new URLSearchParams({
          workspace_id: workspaceId,
          class_uri: classUri,
        });
        const [metaRes, propsRes] = await Promise.all([
          authFetch(`${getApiUrl()}/api/graph/discovery/class-meta?${params.toString()}`),
          authFetch(`${getApiUrl()}/api/graph/discovery/class-datatype-properties?${params.toString()}`),
        ]);
        if (!cancelled) {
          if (metaRes.ok) {
            setClassMeta((await metaRes.json()) as ApiClassMeta);
          } else {
            setClassMeta(null);
          }
          if (propsRes.ok) {
            const props = (await propsRes.json()) as ApiDiscoveryProperty[];
            setDatatypeProperties(Array.isArray(props) ? props : []);
          } else {
            setDatatypeProperties([]);
          }
          setPropertyValues({});
        }
      } catch {
        if (!cancelled) {
          setClassMeta(null);
          setDatatypeProperties([]);
          setPropertyValues({});
        }
      } finally {
        if (!cancelled) {
          setClassMetaLoading(false);
          setPropertiesLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, classUri]);

  const handleCancel = () => {
    router.push(`/workspace/${workspaceId}/graph/network`);
  };

  const resetForm = () => {
    setCreated(null);
    setLabel('');
    setClassUri('');
    setPropertyValues({});
  };

  const handleSubmit = async () => {
    const trimmedLabel = label.trim();
    if (!trimmedLabel || !graphUri) return;

    const properties = Object.fromEntries(
      Object.entries(propertyValues).filter(([, value]) => value.trim()),
    );

    setCreating(true);
    setError(null);
    try {
      const res = await authFetch(`${getApiUrl()}/api/graph/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          label: trimmedLabel,
          class_uri: classUri || null,
          properties,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        const message =
          typeof payload?.detail === 'string'
            ? payload.detail
            : `Failed to create individual (${res.status})`;
        throw new Error(message);
      }
      const data = (await res.json()) as CreatedIndividual;
      setCreated(data);
      const graph = writableGraphs.find((g) => g.uri === graphUri);
      if (graph) {
        selectGraph(graph.id);
        setVisibleGraphs([graph.id]);
      }
      window.dispatchEvent(new CustomEvent('graph-list-update'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create individual');
    } finally {
      setCreating(false);
    }
  };

  const openExplore = () => {
    router.push(`/workspace/${workspaceId}/graph/explore`);
  };

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 flex-col overflow-y-auto bg-card p-6">
        <div className="mx-auto w-full max-w-2xl">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <UserPlus size={24} className="text-workspace-accent" />
              <div>
                <h2 className="text-lg font-semibold">New Individual</h2>
                <p className="text-sm text-muted-foreground">
                  Add an OWL NamedIndividual with class-specific data properties.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleCancel}
              className="rounded p-2 text-muted-foreground hover:bg-muted"
              title="Close"
            >
              <X size={20} />
            </button>
          </div>

          {created ? (
            <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
              <p className="text-sm font-medium text-foreground">
                Individual &quot;{created.label}&quot; created successfully.
              </p>
              <p className="text-xs text-muted-foreground">
                Type: {created.type || 'owl:NamedIndividual'}
              </p>
              <p className="break-all text-xs text-muted-foreground">{created.id}</p>
              {created.properties && Object.keys(created.properties).length > 1 && (
                <div className="rounded border bg-background/60 p-3 text-xs">
                  <p className="mb-2 font-medium text-foreground">Properties</p>
                  <div className="space-y-1 text-muted-foreground">
                    {Object.entries(created.properties)
                      .filter(([key]) => key !== 'http://www.w3.org/2000/01/rdf-schema#label')
                      .map(([key, value]) => (
                        <div key={key} className="flex gap-2">
                          <span className="shrink-0 font-mono">{key.split(/[#/]/).pop()}:</span>
                          <span className="break-all">{value}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={resetForm}
                  className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Create another
                </button>
                <button
                  type="button"
                  onClick={openExplore}
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
                >
                  Open in Explore
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              <div>
                <label className="mb-2 block text-sm font-medium">Label *</label>
                <input
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="e.g., Acme Corporation"
                  className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">
                  Class
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    (aggregated across all graphs)
                  </span>
                </label>
                {classesLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" />
                    Loading classes...
                  </div>
                ) : (
                  <ClassPicker
                    value={classUri}
                    options={classes}
                    onChange={setClassUri}
                  />
                )}
                {classUri && (
                  <div className="mt-3 rounded-lg border bg-muted/20 px-4 py-3">
                    {classMetaLoading ? (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 size={12} className="animate-spin" />
                        Loading class metadata...
                      </div>
                    ) : (
                      <BfoBucketMeta
                        bfoParentIri={classMeta?.bfo_parent_iri ?? ''}
                        bfoParentLabel={classMeta?.bfo_parent_label ?? ''}
                      />
                    )}
                  </div>
                )}
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Graph *</label>
                {graphsLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" />
                    Loading graphs...
                  </div>
                ) : writableGraphs.length === 0 ? (
                  <p className="rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                    No writable graphs available. Admin graphs (schema, nexus) cannot be selected.
                  </p>
                ) : (
                  <select
                    value={graphUri}
                    onChange={(e) => setGraphUri(e.target.value)}
                    className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                  >
                    {writableGraphs.map((g) => (
                      <option key={g.uri} value={g.uri}>
                        {g.label}
                      </option>
                    ))}
                  </select>
                )}
                <p className="mt-2 text-xs text-muted-foreground">
                  Admin graphs are excluded from this list.
                </p>
              </div>

              <div className="rounded-lg border">
                <div className="flex items-center gap-2 border-b px-4 py-3">
                  <Tag size={16} className="text-workspace-accent" />
                  <span className="font-medium">Properties</span>
                </div>
                <div className="p-4">
                  {!classUri ? (
                    <p className="text-sm text-muted-foreground">
                      Select a class to see allowed data properties.
                    </p>
                  ) : propertiesLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 size={14} className="animate-spin" />
                      Loading properties for selected class...
                    </div>
                  ) : datatypeProperties.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No datatype properties declared for this class in the schema graph.
                    </p>
                  ) : (
                    <div className="space-y-4">
                      {datatypeProperties.map((prop) => (
                        <div key={prop.uri}>
                          <label className="mb-1.5 block text-sm font-medium">
                            {prop.label}
                            <span className="ml-2 text-xs font-normal text-muted-foreground">
                              {prop.kind}
                            </span>
                          </label>
                          <input
                            type="text"
                            value={propertyValues[prop.uri] ?? ''}
                            onChange={(e) =>
                              setPropertyValues((prev) => ({
                                ...prev,
                                [prop.uri]: e.target.value,
                              }))
                            }
                            placeholder={`Value for ${prop.label}`}
                            className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border">
                <div className="flex items-center gap-2 border-b px-4 py-3">
                  <GitBranch size={16} className="text-muted-foreground" />
                  <span className="font-medium">Relations</span>
                </div>
                <div className="p-4">
                  <p className="text-sm text-muted-foreground">
                    Object properties and OWL restrictions for the selected class are not available
                    yet. Relation editing will be added in a future release.
                  </p>
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleSubmit()}
                  disabled={!label.trim() || !graphUri || creating || graphsLoading}
                  className={cn(
                    'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                    'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                >
                  {creating ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} />}
                  Create Individual
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
