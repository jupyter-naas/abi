/**
 * Nexus Analytics: where a scope's analytics live in the API, and the query each read
 * sends. Pure, so the URLs are tested without a page.
 *
 * - Organization: `/api/organizations/{org_id}/analytics/...`, filtered by `workspace_id`
 *   (one of the org's workspaces) and `user_id`.
 * - Workspace: `/api/workspaces/{workspace_id}/analytics/...`, filtered by `user_id` only.
 */
import type { AnalyticsGranularity, AnalyticsPeriod, UsersDirectoryEntry } from './types';

export type AnalyticsScope =
  | { kind: 'organization'; orgId: string }
  | { kind: 'workspace'; workspaceId: string };

/** No filter: every in-scope user, or every workspace of the organization. */
export const ALL = 'all';

export interface AnalyticsFilters {
  period: AnalyticsPeriod;
  /** `ALL` or an in-scope member's `user_id`. */
  userId: string;
  /** `ALL` or one of the organization's workspaces; ignored in the workspace scope. */
  workspaceId: string;
}

export const ANALYTICS_PERIODS: { id: AnalyticsPeriod; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: 'this_week', label: 'This week' },
  { id: 'this_month', label: 'This month' },
];

export const DEFAULT_PERIOD: AnalyticsPeriod = 'today';

export function initialAnalyticsFilters(): AnalyticsFilters {
  return { period: DEFAULT_PERIOD, userId: ALL, workspaceId: ALL };
}

/**
 * The filters once `workspaceId` is picked: a picked user who is not a member of that
 * workspace is let go (the user list only offers its members).
 */
export function keepUserInWorkspace(
  filters: AnalyticsFilters,
  workspaceId: string,
  directory: UsersDirectoryEntry[]
): AnalyticsFilters {
  const member =
    filters.userId === ALL ||
    workspaceId === ALL ||
    directory.some((u) => u.user_id === filters.userId && u.workspace_ids.includes(workspaceId));
  return { ...filters, workspaceId, userId: member ? filters.userId : ALL };
}

export function isAnalyticsPeriod(value: unknown): value is AnalyticsPeriod {
  return ANALYTICS_PERIODS.some((p) => p.id === value);
}

/** Today and Yesterday are hourly, This week and This month daily (the server's rule). */
export function periodGranularity(period: AnalyticsPeriod): AnalyticsGranularity {
  return period === 'today' || period === 'yesterday' ? 'hour' : 'day';
}

/** One key per scope: the access cache and the hooks' dependencies. */
export function analyticsScopeKey(scope: AnalyticsScope): string {
  return scope.kind === 'organization' ? `organization:${scope.orgId}` : `workspace:${scope.workspaceId}`;
}

/** Whether the scope spans several workspaces (a Workspaces tab and a workspace filter). */
export function scopeHasWorkspaces(scope: AnalyticsScope): boolean {
  return scope.kind === 'organization';
}

/** `/api/organizations/{id}/analytics` or `/api/workspaces/{id}/analytics`. */
export function analyticsBasePath(scope: AnalyticsScope): string {
  return scope.kind === 'organization'
    ? `/api/organizations/${encodeURIComponent(scope.orgId)}/analytics`
    : `/api/workspaces/${encodeURIComponent(scope.workspaceId)}/analytics`;
}

/** The query of a read: the period, then the filters the scope takes. */
export function analyticsQuery(
  scope: AnalyticsScope,
  filters: AnalyticsFilters,
  extra?: Record<string, string>
): string {
  const params = new URLSearchParams();
  params.set('period', filters.period);
  if (scope.kind === 'organization' && filters.workspaceId && filters.workspaceId !== ALL) {
    params.set('workspace_id', filters.workspaceId);
  }
  if (filters.userId && filters.userId !== ALL) params.set('user_id', filters.userId);
  for (const [key, value] of Object.entries(extra ?? {})) params.set(key, value);
  return params.toString();
}

/**
 * The URL of one read: `path` is the endpoint under the scope's base (`/overview`,
 * `/users/{user_id}`…); without filters, no query (`/access`).
 */
export function analyticsUrl(
  scope: AnalyticsScope,
  path: string,
  filters?: AnalyticsFilters,
  extra?: Record<string, string>
): string {
  const base = `${analyticsBasePath(scope)}${path.startsWith('/') ? path : `/${path}`}`;
  if (!filters) return base;
  const query = analyticsQuery(scope, filters, extra);
  return query ? `${base}?${query}` : base;
}
