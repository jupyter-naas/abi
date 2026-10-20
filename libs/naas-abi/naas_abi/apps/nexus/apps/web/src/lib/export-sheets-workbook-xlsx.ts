import { authFetch } from '@/stores/auth';
import { sheetsApiErrorMessage } from '@/lib/create-sheets-project';

/** Download the live workbook as XLSX (formulas evaluated server-side). */
export async function downloadSheetsWorkbookXlsx(
  workspaceId: string,
  slug: string,
  filename?: string,
): Promise<void> {
  const q = new URLSearchParams({ workspace_id: workspaceId });
  const res = await authFetch(
    `/api/sheets/projects/${encodeURIComponent(slug)}/export/xlsx?${q}`,
  );
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(
      sheetsApiErrorMessage(detail?.detail, `XLSX export failed (${res.status})`),
    );
  }
  const blob = await res.blob();
  const name = filename || `${slug || 'workbook'}.xlsx`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}
