'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { GraphHeader as Header } from '@/components/graph/graph-header';
import {IndividualsTable} from '@/components/graph/individuals-table';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import {
  AlertCircle,
  Box,
  ChevronRight,
  Circle,
  Loader2,
  RefreshCw,
  Search,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { BFO_BUCKET_DEFS } from '@/lib/bfo-buckets';
import { CheckboxFilter } from '@/components/graph/checkbox-filter';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { IndividualDetailPanel } from '@/components/graph/instance-detail-editor';
import { individualHref } from '@/lib/graph-instance-browser';

const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

interface ApiGraphInfo {
  id: string;
  uri: string;
  label: string;
  role_label: string;
  can_write?: boolean;
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
  domain_relations_count?: number;
  range_relations_count?: number;
  properties_count?: number;
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

function IndeterminateCheckbox({
  checked,
  indeterminate,
  onChange,
  className,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: () => void;
  className?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      onClick={(e) => e.stopPropagation()}
      className={cn('cursor-pointer rounded accent-workspace-accent', className)}
    />
  );
}

export default function IndividualsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const loadIcons = useOntologyIconsStore(state => state.load);
  useEffect(() => { void loadIcons(workspaceId); }, [workspaceId, loadIcons]);
  const preSelectedUri = searchParams?.get('selected') ?? null;
  const requestedGraph = searchParams?.get('graph') ?? null;
  const preSelectedClassUri = searchParams?.get('class') ?? null;
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
  // Search submitted on Enter. The /instances fetch reads this — typing alone
  // does not trigger a backend call.
  const [submittedSearch, setSubmittedSearch] = useState('');
  const SEARCH_MIN_CHARS = 2;
  const handleSubmitSearch = useCallback((raw: string) => {
    const trimmed = raw.trim();
    setSubmittedSearch(trimmed.length >= SEARCH_MIN_CHARS ? trimmed : '');
  }, []);
  const [instances, setInstances] = useState<ApiDiscoveryInstance[]>([]);
  const [instancesLoading, setInstancesLoading] = useState(false);
  const [instancesError, setInstancesError] = useState<string | null>(null);

  const [selectedIndividualUri, setSelectedIndividualUri] = useState<string | null>(null);
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [checkedUris, setCheckedUris] = useState<Set<string>>(new Set());

  const [instanceDetail, setInstanceDetail] = useState<InstanceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailRefreshTick, setDetailRefreshTick] = useState(0);
  const autoExpandedForRef = useRef<string | null>(null);
  const prevActiveGraphUriRef = useRef<string | null>(null);

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
    if (requestedGraph) return allGraphs.find(graph => graph.uri === requestedGraph) ?? null;
    if (selectedGraphId) {
      const match = allGraphs.find((g) => g.id === selectedGraphId);
      if (match) return match;
    }
    if (visibleGraphIds.length > 0) {
      const match = allGraphs.find((g) => visibleGraphIds.includes(g.id));
      if (match) return match;
    }
    return allGraphs.find((g) => !isSystemGraph(g)) ?? allGraphs[0] ?? null;
  }, [allGraphs, selectedGraphId, visibleGraphIds, requestedGraph]);

  useEffect(() => {
    if (requestedGraph && activeGraph && activeGraph.id !== selectedGraphId) selectGraph(activeGraph.id);
  }, [requestedGraph, activeGraph, selectedGraphId, selectGraph]);

  const bucketOptions = useMemo(
    () =>
      BFO_BUCKET_DEFS.filter((b) => b.uri).map((bucket) => ({
        uri: bucket.uri,
        label: bucket.label,
        hint: bucket.type,
      })),
    []
  );

  const allClassesSelected = useMemo(
    () =>
      classes.length > 0 &&
      selectedClassUris.length === classes.length &&
      classes.every((cls) => selectedClassUris.includes(cls.uri)),
    [classes, selectedClassUris],
  );

  // Show results only after the user submits a search (Enter, ≥ SEARCH_MIN_CHARS)
  // or ticks at least one class.
  const hasActiveFilter = submittedSearch.length > 0 || selectedClassUris.length > 0;

  const classUrisToFetch = useMemo(() => {
    if (!hasActiveFilter) return [];
    // All classes selected, or graph-wide search with no class filter
    if (allClassesSelected || (submittedSearch.length > 0 && selectedClassUris.length === 0)) {
      return [];
    }
    return selectedClassUris;
  }, [hasActiveFilter, allClassesSelected, submittedSearch, selectedClassUris]);

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

  // Pre-select individual from URL ?selected= param
  useEffect(() => {
    if (preSelectedUri) setSelectedIndividualUri(preSelectedUri);
  }, [preSelectedUri]);

  // Pre-select class from URL ?class= param (e.g. after creating an individual)
  useEffect(() => {
    if (!preSelectedClassUri) return;
    setSelectedClassUris((prev) =>
      prev.includes(preSelectedClassUri) ? prev : [...prev, preSelectedClassUri]
    );
  }, [preSelectedClassUri]);

  useEffect(() => {
    if (!activeGraph) {
      setClasses([]);
      return;
    }
    const graphChanged =
      prevActiveGraphUriRef.current !== null &&
      prevActiveGraphUriRef.current !== activeGraph.uri;
    prevActiveGraphUriRef.current = activeGraph.uri;
    if (graphChanged) {
      setExpandedClasses(new Set());
      setSelectedIndividualUri(preSelectedUri);
      setCheckedUris(new Set());
    }
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
            // Do not auto-select classes — user must explicitly filter
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
  }, [activeGraph, workspaceId, preSelectedUri]);

  useEffect(() => {
    if (!activeGraph || !hasActiveFilter) {
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
            class_uris: classUrisToFetch,
            property_uris: [RDFS_LABEL],
            search: submittedSearch,
          }),
        });
        if (!res.ok) throw new Error(`Search failed (${res.status})`);
        const data = (await res.json()) as ApiDiscoveryInstance[];
        if (!cancelled) {
          setInstances(data);
          setSelectedIndividualUri((prev) => {
            const target = preSelectedUri ?? prev;
            if (!target) return null;
            if (data.some((d) => d.uri === target)) return target;
            return preSelectedUri === target ? target : null;
          });
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
  }, [
    activeGraph,
    workspaceId,
    selectedClassUris,
    submittedSearch,
    hasActiveFilter,
    classUrisToFetch,
    preSelectedUri,
  ]);

  const filteredInstances = useMemo(() => {
    if (selectedBucketUris.length === 0) return [];
    const bucketSet = new Set(selectedBucketUris);
    return instances.filter((i) => !i.bfo_bucket_uri || bucketSet.has(i.bfo_bucket_uri));
  }, [instances, selectedBucketUris]);

  const checkedInstances = useMemo(
    () => filteredInstances.filter((i) => checkedUris.has(i.uri)),
    [filteredInstances, checkedUris]
  );

  const instancesByClass = useMemo(() => {
    const grouped = new Map<string, ApiDiscoveryInstance[]>();
    for (const inst of filteredInstances) {
      const cls = inst.class_label || compactUri(inst.class_uri) || 'Unknown';
      if (!grouped.has(cls)) grouped.set(cls, []);
      grouped.get(cls)!.push(inst);
    }
    return new Map([...grouped.entries()].sort((a, b) => a[0].localeCompare(b[0])));
  }, [filteredInstances]);

  const classSectionKeys = useMemo(
    () => [...instancesByClass.keys()].join('\0'),
    [instancesByClass],
  );

  const selectedClassesKey = selectedClassUris.join(',');
  // Auto-expand class sections when search or class filters are active
  useEffect(() => {
    if (!hasActiveFilter || !classSectionKeys) return;
    setExpandedClasses(new Set(classSectionKeys.split('\0')));
  }, [
    hasActiveFilter,
    classSectionKeys,
    submittedSearch,
    selectedClassesKey,
    allClassesSelected,
    activeGraph?.uri,
  ]);

  // Auto-expand the class section containing the pre-selected individual
  useEffect(() => {
    if (!selectedIndividualUri || autoExpandedForRef.current === selectedIndividualUri) return;
    for (const [cls, insts] of instancesByClass) {
      if (insts.some((i) => i.uri === selectedIndividualUri)) {
        autoExpandedForRef.current = selectedIndividualUri;
        setExpandedClasses((prev) => new Set(prev).add(cls));
        break;
      }
    }
  }, [instancesByClass, selectedIndividualUri]);

  const selectedInstance = useMemo(() => {
    if (!selectedIndividualUri) return null;
    const found = filteredInstances.find((i) => i.uri === selectedIndividualUri);
    if (found) return found;
    if (instanceDetail?.uri === selectedIndividualUri) {
      return {
        uri: instanceDetail.uri,
        label: instanceDetail.label,
        class_uri: instanceDetail.class_uri,
        class_label: instanceDetail.class_label,
        properties: {},
      } satisfies ApiDiscoveryInstance;
    }
    return {
      uri: selectedIndividualUri,
      label: compactUri(selectedIndividualUri),
      class_uri: preSelectedClassUri ?? '',
      class_label: '',
      properties: {},
    } satisfies ApiDiscoveryInstance;
  }, [filteredInstances, selectedIndividualUri, instanceDetail, preSelectedClassUri]);

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
  }, [activeGraph, workspaceId, selectedIndividualUri, detailRefreshTick]);

  const handlePropertyDeleted = useCallback(() => {
    setDetailRefreshTick((t) => t + 1);
  }, []);

  const handleIndividualDeleted = useCallback(() => {
    if (selectedIndividualUri) {
      setCheckedUris((prev) => {
        const next = new Set(prev);
        next.delete(selectedIndividualUri);
        return next;
      });
    }
    setInstances((prev) => prev.filter((i) => i.uri !== selectedIndividualUri));
    setSelectedIndividualUri(null);
  }, [selectedIndividualUri]);

  const handleBatchDeleted = useCallback((deletedUris: string[]) => {
    const deletedSet = new Set(deletedUris);
    setInstances((prev) => prev.filter((i) => !deletedSet.has(i.uri)));
    setCheckedUris((prev) => {
      const next = new Set(prev);
      for (const uri of deletedUris) next.delete(uri);
      return next;
    });
    setSelectedIndividualUri((prev) => (prev && deletedSet.has(prev) ? null : prev));
  }, []);

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

  const toggleChecked = (uri: string) => {
    setCheckedUris((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  };

  const toggleClassChecked = (classInstances: ApiDiscoveryInstance[]) => {
    const uris = classInstances.map((i) => i.uri);
    const allInChecked = uris.every((u) => checkedUris.has(u));
    setCheckedUris((prev) => {
      const next = new Set(prev);
      if (allInChecked) uris.forEach((u) => next.delete(u));
      else uris.forEach((u) => next.add(u));
      return next;
    });
  };

  const toggleAllFiltered = () => {
    const allChecked =
      filteredInstances.length > 0 && filteredInstances.every((i) => checkedUris.has(i.uri));
    if (allChecked) {
      setCheckedUris(new Set());
    } else {
      setCheckedUris(new Set(filteredInstances.map((i) => i.uri)));
    }
  };

  const handleGraphChange = (graph: ApiGraphInfo) => {
    selectGraph(graph.id);
    const query = new URLSearchParams(searchParams.toString());
    query.set('graph', graph.uri);
    query.delete('selected');
    query.delete('class');
    setSelectedClassUris([]);
    router.replace(`/workspace/${workspaceId}/graph/individuals?${query}`, { scroll: false });
  };

  const allFilteredChecked =
    filteredInstances.length > 0 && filteredInstances.every((i) => checkedUris.has(i.uri));
  const someFilteredChecked =
    !allFilteredChecked && filteredInstances.some((i) => checkedUris.has(i.uri));

  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someFilteredChecked;
  }, [someFilteredChecked]);

  const openCreateIndividual = () => {
    router.push(`/workspace/${workspaceId}/graph/create-individual`);
  };

  return (
    <div className="flex h-full flex-col">
      <Header title="Individuals" />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">

          <div className="flex min-h-0 flex-1 overflow-hidden bg-card">
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
                {/* Left panel */}
                <div className="flex w-[30rem] shrink-0 flex-col border-r bg-muted/20">
                  <div className="border-b p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Users size={18} className="text-orange-500 dark:text-orange-400" />
                      <h2 className="font-semibold">Individuals</h2>
                      {hasActiveFilter && (
                        <span className="text-xs text-muted-foreground">
                          ({filteredInstances.length.toLocaleString()})
                        </span>
                      )}
                      {hasActiveFilter && filteredInstances.length > 0 && (
                        <div className="ml-auto flex items-center gap-1.5">
                          <input
                            ref={selectAllRef}
                            type="checkbox"
                            checked={allFilteredChecked}
                            onChange={toggleAllFiltered}
                            className="h-4 w-4 cursor-pointer rounded accent-workspace-accent"
                            title="Select all visible individuals"
                          />
                          {checkedUris.size > 0 && (
                            <span className="text-xs text-muted-foreground">
                              {checkedUris.size} selected
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="relative mb-3">
                      <Search
                        size={14}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                      />
                      <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleSubmitSearch(search);
                          }
                        }}
                        placeholder="Search individuals — press Enter"
                        className="w-full rounded-md border bg-background py-1.5 pl-8 pr-8 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                      {(search || submittedSearch) && (
                        <button
                          type="button"
                          onClick={() => {
                            setSearch('');
                            handleSubmitSearch('');
                          }}
                          title="Clear search"
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
                        emptyMessage="No classes found."
                        emptySummary="Select a class"
                      />
                    </div>
                  </div>

                  {instancesError && (
                    <div className="border-b bg-destructive/10 px-4 py-2 text-xs text-destructive">
                      {instancesError}
                    </div>
                  )}

                  <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
                    {!hasActiveFilter ? (
                      <p className="px-2 py-8 text-center text-sm text-muted-foreground">
                        Type a search and press Enter, or select one or more classes (use
                        Select all) to display results.
                      </p>
                    ) : instancesLoading && filteredInstances.length === 0 ? (
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
                        const classAllChecked = classInstances.every((i) =>
                          checkedUris.has(i.uri)
                        );
                        const classSomeChecked =
                          !classAllChecked && classInstances.some((i) => checkedUris.has(i.uri));
                        const sorted = [...classInstances].sort((a, b) =>
                          instanceLabel(a).localeCompare(instanceLabel(b), undefined, {
                            sensitivity: 'base',
                          })
                        );
                        return (
                          <div key={cls}>
                            <div className="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-sm hover:bg-background">
                              <IndeterminateCheckbox
                                checked={classAllChecked}
                                indeterminate={classSomeChecked}
                                onChange={() => toggleClassChecked(classInstances)}
                                className="h-3.5 w-3.5 shrink-0"
                              />
                              <button
                                type="button"
                                onClick={() => toggleClassSection(cls)}
                                className="flex flex-1 items-center gap-1 text-left"
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
                            </div>

                            {isExpanded &&
                              sorted.map((ind) => (
                                <div
                                  key={ind.uri}
                                  className={cn(
                                    'flex w-full items-center gap-2 rounded-md py-1 pl-7 pr-2 text-sm transition-colors',
                                    checkedUris.has(ind.uri)
                                      ? 'bg-orange-50/60 dark:bg-orange-900/10'
                                      : 'hover:bg-background'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checkedUris.has(ind.uri)}
                                    onChange={() => toggleChecked(ind.uri)}
                                    onClick={(e) => e.stopPropagation()}
                                    className="h-3.5 w-3.5 shrink-0 cursor-pointer rounded accent-workspace-accent"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => router.push(individualHref(workspaceId, activeGraph.uri, ind.class_uri, ind.uri))}
                                    title={ind.uri}
                                    className={cn(
                                      'flex flex-1 items-center gap-2 text-left',
                                      selectedIndividualUri === ind.uri
                                        ? 'text-workspace-accent'
                                        : ''
                                    )}
                                  >
                                    <Circle
                                      size={10}
                                      className="shrink-0 text-orange-500 dark:text-orange-400"
                                    />
                                    <span className="truncate">{instanceLabel(ind)}</span>
                                  </button>
                                </div>
                              ))}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Center panel */}
                <div className="flex flex-1 overflow-hidden">
                  {checkedInstances.length >= 2 ? (
                    <IndividualsTable
                      readOnly={activeGraph.can_write !== true}
                      instances={checkedInstances}
                      graphUri={activeGraph.uri}
                      workspaceId={workspaceId}
                      onDeleted={handleBatchDeleted}
                    />
                  ) : selectedInstance ? (
                    <IndividualDetailPanel
                readOnly={activeGraph.can_write !== true}
                      instance={selectedInstance}
                      detail={instanceDetail}
                      loading={detailLoading}
                      graphUri={activeGraph.uri}
                      workspaceId={workspaceId}
                      onPropertyDeleted={handlePropertyDeleted}
                      onIndividualDeleted={handleIndividualDeleted}
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
                        <p className="mb-6 max-w-md text-muted-foreground">
                          Select an individual from the left panel to view its data and object
                          properties, or create a new individual.
                        </p>
                        <div className="flex justify-center">
                          <button
                            type="button"
                            onClick={openCreateIndividual}
                            className={cn(
                              'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                              'hover:opacity-90'
                            )}
                          >
                            <UserPlus size={16} />
                            New Individual
                          </button>
                        </div>
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
