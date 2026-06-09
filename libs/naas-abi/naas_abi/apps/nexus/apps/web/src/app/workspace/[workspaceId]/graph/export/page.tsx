'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { AlertCircle, CheckCircle2, Clock, Download, FileText, Loader2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { GraphSectionNav } from '@/components/graph/graph-section-nav';
import { ToastStack, type ToastItem } from '@/components/graph/toast-notification';

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

type ExportFormat = 'ttl' | 'owl' | 'nt';
type ExportStatus = 'processing' | 'ready' | 'error';

interface ExportRecord {
  id: string;
  graphUri: string;
  graphLabel: string;
  workspaceId: string;
  format: ExportFormat;
  status: ExportStatus;
  createdAt: string;
  error?: string;
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

function storageKey(workspaceId: string) {
  return `graph-exports-${workspaceId}`;
}

function loadRecords(workspaceId: string): ExportRecord[] {
  try {
    const raw = localStorage.getItem(storageKey(workspaceId));
    if (!raw) return [];
    return JSON.parse(raw) as ExportRecord[];
  } catch {
    return [];
  }
}

function saveRecords(workspaceId: string, records: ExportRecord[]) {
  try {
    localStorage.setItem(storageKey(workspaceId), JSON.stringify(records));
  } catch {
    // ignore storage errors
  }
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

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('ttl');
  const [records, setRecords] = useState<ExportRecord[]>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const item: ToastItem = {
      ...toast,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    };
    setToasts((prev) => [...prev, item]);
  }, []);

  useEffect(() => {
    setRecords(loadRecords(workspaceId));
  }, [workspaceId]);

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

  async function triggerDownload(graph: ApiGraphInfo, format: ExportFormat): Promise<void> {
    const url = `${getApiUrl()}/api/graph/export?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(graph.uri)}&format=${format}`;
    const response = await authFetch(url);
    if (!response.ok) throw new Error(`Export failed (${response.status})`);
    const blob = await response.blob();
    const filename = `${graph.label || 'graph'}.${format}`;
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
  }

  const handleExport = useCallback(async () => {
    if (!activeGraph) return;
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const newRecord: ExportRecord = {
      id,
      graphUri: activeGraph.uri,
      graphLabel: activeGraph.label || activeGraph.id,
      workspaceId,
      format: selectedFormat,
      status: 'processing',
      createdAt: new Date().toISOString(),
    };
    const updated = [newRecord, ...records];
    setRecords(updated);
    saveRecords(workspaceId, updated);

    try {
      await triggerDownload(activeGraph, selectedFormat);
      setRecords((prev) => {
        const next = prev.map((r) => r.id === id ? { ...r, status: 'ready' as const } : r);
        saveRecords(workspaceId, next);
        return next;
      });
      pushToast({
        type: 'success',
        title: 'Export ready',
        message: `${activeGraph.label || activeGraph.id} exported as .${selectedFormat}`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setRecords((prev) => {
        const next = prev.map((r) => r.id === id ? { ...r, status: 'error' as const, error: msg } : r);
        saveRecords(workspaceId, next);
        return next;
      });
      pushToast({ type: 'error', title: 'Export failed', message: msg });
    }
  }, [activeGraph, selectedFormat, records, workspaceId, pushToast]);

  const handleRedownload = useCallback(async (record: ExportRecord) => {
    if (downloadingId) return;
    const graph = allGraphs.find((g) => g.uri === record.graphUri);
    if (!graph) return;
    setDownloadingId(record.id);
    try {
      await triggerDownload(graph, record.format);
      pushToast({
        type: 'success',
        title: 'Download complete',
        message: `${record.graphLabel} (.${record.format})`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Download failed';
      pushToast({ type: 'error', title: 'Download failed', message: msg });
    } finally {
      setDownloadingId(null);
    }
  }, [allGraphs, downloadingId, pushToast]);

  const isExporting = useMemo(
    () => records.some((r) => r.status === 'processing'),
    [records]
  );

  return (
    <div className="flex h-full flex-col">
      <Header />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <GraphSectionNav workspaceId={workspaceId} active="export" />
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
              <div className="mx-auto max-w-3xl space-y-8">
                {/* Format selector */}
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
                    onClick={() => void handleExport()}
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
                </div>

                {/* Export history */}
                {records.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                      Export History
                    </h3>
                    <div className="overflow-hidden rounded-lg border">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-muted/30">
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Date</th>
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Graph</th>
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Format</th>
                            <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Status</th>
                            <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Download</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {records.map((record) => (
                            <tr key={record.id} className="hover:bg-muted/20">
                              <td className="px-4 py-3 text-muted-foreground">
                                <span className="flex items-center gap-1.5">
                                  <Clock size={12} />
                                  {formatDate(record.createdAt)}
                                </span>
                              </td>
                              <td className="px-4 py-3 font-medium">{record.graphLabel}</td>
                              <td className="px-4 py-3">
                                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                                  .{record.format}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <StatusBadge status={record.status} error={record.error} />
                              </td>
                              <td className="px-4 py-3 text-right">
                                {record.status === 'ready' && (
                                  <button
                                    type="button"
                                    onClick={() => void handleRedownload(record)}
                                    disabled={downloadingId === record.id || graphsLoading}
                                    className={cn(
                                      'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors hover:bg-muted',
                                      (downloadingId === record.id || graphsLoading) && 'cursor-not-allowed opacity-50'
                                    )}
                                    title={`Download ${record.graphLabel}.${record.format}`}
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
                          ))}
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
