'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { AlertCircle, CheckCircle2, Clock, Download, FileText, GitBranch, Loader2, RefreshCw, Tag, Users } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { GraphDevBanner } from '@/components/graph/graph-dev-banner';
import { useGraphExportStore } from '@/stores/graph-export';
import { KpiCard } from '@/app/analytics/components/kpi-card';
import {
  exportKpisFromRecord,
  EXPORT_FORMAT_LABELS,
  type ExportFormat,
  type ExportRecord,
  type ExportStatus,
} from '@/lib/graph-export-records';

const EMPTY_RECORDS: ExportRecord[] = [];

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

interface ApiGraphKpis {
  individuals: number;
  relations: number;
  properties: number;
  classes: number;
}

const FORMAT_META: Record<ExportFormat, { label: string; description: string; extension: string }> = {
  ttl: {
    label: 'Turtle',
    description: 'Human-readable RDF syntax. Compact and widely supported.',
    extension: '.ttl',
  },
  owl: {
    label: 'OWL',
    description: 'Web Ontology Language. Best for ontology tooling.',
    extension: '.owl',
  },
  nt: {
    label: 'N-Triples',
    description: 'Simple line-based format. Easy to parse programmatically.',
    extension: '.nt',
  },
};

function formatKpiCount(count?: number): string {
  if (count == null) return '—';
  return count.toLocaleString();
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function StatusBadge({ status, error }: { status: ExportStatus; error?: string }) {
  if (status === 'processing') {
    return (
      <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Loader2 size={13} className="animate-spin" />
        Processing
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span className="flex items-center gap-1.5 text-sm text-red-500" title={error}>
        <AlertCircle size={13} />
        Error
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-sm text-green-600">
      <CheckCircle2 size={13} />
      Ready
    </span>
  );
}

export default function ExportPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;

  const { selectedGraphId } = useKnowledgeGraphStore();
  const records = useGraphExportStore(
    (state) => state.recordsByWorkspace[workspaceId] ?? EMPTY_RECORDS,
  );
  const loadWorkspaceRecords = useGraphExportStore((state) => state.loadWorkspaceRecords);
  const setExportPageActive = useGraphExportStore((state) => state.setExportPageActive);
  const startExport = useGraphExportStore((state) => state.startExport);
  const downloadExport = useGraphExportStore((state) => state.downloadExport);

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('ttl');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [graphKpis, setGraphKpis] = useState<ApiGraphKpis | null>(null);
  const [kpisLoading, setKpisLoading] = useState(false);

  useEffect(() => {
    loadWorkspaceRecords(workspaceId);
  }, [workspaceId, loadWorkspaceRecords]);

  useEffect(() => {
    setExportPageActive(true);
    return () => setExportPageActive(false);
  }, [setExportPageActive]);

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
    return allGraphs[0] ?? null;
  }, [selectedGraphId, allGraphs]);

  const loadGraphs = useCallback(async () => {
    setGraphsLoading(true);
    setGraphsError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}&include_roles=true`
      );
      if (!res.ok) throw new Error(`Failed to load graphs (${res.status})`);
      const data = (await res.json()) as ApiGraphPack[];
      setGraphPacks(data);
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
    if (!activeGraph) {
      setGraphKpis(null);
      return;
    }

    let cancelled = false;
    setKpisLoading(true);
    void (async () => {
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/graph/kpis?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!res.ok) throw new Error(`Failed to load graph KPIs (${res.status})`);
        const data = (await res.json()) as ApiGraphKpis;
        if (!cancelled) setGraphKpis(data);
      } catch {
        if (!cancelled) setGraphKpis(null);
      } finally {
        if (!cancelled) setKpisLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [workspaceId, activeGraph]);

  const handleExport = useCallback(() => {
    if (!activeGraph) return;
    setDownloadError(null);
    startExport(
      workspaceId,
      { uri: activeGraph.uri, label: activeGraph.label || activeGraph.id },
      selectedFormat,
      graphKpis
        ? {
            individuals: graphKpis.individuals,
            relations: graphKpis.relations,
            properties: graphKpis.properties,
          }
        : undefined,
    );
  }, [activeGraph, selectedFormat, workspaceId, startExport, graphKpis]);

  const handleDownload = useCallback(async (record: ExportRecord) => {
    if (downloadingId) return;
    setDownloadingId(record.id);
    setDownloadError(null);
    try {
      await downloadExport(workspaceId, record);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Download failed';
      setDownloadError(msg);
    } finally {
      setDownloadingId(null);
    }
  }, [downloadingId, downloadExport, workspaceId]);

  const isExporting = useMemo(
    () => records.some((r) => r.status === 'processing'),
    [records]
  );

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <GraphDevBanner />
          <div className="flex-1 overflow-y-auto px-6 py-6">
            {graphsLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : graphsError ? (
              <div className="flex h-full items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="mb-2 text-sm">{graphsError}</p>
                  <button
                    onClick={() => void loadGraphs()}
                    className="mx-auto flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    <RefreshCw size={14} />
                    Retry
                  </button>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-5xl space-y-8">
                <div className="space-y-4">
                  <div>
                    <h2 className="text-base font-semibold">Export Graph</h2>
                    {activeGraph ? (
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        Exporting <span className="font-medium text-foreground">{activeGraph.label || activeGraph.id}</span>
                      </p>
                    ) : (
                      <p className="mt-0.5 text-sm text-muted-foreground">No graph selected</p>
                    )}
                  </div>

                  {activeGraph && (
                    <div className="grid grid-cols-3 gap-3">
                      {kpisLoading ? (
                        Array.from({ length: 3 }).map((_, i) => (
                          <div key={i} className="h-[110px] animate-pulse rounded border bg-muted/30" />
                        ))
                      ) : graphKpis ? (
                        <>
                          <KpiCard
                            label="Individuals"
                            value={graphKpis.individuals.toLocaleString()}
                            hint="Unique OWL NamedIndividuals in this graph"
                            icon={Users}
                          />
                          <KpiCard
                            label="Relations"
                            value={graphKpis.relations.toLocaleString()}
                            hint="Object property links between individuals"
                            icon={GitBranch}
                          />
                          <KpiCard
                            label="Properties"
                            value={graphKpis.properties.toLocaleString()}
                            hint="Literal data values attached to individuals"
                            icon={Tag}
                          />
                        </>
                      ) : null}
                    </div>
                  )}

                  <div className="grid grid-cols-3 gap-3">
                    {(Object.entries(FORMAT_META) as [ExportFormat, typeof FORMAT_META[ExportFormat]][]).map(
                      ([fmt, meta]) => (
                        <button
                          key={fmt}
                          type="button"
                          onClick={() => setSelectedFormat(fmt)}
                          className={cn(
                            'flex flex-col items-start rounded-lg border p-4 text-left transition-colors hover:bg-muted/50',
                            selectedFormat === fmt
                              ? 'border-foreground bg-muted/30'
                              : 'border-border'
                          )}
                        >
                          <div className="flex w-full items-center justify-between">
                            <span className="flex items-center gap-2 text-sm font-medium">
                              <FileText size={14} />
                              {meta.label}
                            </span>
                            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                              {meta.extension}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground">{meta.description}</p>
                        </button>
                      )
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleExport}
                    disabled={!activeGraph || isExporting}
                    className={cn(
                      'flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90',
                      (!activeGraph || isExporting) && 'cursor-not-allowed opacity-50'
                    )}
                  >
                    {isExporting ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        Exporting…
                      </>
                    ) : (
                      <>
                        <Download size={14} />
                        Export as {FORMAT_META[selectedFormat].extension}
                      </>
                    )}
                  </button>

                  <p className="text-xs text-muted-foreground">
                    Exports are prepared in the background. Download them from the history table below.
                    Files remain available for 7 days.
                  </p>
                </div>

                {downloadError && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
                    {downloadError}
                  </div>
                )}

                {records.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                      Export History
                    </h3>
                    <div className="overflow-hidden rounded-lg border">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-muted/30">
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Date</th>
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Graph</th>
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Format</th>
                            <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Individuals</th>
                            <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Relations</th>
                            <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Properties</th>
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Status</th>
                            <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Download</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {records.map((record) => {
                            const snapshot = exportKpisFromRecord(record);
                            return (
                            <tr key={record.id} className="hover:bg-muted/20">
                              <td className="px-4 py-3 text-muted-foreground">
                                <span className="flex items-center gap-1.5">
                                  <Clock size={12} />
                                  {formatDate(record.createdAt)}
                                </span>
                              </td>
                              <td className="px-4 py-3 font-medium">{record.graphLabel}</td>
                              <td className="px-4 py-3">{EXPORT_FORMAT_LABELS[record.format]}</td>
                              <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                                {formatKpiCount(snapshot?.individuals)}
                              </td>
                              <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                                {formatKpiCount(snapshot?.relations)}
                              </td>
                              <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                                {formatKpiCount(snapshot?.properties)}
                              </td>
                              <td className="px-4 py-3">
                                <StatusBadge status={record.status} error={record.error} />
                              </td>
                              <td className="px-4 py-3 text-right">
                                {record.status === 'ready' && (
                                  <button
                                    type="button"
                                    onClick={() => void handleDownload(record)}
                                    disabled={downloadingId === record.id}
                                    className={cn(
                                      'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-muted',
                                      downloadingId === record.id && 'cursor-not-allowed opacity-50'
                                    )}
                                    title={`Download ${record.graphLabel} (${EXPORT_FORMAT_LABELS[record.format]})`}
                                  >
                                    {downloadingId === record.id ? (
                                      <Loader2 size={12} className="animate-spin" />
                                    ) : (
                                      <Download size={12} />
                                    )}
                                    Download
                                  </button>
                                )}
                              </td>
                            </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
