import { authFetch } from '@/stores/auth';

/**
 * Relative ``assets/<file.ext>`` only, as stored in ``document.html`` after seed
 * extraction. The lookbehind rejects ``https://host/assets/images/logo.png``
 * (a leading ``/``), which the old one-segment matcher treated as filename
 * ``images`` and 404'd on GET /assets/images.
 */
export const SLIDES_ASSET_REF_RE =
  /(?<![/\w])(?:(?:\.\.\/)+|\.\/)?assets\/[A-Za-z0-9][A-Za-z0-9._-]*\.[A-Za-z0-9]{1,8}/g;

const SLIDES_ASSET_FILENAME_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

export function sectionsAssetFilename(ref: string): string {
  return ref.replace(/^(?:(?:\.\.\/)+|\.\/)/, '').replace(/^assets\//, '');
}

export function isSectionsAssetFilename(filename: string): boolean {
  return (
    SLIDES_ASSET_FILENAME_RE.test(filename) &&
    filename.includes('.') &&
    !filename.includes('/')
  );
}

export function collectSectionsAssetRefs(html: string): string[] {
  if (!html) return [];
  return [...new Set(html.match(SLIDES_ASSET_REF_RE) || [])].filter((ref) =>
    isSectionsAssetFilename(sectionsAssetFilename(ref)),
  );
}

export function rewriteSectionsAssetUrls(
  html: string,
  toUrl: (ref: string) => string,
): string {
  if (!html) return html;
  return html.replace(SLIDES_ASSET_REF_RE, (ref) => toUrl(ref) || ref);
}

export function sectionsAssetApiPath(
  slug: string,
  workspaceId: string,
  filename: string,
): string {
  const q = new URLSearchParams({ workspace_id: workspaceId });
  return `/api/documents/projects/${encodeURIComponent(slug)}/assets/${encodeURIComponent(filename)}?${q}`;
}

export async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('Failed to read asset'));
    reader.readAsDataURL(blob);
  });
}

export async function inlineSectionsAssets(
  html: string,
  load: (filename: string) => Promise<string | null>,
): Promise<string> {
  const refs = collectSectionsAssetRefs(html);
  if (!refs.length) return html;
  const map = new Map<string, string>();
  await Promise.all(
    refs.map(async (ref) => {
      const filename = sectionsAssetFilename(ref);
      if (!isSectionsAssetFilename(filename)) return;
      const dataUrl = await load(filename);
      if (dataUrl) map.set(ref, dataUrl);
    }),
  );
  if (!map.size) return html;
  return rewriteSectionsAssetUrls(html, (ref) => map.get(ref) || ref);
}

export async function loadSectionsAssetDataUrl(
  workspaceId: string,
  slug: string,
  filename: string,
): Promise<string | null> {
  if (!isSectionsAssetFilename(filename)) return null;
  const res = await authFetch(sectionsAssetApiPath(slug, workspaceId, filename));
  if (!res.ok) return null;
  return blobToDataUrl(await res.blob());
}

/** Resolve ``assets/`` refs for srcDoc preview (Bearer auth cannot ride on img src). */
export async function resolveDocumentsPreviewAssets(
  html: string,
  workspaceId: string,
  slug: string,
): Promise<string> {
  if (!html || !workspaceId || !slug || !collectSectionsAssetRefs(html).length) {
    return html;
  }
  return inlineSectionsAssets(html, (filename) =>
    loadSectionsAssetDataUrl(workspaceId, slug, filename),
  );
}

export function downloadDocumentsHtml(filename: string, html: string): void {
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
