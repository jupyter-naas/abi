import { z } from 'zod';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

export class ApiError extends Error {
  constructor(public status: number, public body: string, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = 'ApiError';
  }
}

export class ApiSchemaError extends Error {
  constructor(public issues: z.ZodIssue[], public url: string) {
    super(`API response failed schema validation: ${url}`);
    this.name = 'ApiSchemaError';
  }
}

export interface RequestOptions extends RequestInit {
  /** Optional AbortSignal — typically the one TanStack Query passes to `queryFn`. */
  signal?: AbortSignal;
}

/**
 * Issue an authenticated API call and validate the response against a schema.
 * Throws `ApiError` on non-2xx and `ApiSchemaError` on parse failure.
 */
export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  const url = path.startsWith('http') ? path : `${getApiUrl()}${path}`;
  const response = await authFetch(url, options);
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new ApiError(response.status, body);
  }

  const json: unknown = await response.json().catch(() => null);
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    if (process.env.NODE_ENV !== 'production') {
      console.error('[ApiSchemaError]', url, parsed.error.issues);
    }
    throw new ApiSchemaError(parsed.error.issues, url);
  }
  return parsed.data;
}

/** Same as `apiFetch` but skips schema validation (use sparingly, only for fire-and-forget). */
export async function apiFetchRaw(path: string, options: RequestOptions = {}): Promise<Response> {
  const url = path.startsWith('http') ? path : `${getApiUrl()}${path}`;
  const response = await authFetch(url, options);
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new ApiError(response.status, body);
  }
  return response;
}

export function buildQuery(
  params: Record<string, string | number | boolean | string[] | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) search.append(key, String(v));
    } else {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}
