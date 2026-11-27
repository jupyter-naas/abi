import { authFetch } from '@/stores/auth';
import type { OfficeKindId } from './office-kinds';

/**
 * Relative ``assets/<file.ext>`` only, as stored in an item's HTML after seed
 * extraction. The lookbehind rejects ``https://host/assets/images/logo.png``
 * (a leading ``/``), which the old one-segment matcher treated as filename
 * ``images`` and 404'd on GET /assets/images.
 */
export const OFFICE_ASSET_REF_RE =
  /(?<![/\w])(?:(?:\.\.\/)+|\.\/)?assets\/[A-Za-z0-9][A-Za-z0-9._-]*\.[A-Za-z0-9]{1,8}/g;

const OFFICE_ASSET_FILENAME_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

export function officeAssetFilename(ref: string): string {
  return ref.replace(/^(?:(?:\.\.\/)+|\.\/)/, '').replace(/^assets\//, '');
}

export function isOfficeAssetFilename(filename: string): boolean {
  return (
    OFFICE_ASSET_FILENAME_RE.test(filename) &&
    filename.includes('.') &&
    !filename.includes('/')
  );
}

export function collectOfficeAssetRefs(html: string): string[] {
  if (!html) return [];
  return [...new Set(html.match(OFFICE_ASSET_REF_RE) || [])].filter((ref) =>
    isOfficeAssetFilename(officeAssetFilename(ref)),
  );
}

export function rewriteOfficeAssetUrls(
  html: string,
  toUrl: (ref: string) => string,
): string {
  if (!html) return html;
  return html.replace(OFFICE_ASSET_REF_RE, (ref) => toUrl(ref) || ref);
}

export function officeAssetApiPath(
  kind: OfficeKindId,
  slug: string,
  workspaceId: string,
  filename: string,
): string {
  const q = new URLSearchParams({ workspace_id: workspaceId });
  return `/api/${kind}/projects/${encodeURIComponent(slug)}/assets/${encodeURIComponent(filename)}?${q}`;
}

export async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('Failed to read asset'));
    reader.readAsDataURL(blob);
  });
}

export async function inlineOfficeAssets(
  html: string,
  load: (filename: string) => Promise<string | null>,
): Promise<string> {
  const refs = collectOfficeAssetRefs(html);
  if (!refs.length) return html;
  const map = new Map<string, string>();
  await Promise.all(
    refs.map(async (ref) => {
      const filename = officeAssetFilename(ref);
      if (!isOfficeAssetFilename(filename)) return;
      const dataUrl = await load(filename);
      if (dataUrl) map.set(ref, dataUrl);
    }),
  );
  if (!map.size) return html;
  return rewriteOfficeAssetUrls(html, (ref) => map.get(ref) || ref);
}

export async function loadOfficeAssetDataUrl(
  kind: OfficeKindId,
  workspaceId: string,
  slug: string,
  filename: string,
): Promise<string | null> {
  if (!isOfficeAssetFilename(filename)) return null;
  const res = await authFetch(officeAssetApiPath(kind, slug, workspaceId, filename));
  if (!res.ok) return null;
  return blobToDataUrl(await res.blob());
}

/** Resolve ``assets/`` refs for srcDoc preview (Bearer auth cannot ride on img src). */
export async function resolveOfficePreviewAssets(
  kind: OfficeKindId,
  html: string,
  workspaceId: string,
  slug: string,
): Promise<string> {
  if (!html || !workspaceId || !slug || !collectOfficeAssetRefs(html).length) {
    return html;
  }
  return inlineOfficeAssets(html, (filename) =>
    loadOfficeAssetDataUrl(kind, workspaceId, slug, filename),
  );
}

export function downloadOfficeHtml(filename: string, html: string): void {
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

// Bound per kind for the editor pages.
type ResolvePreviewAssets = (html: string, workspaceId: string, slug: string) => Promise<string>;
export const resolveDocumentsPreviewAssets: ResolvePreviewAssets = (...args) => resolveOfficePreviewAssets('documents', ...args);
export const resolveSheetsPreviewAssets: ResolvePreviewAssets = (...args) => resolveOfficePreviewAssets('sheets', ...args);
export const resolveSlidesPreviewAssets: ResolvePreviewAssets = (...args) => resolveOfficePreviewAssets('slides', ...args);
