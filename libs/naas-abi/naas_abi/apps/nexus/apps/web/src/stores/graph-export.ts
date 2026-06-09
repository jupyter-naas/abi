'use client';

import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import {
  EXPORT_FORMAT_LABELS,
  loadExportRecords,
  pruneExportRecords,
  saveExportRecords,
  type ExportFormat,
  type ExportKpiSnapshot,
  type ExportRecord,
} from '@/lib/graph-export-records';
import { authFetch } from '@/stores/auth';
import type { ToastItem } from '@/components/graph/toast-notification';

interface GraphExportState {
  recordsByWorkspace: Record<string, ExportRecord[]>;
  isExportPageActive: boolean;
  toasts: ToastItem[];
  setExportPageActive: (active: boolean) => void;
  dismissToast: (id: string) => void;
  loadWorkspaceRecords: (workspaceId: string) => void;
  startExport: (
    workspaceId: string,
    graph: { uri: string; label: string },
    format: ExportFormat,
    kpis?: ExportKpiSnapshot,
  ) => string | null;
  downloadExport: (
    workspaceId: string,
    record: ExportRecord,
  ) => Promise<void>;
}

const runningJobs = new Set<string>();
const initializedWorkspaces = new Set<string>();

function createToast(toast: Omit<ToastItem, 'id'>): ToastItem {
  return {
    ...toast,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
  };
}

function parseCountHeader(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

async function fetchExport(
  workspaceId: string,
  graphUri: string,
  format: ExportFormat,
): Promise<{ tripleCount?: number; namedIndividualCount?: number }> {
  const url = `${getApiUrl()}/api/graph/export?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(graphUri)}&format=${format}`;
  const response = await authFetch(url);
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const tripleCount = parseCountHeader(response.headers.get('X-Triple-Count'));
  const namedIndividualCount = parseCountHeader(response.headers.get('X-Named-Individual-Count'));
  await response.blob();
  return { tripleCount, namedIndividualCount };
}

async function triggerBrowserDownload(
  workspaceId: string,
  graph: { uri: string; label: string },
  format: ExportFormat,
): Promise<void> {
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

function updateRecord(
  workspaceId: string,
  recordId: string,
  patch: Partial<ExportRecord>,
): ExportRecord[] {
  const state = useGraphExportStore.getState();
  const current = state.recordsByWorkspace[workspaceId] ?? [];
  const next = pruneExportRecords(
    current.map((record) => (record.id === recordId ? { ...record, ...patch } : record)),
  );
  saveExportRecords(workspaceId, next);
  useGraphExportStore.setState((prev) => ({
    recordsByWorkspace: { ...prev.recordsByWorkspace, [workspaceId]: next },
  }));
  return next;
}

async function runExportJob(
  workspaceId: string,
  recordId: string,
  graphUri: string,
  graphLabel: string,
  format: ExportFormat,
): Promise<void> {
  if (runningJobs.has(recordId)) return;
  runningJobs.add(recordId);

  try {
    const stats = await fetchExport(workspaceId, graphUri, format);
    updateRecord(workspaceId, recordId, {
      status: 'ready',
      tripleCount: stats.tripleCount,
    });

    const { isExportPageActive, toasts, recordsByWorkspace } = useGraphExportStore.getState();
    const record = (recordsByWorkspace[workspaceId] ?? []).find((item) => item.id === recordId);
    const individuals = record?.kpis?.individuals ?? stats.namedIndividualCount;
    const formatLabel = EXPORT_FORMAT_LABELS[format];

    if (!isExportPageActive) {
      const individualsLabel =
        individuals != null
          ? `${individuals.toLocaleString()} individuals`
          : 'Export';
      useGraphExportStore.setState({
        toasts: [
          ...toasts,
          createToast({
            type: 'success',
            title: 'Export ready',
            message: `${graphLabel} (${formatLabel}) — ${individualsLabel} ready to download`,
          }),
        ],
      });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Export failed';
    updateRecord(workspaceId, recordId, { status: 'error', error: message });

    const { isExportPageActive, toasts } = useGraphExportStore.getState();
    if (!isExportPageActive) {
      useGraphExportStore.setState({
        toasts: [
          ...toasts,
          createToast({
            type: 'error',
            title: 'Export failed',
            message: `${graphLabel}: ${message}`,
          }),
        ],
      });
    }
  } finally {
    runningJobs.delete(recordId);
  }
}

function resumeProcessingExports(workspaceId: string, records: ExportRecord[]): void {
  for (const record of records) {
    if (record.status !== 'processing') continue;
    void runExportJob(
      workspaceId,
      record.id,
      record.graphUri,
      record.graphLabel,
      record.format,
    );
  }
}

export const useGraphExportStore = create<GraphExportState>((set, get) => ({
  recordsByWorkspace: {},
  isExportPageActive: false,
  toasts: [],

  setExportPageActive: (active) => set({ isExportPageActive: active }),

  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    })),

  loadWorkspaceRecords: (workspaceId) => {
    if (initializedWorkspaces.has(workspaceId)) return;

    const records = loadExportRecords(workspaceId);
    initializedWorkspaces.add(workspaceId);
    set((state) => ({
      recordsByWorkspace: { ...state.recordsByWorkspace, [workspaceId]: records },
    }));
    resumeProcessingExports(workspaceId, records);
  },

  startExport: (workspaceId, graph, format, kpis) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const newRecord: ExportRecord = {
      id,
      graphUri: graph.uri,
      graphLabel: graph.label,
      workspaceId,
      format,
      status: 'processing',
      createdAt: new Date().toISOString(),
      kpis,
    };

    const current = get().recordsByWorkspace[workspaceId] ?? [];
    const next = pruneExportRecords([newRecord, ...current]);
    saveExportRecords(workspaceId, next);
    set((state) => ({
      recordsByWorkspace: { ...state.recordsByWorkspace, [workspaceId]: next },
    }));

    void runExportJob(workspaceId, id, graph.uri, graph.label, format);
    return id;
  },

  downloadExport: async (workspaceId, record) => {
    await triggerBrowserDownload(
      workspaceId,
      { uri: record.graphUri, label: record.graphLabel },
      record.format,
    );
  },
}));
