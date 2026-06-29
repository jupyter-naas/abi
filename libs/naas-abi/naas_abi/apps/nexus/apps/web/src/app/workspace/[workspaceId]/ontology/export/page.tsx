'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  Box,
  Download,
  GitBranch,
  Link2,
  Loader2,
  RefreshCw,
  Tag,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useOntologyStore } from '@/stores/ontology';
import { KpiCard } from '@/app/analytics/components/kpi-card';

interface OntologyFileApiItem {
  name?: string;
  path?: string;
  module_name?: string;
  submodule_name?: string | null;
}

interface OntologyFile {
  name: string;
  path: string;
  moduleName: string;
}

interface OntologyStats {
  name: string;
  path: string;
  total_items: number;
  classes: number;
  object_properties: number;
  data_properties: number;
  named_individuals: number;
  imports: number;
}

interface ModuleGroup {
  moduleName: string;
  files: OntologyFile[];
}

export default function OntologyExportPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const { selectedOntologyPath } = useOntologyStore();

  const [files, setFiles] = useState<OntologyFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [stats, setStats] = useState<OntologyStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const loadFiles = useCallback(async () => {
    setFilesLoading(true);
    setFilesError(null);
    try {
      const res = await authFetch(`${getApiUrl()}/api/ontology/ontologies`);
      if (!res.ok) throw new Error(`Failed to load ontologies (${res.status})`);
      const data = (await res.json()) as { items?: OntologyFileApiItem[] };
      const items = Array.isArray(data.items) ? data.items : [];
      const normalized: OntologyFile[] = items
        .filter((f): f is OntologyFileApiItem & { name: string; path: string } =>
          typeof f.name === 'string' && typeof f.path === 'string')
        .map((f) => ({
          name: f.name,
          path: f.path,
          moduleName: f.module_name || 'Unknown module',
        }))
        .sort((a, b) =>
          a.moduleName.localeCompare(b.moduleName, undefined, { sensitivity: 'base' })
          || a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
      setFiles(normalized);
    } catch (err) {
      setFilesError(err instanceof Error ? err.message : 'Failed to load ontologies');
      setFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  const moduleGroups = useMemo<ModuleGroup[]>(() => {
    const byModule = new Map<string, OntologyFile[]>();
    for (const f of files) {
      const bucket = byModule.get(f.moduleName);
      if (bucket) bucket.push(f);
      else byModule.set(f.moduleName, [f]);
    }
    return [...byModule.entries()].map(([moduleName, fs]) => ({ moduleName, files: fs }));
  }, [files]);

  // Resolve the active ontology: explicit selection wins, else the workspace-wide
  // selected ontology, else the first available.
  const activePath = useMemo<string | null>(() => {
    if (selectedPath && files.some((f) => f.path === selectedPath)) return selectedPath;
    if (selectedOntologyPath && files.some((f) => f.path === selectedOntologyPath)) {
      return selectedOntologyPath;
    }
    return files[0]?.path ?? null;
  }, [selectedPath, selectedOntologyPath, files]);

  const activeFile = useMemo(
    () => files.find((f) => f.path === activePath) ?? null,
    [files, activePath],
  );

  useEffect(() => {
    if (!activePath) {
      setStats(null);
      return;
    }
    let cancelled = false;
    setStatsLoading(true);
    void (async () => {
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/ontology/overview/stats?ontology_path=${encodeURIComponent(activePath)}`,
        );
        if (!res.ok) throw new Error(`Failed to load ontology stats (${res.status})`);
        const data = (await res.json()) as OntologyStats;
        if (!cancelled) setStats(data);
      } catch {
        if (!cancelled) setStats(null);
      } finally {
        if (!cancelled) setStatsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activePath]);

  const handleExport = useCallback(async () => {
    if (!activePath || exporting) return;
    setExporting(true);
    setExportError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/ontology/export?ontology_path=${encodeURIComponent(activePath)}`,
      );
      if (!res.ok) throw new Error(`Failed to export ontology (${res.status})`);

      const contentDisposition = res.headers.get('content-disposition') || '';
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
      const filename = filenameMatch?.[1] || activePath.split('/').pop() || 'ontology.ttl';

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  }, [activePath, exporting]);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-6">
            {filesLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : filesError ? (
              <div className="flex h-full items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="mb-2 text-sm">{filesError}</p>
                  <button
                    onClick={() => void loadFiles()}
                    className="mx-auto flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    <RefreshCw size={14} />
                    Retry
                  </button>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-5xl space-y-10">
                <div className="space-y-8">
                  <div>
                    <h2 className="text-base font-semibold">Export Ontology</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Pick an ontology and download it as a Turtle (.ttl) file.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="export-ontology" className="text-xs font-medium text-muted-foreground">
                      Ontology
                    </label>
                    {files.length > 0 ? (
                      <select
                        id="export-ontology"
                        value={activePath ?? ''}
                        onChange={(e) => setSelectedPath(e.target.value)}
                        className="block w-full max-w-sm rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      >
                        {moduleGroups.map((group) => (
                          <optgroup key={group.moduleName} label={group.moduleName}>
                            {group.files.map((f) => (
                              <option key={f.path} value={f.path}>
                                {f.name}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    ) : (
                      <p className="text-sm text-muted-foreground">No ontology selected</p>
                    )}
                  </div>

                  {activeFile && (
                    <div className="grid grid-cols-3 gap-4">
                      {statsLoading ? (
                        Array.from({ length: 3 }).map((_, i) => (
                          <div key={i} className="h-[110px] animate-pulse rounded border bg-muted/30" />
                        ))
                      ) : stats ? (
                        <>
                          <KpiCard
                            label="Classes"
                            value={stats.classes.toLocaleString()}
                            hint="OWL classes defined in this ontology"
                            icon={Box}
                          />
                          <KpiCard
                            label="Object Properties"
                            value={stats.object_properties.toLocaleString()}
                            hint="Relationships between classes"
                            icon={Link2}
                          />
                          <KpiCard
                            label="Data Properties"
                            value={stats.data_properties.toLocaleString()}
                            hint="Literal data attributes on classes"
                            icon={Tag}
                          />
                        </>
                      ) : null}
                    </div>
                  )}

                  <div className="space-y-2 pt-1">
                    <button
                      type="button"
                      onClick={() => void handleExport()}
                      disabled={!activePath || exporting}
                      className={cn(
                        'flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90',
                        (!activePath || exporting) && 'cursor-not-allowed opacity-50',
                      )}
                    >
                      {exporting ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          Exporting…
                        </>
                      ) : (
                        <>
                          <Download size={14} />
                          Export as .ttl
                        </>
                      )}
                    </button>

                    <p className="text-xs text-muted-foreground">
                      Exports the ontology definition file as-is. The download starts immediately.
                    </p>
                  </div>

                  {exportError && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
                      <span className="flex items-center gap-2">
                        <GitBranch size={14} />
                        {exportError}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
