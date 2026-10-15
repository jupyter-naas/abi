import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { LayoutApiError } from './layouts-api';

/**
 * Settings → Maps → Access (`/api/maps/permissions`): which workspaces may use
 * a deployment layer / basemap, or a custom one this workspace shares.
 */

export type MapsItemKind = 'layout' | 'basemap';

export interface MapsAccessItem {
  kind: MapsItemKind;
  item_id: string;
  title: string;
  /** '' for a deployment item, else the owning workspace id. */
  owner: string;
  editable: boolean;
  all_workspaces: boolean;
  workspace_ids: string[];
}

export interface MapsPermissionsResponse {
  superadmin: boolean;
  /** Workspaces the current user may grant to. */
  workspaces: { id: string; name: string }[];
  items: MapsAccessItem[];
}

const base = () => `${getApiUrl()}/api/maps/permissions`;
const ws = (workspaceId: string) => `workspace_id=${encodeURIComponent(workspaceId)}`;

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

export const mapsPermissionsApi = {
  list: (workspaceId: string) => request<MapsPermissionsResponse>(`${base()}?${ws(workspaceId)}`),
  update: (
    workspaceId: string,
    kind: MapsItemKind,
    itemId: string,
    grant: { all_workspaces: boolean; workspace_ids: string[] },
  ) =>
    request<MapsAccessItem>(`${base()}/${kind}/${encodeURIComponent(itemId)}?${ws(workspaceId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(grant),
    }),
};

/** One-line summary for the Access column. */
export function accessSummary(
  item: Pick<MapsAccessItem, 'owner' | 'all_workspaces' | 'workspace_ids'>,
  names: ReadonlyMap<string, string>,
): string {
  if (item.all_workspaces) return 'All workspaces';
  const ids = item.workspace_ids.filter((id) => id !== item.owner);
  const label = (id: string) => names.get(id) ?? id;
  if (item.owner) {
    if (ids.length === 0) return 'This workspace only';
    return ids.length === 1 ? `Shared with ${label(ids[0]!)}` : `Shared with ${ids.length} workspaces`;
  }
  if (ids.length === 0) return 'No workspace';
  return ids.length <= 2 ? ids.map(label).join(', ') : `${ids.length} workspaces`;
}
