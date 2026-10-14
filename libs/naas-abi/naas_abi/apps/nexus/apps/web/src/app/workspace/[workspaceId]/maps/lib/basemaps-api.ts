import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { LayoutApiError } from './layouts-api';
import type { WorkspaceFeedLayer, WorkspaceMapLayout } from './layouts';

/**
 * Settings → Maps basemaps API (`/api/maps/basemaps`) and the one-read catalog
 * (`/api/maps/catalog`) the Maps store loads per workspace.
 */

export type BasemapCategory = 'standard' | 'organization' | 'custom';

export interface BasemapPalette {
  fill?: string;
  stroke?: string;
  background?: string;
}

/** A named group of countries labelled on a vector basemap (counts per region). */
export interface BasemapRegion {
  id: string;
  name: string;
  color: string;
  /** Label anchor, as a share of the map width / height. */
  label_x: number;
  label_y: number;
  /** Map view when the region is selected. */
  latitude?: number;
  longitude?: number;
  zoom?: number;
  countries: string[];
}

export type BasemapRenderer =
  | {
      kind: 'tile';
      url: string;
      dark_url?: string;
      subdomains?: string[];
      attribution?: string;
      max_zoom?: number;
    }
  | { kind: 'countries'; palette?: BasemapPalette; stroke_width?: number; regions?: BasemapRegion[] }
  | {
      kind: 'geojson';
      feature_collection: GeoJSON.FeatureCollection;
      palette?: BasemapPalette;
      regions?: BasemapRegion[];
    };

/** A basemap as the API returns it. */
export interface WorkspaceBasemap {
  id: string;
  title: string;
  category: BasemapCategory;
  order: number;
  renderer: BasemapRenderer;
  /** Seeded by Nexus or the deployment: renamable and hideable, not deletable. */
  system: boolean;
  preview_content_type: string | null;
  preview_version: number;
  /** Owning workspace when another workspace shares this basemap (read-only here). */
  shared_from?: string;
}

export type BasemapDraft = Pick<WorkspaceBasemap, 'title' | 'category' | 'order' | 'renderer'>;

export interface MapsCatalogResponse {
  /** Feeds. */
  layouts: WorkspaceMapLayout[];
  feed_layers?: WorkspaceFeedLayer[];
  hidden_layouts: string[];
  /** Feeds switched off: every layer drawn from them is hidden. */
  hidden_feeds?: string[];
  layer_colors: Record<string, string>;
  basemaps: WorkspaceBasemap[];
  hidden_basemaps: string[];
  default_basemap_id: string;
  can_edit: boolean;
}

const api = () => `${getApiUrl()}/api/maps`;
const ws = (workspaceId: string) => `workspace_id=${encodeURIComponent(workspaceId)}`;
const basemapUrl = (workspaceId: string, id: string, suffix = '') =>
  `${api()}/basemaps/${encodeURIComponent(id)}${suffix}?${ws(workspaceId)}`;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(url, init);
  if (response.ok) return (await response.json()) as T;
  let detail: unknown;
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  if (detail && typeof detail === 'object' && Array.isArray((detail as { errors?: unknown }).errors)) {
    const errors = (detail as { errors: string[] }).errors;
    throw new LayoutApiError(errors.join('\n'), errors);
  }
  throw new LayoutApiError(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const mapsCatalogApi = {
  get: (workspaceId: string) => request<MapsCatalogResponse>(`${api()}/catalog?${ws(workspaceId)}`),
};

export const basemapsApi = {
  save: (workspaceId: string, id: string, draft: BasemapDraft) =>
    request<WorkspaceBasemap>(basemapUrl(workspaceId, id), json('PUT', draft)),
  remove: (workspaceId: string, id: string) =>
    request<{ message: string }>(basemapUrl(workspaceId, id), { method: 'DELETE' }),
  setHidden: (workspaceId: string, id: string, hidden: boolean) =>
    request<{ hidden: string[] }>(basemapUrl(workspaceId, id, '/visibility'), json('PUT', { hidden })),
  uploadPreview: (workspaceId: string, id: string, file: Blob) =>
    request<WorkspaceBasemap>(basemapUrl(workspaceId, id, '/preview'), {
      method: 'PUT',
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    }),
  /** Authenticated; load through useAuthedImageUrl. `v` busts the cache on upload. */
  previewUrl: (workspaceId: string, id: string, version: number) =>
    `${basemapUrl(workspaceId, id, '/preview')}&v=${version}`,
};

export const BASEMAP_PREVIEW_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'] as const;
export const BASEMAP_PREVIEW_MAX_BYTES = 512_000;
