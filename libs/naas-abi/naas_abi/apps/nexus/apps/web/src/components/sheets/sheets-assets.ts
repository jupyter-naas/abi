import { authFetch } from '@/stores/auth';

/**
 * Relative ``assets/<file.ext>`` only, as stored in ``workbook.html`` after seed
 * extraction. The lookbehind rejects ``https://host/assets/images/logo.png``
 * (a leading ``/``), which the old one-segment matcher treated as filename
 * ``images`` and 404'd on GET /assets/images.
 */
export const SHEETS_ASSET_REF_RE =
  /(?<![/\w])(?:(?:\.\.\/)+|\.\/)?assets\/[A-Za-z0-9][A-Za-z0-9._-]*\.[A-Za-z0-9]{1,8}/g;

const SHEETS_ASSET_FILENAME_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

export function sheetsAssetFilename(ref: string): string {
  return ref.replace(/^(?:(?:\.\.\/)+|\.\/)/, '').replace(/^assets\//, '');
}

export function isSheetsAssetFilename(filename: string): boolean {
  return (
    SHEETS_ASSET_FILENAME_RE.test(filename) &&
    filename.includes('.') &&
    !filename.includes('/')
  );
}

export function collectSheetsAssetRefs(html: string): string[] {
  if (!html) return [];
  return [...new Set(html.match(SHEETS_ASSET_REF_RE) || [])].filter((ref) =>
    isSheetsAssetFilename(sheetsAssetFilename(ref)),
  );
}

export function rewriteSheetsAssetUrls(
  html: string,
  toUrl: (ref: string) => string,
): string {
  if (!html) return html;
  return html.replace(SHEETS_ASSET_REF_RE, (ref) => toUrl(ref) || ref);
}

export function sheetsAssetApiPath(
  slug: string,
  workspaceId: string,
  filename: string,
): string {
  const q = new URLSearchParams({ workspace_id: workspaceId });
  return `/api/sheets/projects/${encodeURIComponent(slug)}/assets/${encodeURIComponent(filename)}?${q}`;
}

export async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('Failed to read asset'));
    reader.readAsDataURL(blob);
  });
}

export async function inlineSheetsAssets(
  html: string,
  load: (filename: string) => Promise<string | null>,
): Promise<string> {
  const refs = collectSheetsAssetRefs(html);
  if (!refs.length) return html;
  const map = new Map<string, string>();
  await Promise.all(
    refs.map(async (ref) => {
      const filename = sheetsAssetFilename(ref);
      if (!isSheetsAssetFilename(filename)) return;
      const dataUrl = await load(filename);
      if (dataUrl) map.set(ref, dataUrl);
    }),
  );
  if (!map.size) return html;
  return rewriteSheetsAssetUrls(html, (ref) => map.get(ref) || ref);
}

export async function loadSheetsAssetDataUrl(
  workspaceId: string,
  slug: string,
  filename: string,
): Promise<string | null> {
  if (!isSheetsAssetFilename(filename)) return null;
  const res = await authFetch(sheetsAssetApiPath(slug, workspaceId, filename));
  if (!res.ok) return null;
  return blobToDataUrl(await res.blob());
}

/** Resolve ``assets/`` refs for srcDoc preview (Bearer auth cannot ride on img src). */
export async function resolveSheetsPreviewAssets(
  html: string,
  workspaceId: string,
  slug: string,
): Promise<string> {
  if (!html || !workspaceId || !slug || !collectSheetsAssetRefs(html).length) {
    return html;
  }
  return inlineSheetsAssets(html, (filename) =>
    loadSheetsAssetDataUrl(workspaceId, slug, filename),
  );
}

export function downloadSheetsHtml(filename: string, html: string): void {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.html') ? filename : `${filename}.html`;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
