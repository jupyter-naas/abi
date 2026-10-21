import { authFetch, useAuthStore } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

/** The slice of organization branding the workspace shell applies. */
export interface OrgShellBranding {
  borderRadius: string;
  defaultTheme?: 'light' | 'dark' | 'system';
}

const THEMES = new Set(['light', 'dark', 'system']);

// Keyed by API base + user + org: a cached org never crosses an auth boundary.
const cache = new Map<string, OrgShellBranding>();
const pending = new Map<string, Promise<OrgShellBranding | null>>();
// Bumped on every clear so a request started before it cannot refill the cache.
let generation = 0;

const cacheKey = (orgId: string) =>
  JSON.stringify([getApiUrl(), useAuthStore.getState().user?.id ?? null, orgId]);

export function clearOrgBrandingCache(): void {
  generation += 1;
  cache.clear();
  pending.clear();
}

/** Drop one organization after its branding is edited. */
export function invalidateOrgBranding(orgId: string): void {
  generation += 1;
  for (const map of [cache, pending]) {
    for (const key of map.keys()) {
      if ((JSON.parse(key) as string[])[2] === orgId) map.delete(key);
    }
  }
}

useAuthStore.subscribe((state, previous) => {
  if (state.user?.id !== previous.user?.id || Boolean(state.token) !== Boolean(previous.token)) {
    clearOrgBrandingCache();
  }
});
if (typeof window !== 'undefined') {
  window.addEventListener('org-branding-updated', clearOrgBrandingCache);
}

export function parseOrgShellBranding(data: Record<string, unknown>): OrgShellBranding {
  // Allow "0": only fall back when the radius is absent.
  const radius = data.loginBorderRadius ?? data.login_border_radius;
  const theme = data.defaultTheme || data.default_theme;
  return {
    borderRadius: radius == null ? '0' : String(radius),
    defaultTheme: typeof theme === 'string' && THEMES.has(theme)
      ? (theme as OrgShellBranding['defaultTheme'])
      : undefined,
  };
}

/** Cached, deduplicated org branding; resolves null on failure (never cached). */
export function loadOrgBranding(orgId: string): Promise<OrgShellBranding | null> {
  const key = cacheKey(orgId);
  const saved = cache.get(key);
  if (saved) return Promise.resolve(saved);
  const inflight = pending.get(key);
  if (inflight) return inflight;

  const request = fetchOrgBranding(orgId, key, generation);
  pending.set(key, request);
  void request.finally(() => {
    if (pending.get(key) === request) pending.delete(key);
  });
  return request;
}

async function fetchOrgBranding(
  orgId: string,
  key: string,
  started: number,
): Promise<OrgShellBranding | null> {
  try {
    const response = await authFetch(`/api/organizations/${orgId}`);
    if (!response.ok) return null;
    const branding = parseOrgShellBranding(await response.json());
    if (generation === started) cache.set(key, branding);
    return branding;
  } catch (error) {
    console.error('Failed to fetch org branding:', error);
    return null;
  }
}

/**
 * The workspace's organization id: the loaded record when it has one, else a
 * workspace-details lookup (records persisted before organizationId existed).
 */
export async function resolveWorkspaceOrgId(
  workspaceId: string,
  organizationId?: string,
): Promise<string | null> {
  if (organizationId) return organizationId;
  try {
    const response = await authFetch(`/api/workspaces/${workspaceId}`);
    if (!response.ok) return null;
    const data = await response.json();
    return data.organization_id || null;
  } catch (error) {
    console.error('Failed to resolve workspace organization:', error);
    return null;
  }
}
