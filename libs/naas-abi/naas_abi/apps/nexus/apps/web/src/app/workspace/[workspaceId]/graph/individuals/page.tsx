'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  Box,
  ChevronRight,
  Circle,
  Hash,
  Link2,
  Loader2,
  RefreshCw,
  Search,
  Users,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { BFO_BUCKET_DEFS } from '@/lib/bfo-buckets';
import { CheckboxFilter } from '@/components/graph/checkbox-filter';
import { GraphSectionNav } from '@/components/graph/graph-section-nav';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';

const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';
const SEARCH_DEBOUNCE_MS = 300;

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

interface ApiDiscoveryInstance {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  properties: Record<string, string>;
  bfo_bucket_uri?: string;
  bfo_bucket_label?: string;
}

interface InstanceDetail {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  data_properties: Array<{
    predicate_uri: string;
    predicate_label: string;
    value: string;
  }>;
  relations: Array<{
    role: 'domain' | 'range';
    predicate_uri: string;
    predicate_label: string;
    other_uri: string;
    other_label: string;
  }>;
}

function compactUri(uri: string): string {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

function isSystemGraph(graph: { id: string; label?: string }): boolean {
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

function instanceLabel(inst: ApiDiscoveryInstance): string {
  return inst.label || inst.properties[RDFS_LABEL] || compactUri(inst.uri);
}

function IndividualDetailPanel({
  instance,
  detail,
  loading,
}: {
  instance: ApiDiscoveryInstance;
  detail: InstanceDetail | null;
  loading: boolean;
}) {
  const dataProperties = detail?.data_properties ?? [];
  const objectProperties = useMemo(
    () =>
      (detail?.relations ?? [])
        .filter((r) => r.role === 'domain')
        .map((r) => ({
          predicate: r.predicate_label,
          targetId: r.other_uri,
          targetLabel: r.other_label || compactUri(r.other_uri),
        })),
    [detail]
  );

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mb-6">
        <div className="mb-2 flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-100 dark:bg-orange-900/30">
            <Circle size={20} className="text-orange-500" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold">{instanceLabel(instance)}</h2>
            <p className="truncate font-mono text-xs text-muted-foreground" title={instance.uri}>
              {instance.uri}
            </p>
          </div>
        </div>
        <div className="ml-13 flex items-center gap-2">
          <Box size={14} className="text-blue-500" />
          <span className="text-sm text-muted-foreground">
            {instance.class_label || compactUri(instance.class_uri)}
          </span>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading properties…
        </div>
      ) : (
        <>
          <div className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 font-medium">
              <Hash size={16} className="text-purple-500" />
              Data Properties
              <span className="text-xs text-muted-foreground">({dataProperties.length})</span>
            </h3>
            {dataProperties.length === 0 ? (
              <p className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
                No data properties.
              </p>
            ) : (
              <div className="overflow-hidden rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40">
                    <tr>
                      <th className="w-2/5 px-4 py-2 text-left font-medium text-muted-foreground">
                        Property
                      </th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataProperties.map((dp, i) => (
                      <tr key={`${dp.predicate_uri}-${i}`} className="border-t">
                        <td className="px-4 py-2 font-medium text-purple-600 dark:text-purple-400">
                          {dp.predicate_label}
                        </td>
                        <td className="break-all px-4 py-2 text-muted-foreground">{dp.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div>
            <h3 className="mb-3 flex items-center gap-2 font-medium">
              <Link2 size={16} className="text-green-500" />
              Object Properties
              <span className="text-xs text-muted-foreground">({objectProperties.length})</span>
            </h3>
            {objectProperties.length === 0 ? (
              <p className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
                No object properties.
              </p>
            ) : (
              <div className="overflow-hidden rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40">
                    <tr>
                      <th className="w-2/5 px-4 py-2 text-left font-medium text-muted-foreground">
                        Property
                      </th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {objectProperties.map((op, i) => (
                      <tr key={`${op.predicate}-${op.targetId}-${i}`} className="border-t">
                        <td className="px-4 py-2 font-medium text-green-600 dark:text-green-400">
                          {op.predicate}
                        </td>
                        <td className="px-4 py-2">
                          <span className="font-medium">{op.targetLabel}</span>
                          {op.targetLabel !== op.targetId && (
                            <span
                              className="mt-0.5 block truncate font-mono text-xs text-muted-foreground"
                              title={op.targetId}
                            >
                              {op.targetId}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function IndividualsPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const { selectedGraphId, visibleGraphIds, selectGraph } = useKnowledgeGraphStore();

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);

  const [classes, setClasses] = useState<ApiDiscoveryClass[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);
  const [selectedClassUris, setSelectedClassUris] = useState<string[]>([]);
  const lastSeededGraphUriRef = useRef<string | null>(null);

  const [selectedBucketUris, setSelectedBucketUris] = useState<string[]>(
    BFO_BUCKET_DEFS.filter((b) => b.uri).map((b) => b.uri)
  );

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [instances, setInstances] = useState<ApiDiscoveryInstance[]>([]);
  const [instancesLoading, setInstancesLoading] = useState(false);
  const [instancesError, setInstancesError] = useState<string | null>(null);

  const [selectedIndividualUri, setSelectedIndividualUri] = useState<string | null>(null);
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [didInitExpanded, setDidInitExpanded] = useState(false);

  const [instanceDetail, setInstanceDetail] = useState<InstanceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const allGraphs = useMemo<ApiGraphInfo[]>(() => {
    const seen = new Set<string>();
    const out: ApiGraphInfo[] = [];
    for (const pack of graphPacks) {
      for (const g of pack.graphs) {
        if (seen.has(g.uri)) continue;
        seen.add(g.uri);
        out.push(g);
      }
    }
    return out;
  }, [graphPacks]);

  const activeGraph = useMemo<ApiGraphInfo | null>(() => {
    if (selectedGraphId) {
      const match = allGraphs.find((g) => g.id === selectedGraphId);
      if (match) return match;
    }
    if (visibleGraphIds.length > 0) {
      const match = allGraphs.find((g) => visibleGraphIds.includes(g.id));
      if (match) return match;
    }
    return allGraphs.find((g) => !isSystemGraph(g)) ?? allGraphs[0] ?? null;
  }, [allGraphs, selectedGraphId, visibleGraphIds]);

  const bucketOptions = useMemo(
    () =>
      BFO_BUCKET_DEFS.filter((b) => b.uri).map((bucket) => ({
        uri: bucket.uri,
        label: bucket.label,
        hint: bucket.type,
      })),
    []
  );

  const loadGraphs = useCallback(async () => {
    setGraphsLoading(true);
    setGraphsError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!res.ok) throw new Error(`Failed to load graphs (${res.status})`);
      const data = (await res.json()) as ApiGraphPack[];
      setGraphPacks(Array.isArray(data) ? data : []);
    } catch (err) {
      setGraphsError(err instanceof Error ? err.message : 'Failed to load graphs');
      setGraphPacks([]);
    } finally {
      setGraphsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadGraphs();
  }, [loadGraphs]);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    if (!activeGraph) {
      setClasses([]);
      return;
    }
    setDidInitExpanded(false);
    setExpandedClasses(new Set());
    setSelectedIndividualUri(null);
    let cancelled = false;
    (async () => {
      setClassesLoading(true);
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/graph/discovery/classes?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as ApiDiscoveryClass[];
        if (!cancelled) {
          setClasses(data);
          if (lastSeededGraphUriRef.current !== activeGraph.uri) {
            lastSeededGraphUriRef.current = activeGraph.uri;
            setSelectedClassUris(data.map((c) => c.uri));
            setSelectedBucketUris(BFO_BUCKET_DEFS.filter((b) => b.uri).map((b) => b.uri));
          }
        }
      } catch {
        if (!cancelled) setClasses([]);
      } finally {
        if (!cancelled) setClassesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeGraph, workspaceId]);

  useEffect(() => {
    if (!activeGraph || selectedClassUris.length === 0) {
      setInstances([]);
      setInstancesLoading(false);
      setInstancesError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setInstancesLoading(true);
      setInstancesError(null);
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/discovery/instances`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            class_uris: selectedClassUris,
            property_uris: [RDFS_LABEL],
            search: debouncedSearch,
          }),
        });
        if (!res.ok) throw new Error(`Search failed (${res.status})`);
        const data = (await res.json()) as ApiDiscoveryInstance[];
        if (!cancelled) {
          setInstances(data);
          setSelectedIndividualUri((prev) =>
            prev && data.some((d) => d.uri === prev) ? prev : null
          );
        }
      } catch (err) {
        if (!cancelled) {
          setInstancesError(err instanceof Error ? err.message : 'Search failed');
          setInstances([]);
        }
      } finally {
        if (!cancelled) setInstancesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeGraph, workspaceId, selectedClassUris, debouncedSearch]);

  const filteredInstances = useMemo(() => {
    if (selectedBucketUris.length === 0) return [];
    const bucketSet = new Set(selectedBucketUris);
    return instances.filter((i) => !i.bfo_bucket_uri || bucketSet.has(i.bfo_bucket_uri));
  }, [instances, selectedBucketUris]);

  const instancesByClass = useMemo(() => {
    const grouped = new Map<string, ApiDiscoveryInstance[]>();
    for (const inst of filteredInstances) {
      const cls = inst.class_label || compactUri(inst.class_uri) || 'Unknown';
      if (!grouped.has(cls)) grouped.set(cls, []);
      grouped.get(cls)!.push(inst);
    }
    return new Map([...grouped.entries()].sort((a, b) => a[0].localeCompare(b[0])));
  }, [filteredInstances]);

  useEffect(() => {
    if (!didInitExpanded && instancesByClass.size > 0) {
      setExpandedClasses(new Set(instancesByClass.keys()));
      setDidInitExpanded(true);
    }
  }, [didInitExpanded, instancesByClass]);

  const selectedInstance = useMemo(
    () => filteredInstances.find((i) => i.uri === selectedIndividualUri) ?? null,
    [filteredInstances, selectedIndividualUri]
  );

  useEffect(() => {
    if (!activeGraph || !selectedIndividualUri) {
      setInstanceDetail(null);
      setDetailLoading(false);
      return;
    }
    let cancelled = false;
    setInstanceDetail(null);
    setDetailLoading(true);
    void authFetch(`${getApiUrl()}/api/graph/discovery/instance-detail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        graph_uri: activeGraph.uri,
        instance_uri: selectedIndividualUri,
      }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => {
        if (!cancelled) setInstanceDetail(data as InstanceDetail);
      })
      .catch(() => {
        if (!cancelled) setInstanceDetail(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeGraph, workspaceId, selectedIndividualUri]);

  const toggleClass = (uri: string) => {
    setSelectedClassUris((prev) =>
      prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
    );
  };

  const toggleBucket = (uri: string) => {
    setSelectedBucketUris((prev) =>
      prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
    );
  };

  const toggleClassSection = (cls: string) => {
    setExpandedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  };

  const handleGraphChange = (graph: ApiGraphInfo) => {
    selectGraph(graph.id);
  };

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <GraphSectionNav workspaceId={workspaceId} active="individuals" />

          <div className="flex flex-1 overflow-hidden bg-card">
            {graphsLoading ? (
              <div className="flex flex-1 items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : graphsError ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="mb-2 text-sm">{graphsError}</p>
                  <button
                    type="button"
                    onClick={() => void loadGraphs()}
                    className="mx-auto flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    <RefreshCw size={14} />
                    Retry
                  </button>
                </div>
              </div>
            ) : !activeGraph ? (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-sm text-muted-foreground">No graphs available in this workspace.</p>
              </div>
            ) : (
              <>
                <div className="flex w-80 shrink-0 flex-col border-r bg-muted/20">
                  <div className="border-b p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Users size={18} className="text-orange-500 dark:text-orange-400" />
                      <h2 className="font-semibold">Individuals</h2>
                      <span className="text-xs text-muted-foreground">
                        ({filteredInstances.length.toLocaleString()})
                      </span>
                    </div>

                    <div className="relative mb-3">
                      <Search
                        size={14}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                      />
                      <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search individuals..."
                        className="w-full rounded-md border bg-background py-1.5 pl-8 pr-8 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                      {search && (
                        <button
                          type="button"
                          onClick={() => setSearch('')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>

                    <div className="flex flex-col gap-2">
                      <div className="flex gap-2">
                        <div className="flex-1">
                          <CheckboxFilter
                            label="Graph"
                            loading={graphsLoading}
                            options={allGraphs.map((g) => ({
                              uri: g.uri,
                              label: g.label,
                              hint: g.role_label,
                            }))}
                            selected={activeGraph ? [activeGraph.uri] : []}
                            onToggle={(uri) => {
                              if (uri !== activeGraph?.uri) {
                                const g = allGraphs.find((gr) => gr.uri === uri);
                                if (g) handleGraphChange(g);
                              }
                            }}
                            onSetSelected={(uris) => {
                              const newUri = uris.find((u) => u !== activeGraph?.uri) ?? uris[0];
                              if (newUri) {
                                const g = allGraphs.find((gr) => gr.uri === newUri);
                                if (g) handleGraphChange(g);
                              }
                            }}
                            emptyMessage="No graphs available."
                          />
                        </div>
                        <div className="flex-1">
                          <CheckboxFilter
                            label="Buckets"
                            options={bucketOptions}
                            selected={selectedBucketUris}
                            onToggle={toggleBucket}
                            onSetSelected={setSelectedBucketUris}
                            emptyMessage="No buckets available."
                          />
                        </div>
                      </div>

                      <CheckboxFilter
                        label="Classes"
                        loading={classesLoading}
                        options={classes.map((cls) => ({
                          uri: cls.uri,
                          label: cls.label || compactUri(cls.uri),
                          hint: String(cls.count),
                        }))}
                        selected={selectedClassUris}
                        onToggle={toggleClass}
                        onSetSelected={setSelectedClassUris}
                        minSelected={1}
                        minSelectedWarning="Select at least one class to load individuals."
                        emptyMessage="No classes found."
                      />
                    </div>
                  </div>

                  {instancesError && (
                    <div className="border-b bg-destructive/10 px-4 py-2 text-xs text-destructive">
                      {instancesError}
                    </div>
                  )}

                  <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
                    {instancesLoading && filteredInstances.length === 0 ? (
                      <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
                        <Loader2 size={16} className="animate-spin" />
                        <span className="text-sm">Loading…</span>
                      </div>
                    ) : instancesByClass.size === 0 ? (
                      <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                        No individuals found.
                      </p>
                    ) : (
                      Array.from(instancesByClass.entries()).map(([cls, classInstances]) => {
                        const isExpanded = expandedClasses.has(cls);
                        const sorted = [...classInstances].sort((a, b) =>
                          instanceLabel(a).localeCompare(instanceLabel(b), undefined, {
                            sensitivity: 'base',
                          })
                        );
                        return (
                          <div key={cls}>
                            <button
                              type="button"
                              onClick={() => toggleClassSection(cls)}
                              className="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-left text-sm hover:bg-background"
                            >
                              <ChevronRight
                                size={14}
                                className={cn(
                                  'shrink-0 text-muted-foreground transition-transform',
                                  isExpanded && 'rotate-90'
                                )}
                              />
                              <Box size={14} className="shrink-0 text-blue-500" />
                              <span className="flex-1 truncate font-medium">{cls}</span>
                              <span className="text-xs text-muted-foreground">
                                {classInstances.length}
                              </span>
                            </button>

                            {isExpanded &&
                              sorted.map((ind) => (
                                <button
                                  key={ind.uri}
                                  type="button"
                                  onClick={() => setSelectedIndividualUri(ind.uri)}
                                  title={ind.uri}
                                  className={cn(
                                    'flex w-full items-center gap-2 rounded-md py-1 pl-8 pr-2 text-left text-sm transition-colors',
                                    selectedIndividualUri === ind.uri
                                      ? 'bg-workspace-accent-10 text-workspace-accent'
                                      : 'hover:bg-background'
                                  )}
                                >
                                  <Circle
                                    size={10}
                                    className="shrink-0 text-orange-500 dark:text-orange-400"
                                  />
                                  <span className="truncate">{instanceLabel(ind)}</span>
                                </button>
                              ))}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                <div className="flex flex-1 overflow-hidden">
                  {selectedInstance ? (
                    <IndividualDetailPanel
                      instance={selectedInstance}
                      detail={instanceDetail}
                      loading={detailLoading}
                    />
                  ) : (
                    <div className="flex flex-1 items-center justify-center">
                      <div className="text-center">
                        <div className="mb-4 flex justify-center">
                          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                            <Users size={32} className="text-orange-500 dark:text-orange-400" />
                          </div>
                        </div>
                        <h2 className="mb-2 text-lg font-semibold">Individuals</h2>
                        <p className="max-w-md text-muted-foreground">
                          Select an individual from the left panel to view its data and object
                          properties.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
