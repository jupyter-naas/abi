'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileText,
  GitBranch,
  Loader2,
  Network,
  Upload,
  Users,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { GraphSectionNav } from '@/components/graph/graph-section-nav';
import { GraphDevBanner } from '@/components/graph/graph-dev-banner';
import { KpiCard } from '@/app/analytics/components/kpi-card';
import { ToastStack, type ToastItem } from '@/components/graph/toast-notification';

const ACCEPTED_EXTENSIONS = ['.ttl', '.owl', '.nt', '.rdf', '.n3'];

function isAcceptedFile(name: string): boolean {
  const ext = `.${name.split('.').pop()?.toLowerCase() ?? ''}`;
  return ACCEPTED_EXTENSIONS.includes(ext);
}

interface GraphAnalysis {
  total_triples: number;
  total_subjects: number;
  named_individuals_subjects: number;
  named_individuals_triples: number;
  classes_subjects: number;
  classes_triples: number;
  object_properties_subjects: number;
  object_properties_triples: number;
  datatype_properties_subjects: number;
  datatype_properties_triples: number;
  restrictions_subjects: number;
  restrictions_triples: number;
  unknown_subjects: number;
  unknown_triples: number;
}

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

type ImportStatus = 'processing' | 'done' | 'error';

interface ImportRecord {
  id: string;
  filename: string;
  graphLabel: string;
  triplesImported: number;
  status: ImportStatus;
  createdAt: string;
  error?: string;
}

function storageKey(workspaceId: string) {
  return `graph-imports-${workspaceId}`;
}

function loadRecords(workspaceId: string): ImportRecord[] {
  try {
    const raw = localStorage.getItem(storageKey(workspaceId));
    return raw ? (JSON.parse(raw) as ImportRecord[]) : [];
  } catch {
    return [];
  }
}

