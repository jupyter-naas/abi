import { authFetch } from '@/stores/auth';

/** Relative deck asset, as stored in ``deck.html`` after seed extraction. */
export const SLIDES_ASSET_REF_RE = /(?:(?:\.\.\/)+|\.\/)?assets\/[A-Za-z0-9._-]+/g;

export function collectSlidesAssetRefs(html: string): string[] {
  if (!html) return [];
  return [...new Set(html.match(SLIDES_ASSET_REF_RE) || [])];
}

export function slidesAssetFilename(ref: string): string {
  return ref.replace(/^(?:(?:\.\.\/)+|\.\/)/, '').replace(/^assets\//, '');
}

export function rewriteSlidesAssetUrls(
  html: string,
  toUrl: (ref: string) => string,
): string {
  if (!html) return html;
  return html.replace(SLIDES_ASSET_REF_RE, (ref) => toUrl(ref) || ref);
}

export function slidesAssetApiPath(
  slug: string,
  workspaceId: string,
  filename: string,
): string {
  const q = new URLSearchParams({ workspace_id: workspaceId });
  return `/api/slides/projects/${encodeURIComponent(slug)}/assets/${encodeURIComponent(filename)}?${q}`;
}

export async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('Failed to read asset'));
    reader.readAsDataURL(blob);
  });
}

export async function inlineSlidesAssets(
  html: string,
  load: (filename: string) => Promise<string | null>,
): Promise<string> {
  const refs = collectSlidesAssetRefs(html);
  if (!refs.length) return html;
  const map = new Map<string, string>();
  await Promise.all(
    refs.map(async (ref) => {
      const dataUrl = await load(slidesAssetFilename(ref));
      if (dataUrl) map.set(ref, dataUrl);
    }),
  );
  if (!map.size) return html;
  return rewriteSlidesAssetUrls(html, (ref) => map.get(ref) || ref);
}

export async function loadSlidesAssetDataUrl(
  workspaceId: string,
  slug: string,
  filename: string,
): Promise<string | null> {
  const res = await authFetch(slidesAssetApiPath(slug, workspaceId, filename));
  if (!res.ok) return null;
  return blobToDataUrl(await res.blob());
}

/** Resolve ``assets/`` refs for srcDoc preview (Bearer auth cannot ride on img src). */
export async function resolveSlidesPreviewAssets(
  html: string,
  workspaceId: string,
  slug: string,
): Promise<string> {
  if (!html || !workspaceId || !slug || !collectSlidesAssetRefs(html).length) {
    return html;
  }
  return inlineSlidesAssets(html, (filename) =>
    loadSlidesAssetDataUrl(workspaceId, slug, filename),
  );
}

export function downloadSlidesHtml(filename: string, html: string): void {
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
