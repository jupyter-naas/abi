export type ExportFormat = 'ttl' | 'owl' | 'nt';
export type ExportStatus = 'processing' | 'ready' | 'error';

export interface ExportRecord {
  id: string;
  graphUri: string;
  graphLabel: string;
  workspaceId: string;
  format: ExportFormat;
  status: ExportStatus;
  createdAt: string;
  error?: string;
  tripleCount?: number;
  namedIndividualCount?: number;
}

export const EXPORT_RETENTION_MS = 7 * 24 * 60 * 60 * 1000;

export function storageKey(workspaceId: string): string {
  return `graph-exports-${workspaceId}`;
}

export function pruneExportRecords(
  records: ExportRecord[],
  now = Date.now(),
): ExportRecord[] {
  const cutoff = now - EXPORT_RETENTION_MS;
  return records.filter((record) => new Date(record.createdAt).getTime() >= cutoff);
}

export function loadExportRecords(workspaceId: string): ExportRecord[] {
  try {
    const raw = localStorage.getItem(storageKey(workspaceId));
    if (!raw) return [];
    return pruneExportRecords(JSON.parse(raw) as ExportRecord[]);
  } catch {
    return [];
  }
}

export function saveExportRecords(workspaceId: string, records: ExportRecord[]): void {
  try {
    const pruned = pruneExportRecords(records);
    localStorage.setItem(storageKey(workspaceId), JSON.stringify(pruned));
  } catch {
    // ignore storage errors
  }
}