function saveRecords(workspaceId: string, records: ImportRecord[]) {
  try {
    localStorage.setItem(storageKey(workspaceId), JSON.stringify(records));
  } catch {}
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatRoleLabel(role: string): string {
  if (!role || role === 'unknown') return 'Unknown';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function StatusBadge({ status, error }: { status: ImportStatus; error?: string }) {
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
      Done
    </span>
  );
}

export default function ImportPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const { selectGraph, setVisibleGraphs } = useKnowledgeGraphStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<GraphAnalysis | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [roles, setRoles] = useState<string[]>(['unknown']);
  const [metaLoading, setMetaLoading] = useState(true);

  // destination: 'new' or 'existing'
  const [destMode, setDestMode] = useState<'new' | 'existing'>('new');
  const [newLabel, setNewLabel] = useState('');
  const [newRole, setNewRole] = useState('unknown');
  const [existingGraphUri, setExistingGraphUri] = useState('');

  const [importing, setImporting] = useState(false);
  const [records, setRecords] = useState<ImportRecord[]>([]);

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
    return graphPacks.flatMap((p) =>
      p.graphs.filter((g) => {
        if (seen.has(g.uri)) return false;
        seen.add(g.uri);
        return true;
      }),
    );
  }, [graphPacks]);

  const selectableRoles = useMemo(
    () => roles.filter((r) => r.trim().toLowerCase() !== 'admin'),
    [roles],
  );

  useEffect(() => {
    if (allGraphs.length > 0 && !existingGraphUri) {
      setExistingGraphUri(allGraphs[0].uri);
    }
  }, [allGraphs, existingGraphUri]);

  const loadMeta = useCallback(async () => {
    setMetaLoading(true);
    try {
      const [rolesRes, listRes] = await Promise.all([
        authFetch(`${getApiUrl()}/api/graph/roles?workspace_id=${encodeURIComponent(workspaceId)}`),
        authFetch(`${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`),
      ]);
      if (rolesRes.ok) {
        const data = (await rolesRes.json()) as string[];
        const normalized = data.map((r) => r.trim().toLowerCase()).filter(Boolean);
        const withDefault = normalized.includes('unknown') ? normalized : [...normalized, 'unknown'];
        setRoles(withDefault);
        setNewRole(withDefault.filter((r) => r !== 'admin')[0] ?? 'unknown');
      }
      if (listRes.ok) {
        const packs = (await listRes.json()) as ApiGraphPack[];
        setGraphPacks(Array.isArray(packs) ? packs : []);
      }
    } catch {
      /* ignore */
    } finally {
      setMetaLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta]);

  const analyzeFile = useCallback(async (f: File) => {
    setAnalyzing(true);
    setAnalysis(null);
    setAnalyzeError(null);
    try {
      const form = new FormData();
      form.append('workspace_id', workspaceId);
      form.append('file', f);
      const res = await authFetch(`${getApiUrl()}/api/graph/analyze`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(typeof payload.detail === 'string' ? payload.detail : `Parse error (${res.status})`);
      }
      const data = (await res.json()) as GraphAnalysis;
      setAnalysis(data);
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Failed to analyze file');
    } finally {
      setAnalyzing(false);
    }
  }, [workspaceId]);

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;
    const f = files[0];
    if (!isAcceptedFile(f.name)) {
      setFileError(`Unsupported format. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      return;
    }
    setFileError(null);
    setAnalysis(null);
    setAnalyzeError(null);
    setFile(f);
    void analyzeFile(f);
  }, [analyzeFile]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const clearFile = useCallback(() => {
    setFile(null);
    setAnalysis(null);
    setAnalyzeError(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleImport = useCallback(async () => {
    if (!file || !analysis || importing) return;

    const recordId = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    let graphUri = '';
    let graphLabel = '';

    setImporting(true);

    const newRecord: ImportRecord = {
      id: recordId,
      filename: file.name,
      graphLabel: '',
      triplesImported: 0,
      status: 'processing',
      createdAt: new Date().toISOString(),
    };
    setRecords((prev) => {
      const next = [newRecord, ...prev];
      saveRecords(workspaceId, next);
      return next;
    });

    try {
      if (destMode === 'new') {
        const trimmed = newLabel.trim();
        if (!trimmed) throw new Error('Graph name is required');
        const createRes = await authFetch(`${getApiUrl()}/api/graph/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            label: trimmed,
            role_label: newRole,
          }),
        });
        if (!createRes.ok) {
          const p = await createRes.json().catch(() => ({})) as { detail?: string };
          throw new Error(typeof p.detail === 'string' ? p.detail : `Failed to create graph (${createRes.status})`);
        }
        const created = (await createRes.json()) as { uri: string; id: string; label: string };
        graphUri = created.uri;
        graphLabel = created.label;
        selectGraph(created.id);
        setVisibleGraphs([created.id]);
        window.dispatchEvent(new CustomEvent('graph-list-update'));
      } else {
        const g = allGraphs.find((x) => x.uri === existingGraphUri);
        if (!g) throw new Error('No graph selected');
        graphUri = g.uri;
        graphLabel = g.label;
      }

      const form = new FormData();
      form.append('workspace_id', workspaceId);
      form.append('graph_uri', graphUri);
      form.append('file', file);
      const importRes = await authFetch(`${getApiUrl()}/api/graph/import`, {
        method: 'POST',
        body: form,
      });
      if (!importRes.ok) {
        const p = await importRes.json().catch(() => ({})) as { detail?: string };
        throw new Error(typeof p.detail === 'string' ? p.detail : `Import failed (${importRes.status})`);
      }
      const result = (await importRes.json()) as { status: string; count: number };

      setRecords((prev) => {
        const next = prev.map((r) =>
          r.id === recordId
            ? { ...r, status: 'done' as const, graphLabel, triplesImported: result.count }
            : r,
        );
        saveRecords(workspaceId, next);
        return next;
      });

      pushToast({
        type: 'success',
        title: 'Import complete',
        message: `${result.count} triple${result.count !== 1 ? 's' : ''} imported into "${graphLabel}"`,
      });
      clearFile();
      setNewLabel('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Import failed';
      setRecords((prev) => {
        const next = prev.map((r) =>
          r.id === recordId ? { ...r, status: 'error' as const, error: msg } : r,
        );
        saveRecords(workspaceId, next);
        return next;
      });
      pushToast({ type: 'error', title: 'Import failed', message: msg });
    } finally {
      setImporting(false);
    }
  }, [
    file, analysis, importing, destMode, newLabel, newRole, existingGraphUri,
    allGraphs, workspaceId, selectGraph, setVisibleGraphs, pushToast, clearFile,
  ]);

  const canImport =
    !!file &&
    !!analysis &&
    !analyzing &&
    !importing &&
    (destMode === 'existing' ? !!existingGraphUri : newLabel.trim().length > 0);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <GraphSectionNav workspaceId={workspaceId} active="import" />
          <GraphDevBanner />

          <div className="flex-1 overflow-y-auto px-6 py-6">
            <div className="mx-auto max-w-3xl space-y-8">

              {/* Drop zone */}
              <div className="space-y-4">
                <div>
                  <h2 className="text-base font-semibold">Import Graph</h2>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    Upload a Turtle, OWL or N-Triples file to import named individuals into a graph.
                  </p>
                </div>

                {!file ? (
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={cn(
                      'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-12 transition-colors',
                      dragOver
                        ? 'border-foreground bg-muted/30'
                        : 'border-border hover:border-muted-foreground hover:bg-muted/10',
                    )}
                  >
                    <Upload size={28} className="text-muted-foreground" />
                    <div className="text-center">
                      <p className="text-sm font-medium">Drop your RDF file here</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        or click to browse — {ACCEPTED_EXTENSIONS.join(', ')}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 rounded-lg border bg-muted/20 px-4 py-3">
                    <FileText size={16} className="shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{file.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </span>
                    <button
                      type="button"
                      onClick={clearFile}
                      className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
                      title="Remove file"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(',')}
                  className="hidden"
                  onChange={(e) => handleFiles(e.target.files)}
                />

                {fileError && (
                  <p className="flex items-center gap-2 text-sm text-red-500">
                    <AlertCircle size={14} />
                    {fileError}
                  </p>
                )}
              </div>

              {/* Analysis */}
              {file && (
                <div className="space-y-4">
                  {analyzing ? (
                    <div className="grid grid-cols-4 gap-3">
                      {Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="h-[110px] animate-pulse rounded border bg-muted/30" />
                      ))}
                    </div>
                  ) : analyzeError ? (
                    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
                      <AlertCircle size={15} className="mt-0.5 shrink-0" />
                      <div>
                        <p className="font-medium">File parse error</p>
                        <p className="mt-0.5 text-xs opacity-80">{analyzeError}</p>
                      </div>
                    </div>
                  ) : analysis ? (
                    <div className="grid grid-cols-4 gap-3">
                      <KpiCard
                        label="Classes"
                        value={analysis.classes_subjects}
                        icon={Network}
                      />
                      <KpiCard
                        label="Individuals"
                        value={analysis.named_individuals_subjects}
                        icon={Users}
                      />
                      <KpiCard
                        label="Total Triples"
                        value={analysis.total_triples}
                        icon={GitBranch}
                      />
                      <KpiCard
                        label="Object Properties"
                        value={analysis.object_properties_subjects}
                        icon={FileText}
                      />
                    </div>
                  ) : null}
                </div>
              )}

              {/* Graph destination */}
              {analysis && !analyzeError && (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold">Graph destination</h3>

                  <div className="space-y-3">
                    {/* New graph option */}
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-4 hover:bg-muted/20">
                      <input
                        type="radio"
                        name="destMode"
                        value="new"
                        checked={destMode === 'new'}
                        onChange={() => setDestMode('new')}
                        className="mt-0.5"
                      />
                      <div className="flex-1 space-y-3">
                        <span className="text-sm font-medium">Create new graph</span>
                        {destMode === 'new' && (
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="mb-1.5 block text-xs text-muted-foreground">
                                Graph name *
                              </label>
                              <input
                                type="text"
                                value={newLabel}
                                onChange={(e) => setNewLabel(e.target.value)}
                                placeholder="e.g., Customer Graph"
                                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary"
                                onClick={(e) => e.stopPropagation()}
                              />
                            </div>
                            <div>
                              <label className="mb-1.5 block text-xs text-muted-foreground">
                                Role
                              </label>
                              {metaLoading ? (
                                <div className="flex h-[34px] items-center gap-2 rounded-md border bg-muted/30 px-3 text-xs text-muted-foreground">
                                  <Loader2 size={12} className="animate-spin" />
                                  Loading…
                                </div>
                              ) : (
                                <div className="relative">
                                  <select
                                    value={newRole}
                                    onChange={(e) => setNewRole(e.target.value)}
                                    onClick={(e) => e.stopPropagation()}
                                    className="w-full appearance-none rounded-md border bg-background px-3 py-1.5 pr-8 text-sm outline-none focus:ring-2 focus:ring-primary"
                                  >
                                    {selectableRoles.map((r) => (
                                      <option key={r} value={r}>
                                        {formatRoleLabel(r)}
                                      </option>
                                    ))}
                                  </select>
                                  <ChevronDown
                                    size={13}
                                    className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </label>

                    {/* Existing graph option */}
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-4 hover:bg-muted/20">
                      <input
                        type="radio"
                        name="destMode"
                        value="existing"
                        checked={destMode === 'existing'}
                        onChange={() => setDestMode('existing')}
                        className="mt-0.5"
                      />
                      <div className="flex-1 space-y-3">
                        <span className="text-sm font-medium">Import into existing graph</span>
                        {destMode === 'existing' && (
                          <div>
                            {metaLoading ? (
                              <div className="flex h-[34px] items-center gap-2 rounded-md border bg-muted/30 px-3 text-xs text-muted-foreground">
                                <Loader2 size={12} className="animate-spin" />
                                Loading graphs…
                              </div>
                            ) : allGraphs.length === 0 ? (
                              <p className="text-xs text-muted-foreground">
                                No graphs available in this workspace.
                              </p>
                            ) : (
                              <div className="relative">
                                <select
                                  value={existingGraphUri}
                                  onChange={(e) => setExistingGraphUri(e.target.value)}
                                  onClick={(e) => e.stopPropagation()}
                                  className="w-full appearance-none rounded-md border bg-background px-3 py-1.5 pr-8 text-sm outline-none focus:ring-2 focus:ring-primary"
                                >
                                  {graphPacks.map((pack) => (
                                    <optgroup key={pack.role_label} label={formatRoleLabel(pack.role_label)}>
                                      {pack.graphs.map((g) => (
                                        <option key={g.uri} value={g.uri}>
                                          {g.label}
                                        </option>
                                      ))}
                                    </optgroup>
                                  ))}
                                </select>
                                <ChevronDown
                                  size={13}
                                  className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                                />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </label>
                  </div>

                  <button
                    type="button"
                    onClick={() => void handleImport()}
                    disabled={!canImport}
                    className={cn(
                      'flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90',
                      !canImport && 'cursor-not-allowed opacity-50',
                    )}
                  >
                    {importing ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        Importing…
                      </>
                    ) : (
                      <>
                        <Upload size={14} />
                        Import
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* Import history */}
              {records.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Import History
                  </h3>
                  <div className="overflow-hidden rounded-lg border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/30">
                          <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Date</th>
                          <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">File</th>
                          <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Graph</th>
                          <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Triples</th>
                          <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {records.map((rec) => (
                          <tr key={rec.id} className="hover:bg-muted/20">
                            <td className="px-4 py-3 text-muted-foreground">
                              <span className="flex items-center gap-1.5">
                                <Clock size={12} />
                                {formatDate(rec.createdAt)}
                              </span>
                            </td>
                            <td className="max-w-[160px] truncate px-4 py-3 font-mono text-xs">
                              {rec.filename}
                            </td>
                            <td className="px-4 py-3">
                              {rec.graphLabel || (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {rec.status === 'done' ? (
                                <span className="font-medium">{rec.triplesImported}</span>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <StatusBadge status={rec.status} error={rec.error} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
