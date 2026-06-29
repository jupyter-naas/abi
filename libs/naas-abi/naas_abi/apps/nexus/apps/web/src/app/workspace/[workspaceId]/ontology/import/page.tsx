'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  Box,
  CheckCircle2,
  Clock,
  FileText,
  Link2,
  Loader2,
  Upload,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOntologyStore } from '@/stores/ontology';
import { useWorkspaceStore } from '@/stores/workspace';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { KpiCard } from '@/app/analytics/components/kpi-card';
import { ToastStack, type ToastItem } from '@/components/graph/toast-notification';

const ACCEPTED_EXTENSIONS = ['.ttl', '.owl', '.rdf', '.n3', '.nt'];

function isAcceptedFile(name: string): boolean {
  const ext = `.${name.split('.').pop()?.toLowerCase() ?? ''}`;
  return ACCEPTED_EXTENSIONS.includes(ext);
}

type ImportStatus = 'processing' | 'done' | 'error';

interface ImportRecord {
  id: string;
  filename: string;
  ontologyName: string;
  classes: number;
  properties: number;
  status: ImportStatus;
  createdAt: string;
  error?: string;
}

function storageKey(workspaceId: string) {
  return `ontology-imports-${workspaceId}`;
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

export default function OntologyImportPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const { currentWorkspaceId } = useWorkspaceStore();
  const importReferenceFromContent = useOntologyStore((state) => state.importReferenceFromContent);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
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

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;
    const f = files[0];
    if (!isAcceptedFile(f.name)) {
      setFileError(`Unsupported format. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      return;
    }
    setFileError(null);
    setFile(f);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const clearFile = useCallback(() => {
    setFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleImport = useCallback(async () => {
    if (!file || importing) return;

    const recordId = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setImporting(true);

    const newRecord: ImportRecord = {
      id: recordId,
      filename: file.name,
      ontologyName: '',
      classes: 0,
      properties: 0,
      status: 'processing',
      createdAt: new Date().toISOString(),
    };
    setRecords((prev) => {
      const next = [newRecord, ...prev];
      saveRecords(workspaceId, next);
      return next;
    });

    try {
      const content = await file.text();
      const ontology = await importReferenceFromContent(content, file.name);
      if (!ontology) throw new Error('Failed to import ontology');

      const classes = ontology.classes?.length ?? 0;
      const properties = ontology.properties?.length ?? 0;
      setRecords((prev) => {
        const next = prev.map((r) =>
          r.id === recordId
            ? { ...r, status: 'done' as const, ontologyName: ontology.name, classes, properties }
            : r,
        );
        saveRecords(workspaceId, next);
        return next;
      });

      pushToast({
        type: 'success',
        title: 'Import complete',
        message: `"${ontology.name}" imported — ${classes} class${classes !== 1 ? 'es' : ''}, ${properties} propert${properties !== 1 ? 'ies' : 'y'}`,
      });
      clearFile();
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
  }, [file, importing, workspaceId, importReferenceFromContent, pushToast, clearFile]);

  const lastDone = records.find((r) => r.status === 'done');

  return (
    <div className="flex h-full flex-col">
      <Header />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-6">
            <div className="mx-auto max-w-3xl space-y-8">

              {/* Drop zone */}
              <div className="space-y-4">
                <div>
                  <h2 className="text-base font-semibold">Import Ontology</h2>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    Upload a Turtle, OWL or RDF file to register it as a reference ontology.
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
                      <p className="text-sm font-medium">Drop your ontology file here</p>
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

              {/* Result preview */}
              {lastDone && (
                <div className="grid grid-cols-2 gap-3">
                  <KpiCard label="Classes" value={lastDone.classes} icon={Box} />
                  <KpiCard label="Object Properties" value={lastDone.properties} icon={Link2} />
                </div>
              )}

              {/* Action */}
              {file && (
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => void handleImport()}
                    disabled={importing}
                    className={cn(
                      'flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90',
                      importing && 'cursor-not-allowed opacity-50',
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
                  <button
                    type="button"
                    onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/ontology?view=network'))}
                    className="rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
                  >
                    Done
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
                          <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Ontology</th>
                          <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Classes</th>
                          <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">Properties</th>
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
                              {rec.ontologyName || <span className="text-muted-foreground">—</span>}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {rec.status === 'done' ? (
                                <span className="font-medium">{rec.classes}</span>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {rec.status === 'done' ? (
                                <span className="font-medium">{rec.properties}</span>
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
