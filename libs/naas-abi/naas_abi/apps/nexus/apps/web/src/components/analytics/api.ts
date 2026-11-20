/**
 * Nexus Analytics client: reads through `authFetch` (the API base URL, the session
 * cookie and CSRF), like every other `/api/organizations/...` and `/api/workspaces/...`
 * read of the settings pages.
 */
import { analyticsUrl, type AnalyticsScope } from './scope';
import type { AnalyticsAccess } from './types';

export type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

/** A refused or failed read, with its HTTP status (403: no right, 404: out of scope). */
export class AnalyticsHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'AnalyticsHttpError';
    this.status = status;
  }
}

export async function readAnalyticsJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = '';
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // A non-JSON error body stays a status-only message.
    }
    throw new AnalyticsHttpError(
      response.status,
      detail ? `${detail} (${response.status})` : `Request failed (${response.status})`
    );
  }
  return (await response.json()) as T;
}

/** What a caller who may read nothing gets: no entry, no page. */
export const NO_ANALYTICS_ACCESS: AnalyticsAccess = {
  can_read: false,
  can_read_conversations: false,
  timezone: 'UTC',
};

/** The answer of `GET /access`, made safe: a missing flag is false, a missing timezone UTC. */
export function analyticsAccessFrom(data: unknown): AnalyticsAccess {
  const body = (data && typeof data === 'object' ? data : {}) as Partial<Record<keyof AnalyticsAccess, unknown>>;
  return {
    can_read: body.can_read === true,
    can_read_conversations: body.can_read_conversations === true,
    timezone: typeof body.timezone === 'string' && body.timezone ? body.timezone : 'UTC',
  };
}

/**
 * `GET {base}/analytics/access`. The API answers false flags rather than 403; a 401,
 * 403 or 404 (an API without the route, a scope gone) is read as no access too. Any
 * other failure throws, so a cache can keep its last answer.
 */
export async function fetchAnalyticsAccess(scope: AnalyticsScope, fetcher: Fetcher): Promise<AnalyticsAccess> {
  const response = await fetcher(analyticsUrl(scope, '/access'));
  if (response.status === 401 || response.status === 403 || response.status === 404) return NO_ANALYTICS_ACCESS;
  if (!response.ok) throw new AnalyticsHttpError(response.status, `Request failed (${response.status})`);
  return analyticsAccessFrom(await response.json());
}
