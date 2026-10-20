import { getApiUrl } from '@/lib/config';
import { ICON_PREFIX } from '@/lib/ontology-icon-library';

export const LOGO_URL_PREDICATE = 'http://ontology.naas.ai/nexus/logo_url';

export function isMaterialIconValue(value: string): boolean {
  return /^material-symbols-light:[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
}

export function isImageHref(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 2048) return false;
  if (trimmed.startsWith('/uploads/') && !trimmed.includes('..') && !trimmed.includes('//', 1)) {
    return true;
  }
  try {
    const url = new URL(trimmed);
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname);
  } catch {
    return false;
  }
}

export function normalizeImageHref(value: string): string | null {
  const trimmed = value.trim();
  return isImageHref(trimmed) ? trimmed : null;
}

export function materialIconName(value: string | null | undefined): string | undefined {
  if (!value?.startsWith(ICON_PREFIX) || !isMaterialIconValue(value)) return undefined;
  return value.slice(ICON_PREFIX.length);
}

export function logoUrlProperties<T extends { predicate_uri: string }>(rows: T[]): T[] {
  return rows.filter(row => /(?:^|[/#])logo_url$/i.test(row.predicate_uri));
}

export async function uploadObjectImage(workspaceId: string, file: File): Promise<string> {
  const { authFetch } = await import('@/stores/auth');
  const form = new FormData();
  form.append('file', file);
  const response = await authFetch(
    `${getApiUrl()}/api/ontology/icons/upload?${new URLSearchParams({ workspace_id: workspaceId })}`,
    { method: 'POST', body: form },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not upload the image.');
  }
  const data: { url?: string } = await response.json();
  if (typeof data.url !== 'string' || !isImageHref(data.url)) {
    throw new Error('The uploaded image could not be read.');
  }
  return data.url;
}
