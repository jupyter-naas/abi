/**
 * Personal API keys: made, listed and revoked through /api/iam/api-keys (see
 * services/api_keys in the API). A key is a credential of its owner for scripts
 * and tools. The API stores only a hash of it, so the secret comes back once,
 * when the key is created, and is never kept here.
 *
 * These routes take a session only: an API key cannot make or revoke keys.
 */
import { authFetch } from '@/stores/auth';

export type ApiKeyStatus = 'active' | 'revoked' | 'expired';
export type ApiKeyAccess = 'full' | 'read' | 'custom';

/** A statement of a key's scope: what it may do, and on what. */
export type ScopeStatement = {
  effect: 'Allow';
  actions: string[];
  resources: string[];
};

export type ApiKey = {
  id: string;
  name: string;
  /** `abi_pk_<id>`: enough to tell keys apart, never the secret. */
  prefix: string;
  created_at: string | null;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  status: ApiKeyStatus;
  access: ApiKeyAccess;
  scope: ScopeStatement[] | null;
};

export type CreatedApiKey = {
  key: ApiKey;
  /** The key itself. Shown once. */
  secret: string;
};

export type CreateApiKeyInput = {
  name: string;
  expiresInDays: number;
  access: ApiKeyAccess;
  /** Required for `custom`. */
  scope?: ScopeStatement[];
};

export const MAX_ACTIVE_KEYS = 5;
export const EXPIRY_CHOICES = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 365, label: '1 year' },
] as const;
export const DEFAULT_EXPIRY_DAYS = 365;
export const NAME_MAX_LENGTH = 100;

export const ACCESS_LABELS: Record<ApiKeyAccess, string> = {
  full: 'Full access',
  read: 'Read only',
  custom: 'Custom',
};

export const STATUS_LABELS: Record<ApiKeyStatus, string> = {
  active: 'Active',
  revoked: 'Revoked',
  expired: 'Expired',
};

export const CUSTOM_SCOPE_EXAMPLE = JSON.stringify(
  [{ effect: 'Allow', actions: ['triple_store:Query'], resources: ['*'] }],
  null,
  2,
);

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

/** What the API said went wrong, in words for the user. */
export class ApiKeysError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiKeysError';
    this.status = status;
  }
}

async function failure(response: Response, fallback: string): Promise<ApiKeysError> {
  let detail = '';
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') detail = body.detail;
    else if (Array.isArray(body?.detail) && body.detail[0]?.msg) detail = String(body.detail[0].msg);
  } catch {
    // no JSON body
  }
  if (response.status === 409) {
    return new ApiKeysError(
      detail || `You already have ${MAX_ACTIVE_KEYS} active keys: revoke one first.`,
      409,
    );
  }
  if (response.status === 503) {
    return new ApiKeysError('API keys are not available on this server.', 503);
  }
  return new ApiKeysError(detail || fallback, response.status);
}

export async function listApiKeys(fetcher: Fetcher = authFetch): Promise<ApiKey[]> {
  const response = await fetcher('/api/iam/api-keys');
  if (!response.ok) throw await failure(response, 'Could not load your API keys.');
  return (await response.json()) as ApiKey[];
}

export async function createApiKey(
  input: CreateApiKeyInput,
  fetcher: Fetcher = authFetch,
): Promise<CreatedApiKey> {
  const body: Record<string, unknown> = {
    name: input.name.trim(),
    expires_in_days: input.expiresInDays,
    access: input.access,
  };
  if (input.access === 'custom') body.scope = input.scope;
  const response = await fetcher('/api/iam/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await failure(response, 'Could not create the API key.');
  return (await response.json()) as CreatedApiKey;
}

export async function revokeApiKey(id: string, fetcher: Fetcher = authFetch): Promise<ApiKey> {
  const response = await fetcher(`/api/iam/api-keys/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw await failure(response, 'Could not revoke the API key.');
  return (await response.json()) as ApiKey;
}

export type ScopeParse =
  | { ok: true; scope: ScopeStatement[] }
  | { ok: false; error: string };

/** The statements a user typed, checked before they are sent: a JSON array of
 *  `{effect: 'Allow', actions: string[], resources: string[]}`. */
export function parseScopeJson(text: string): ScopeParse {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return { ok: false, error: 'The statements are not valid JSON.' };
  }
  if (!Array.isArray(value) || value.length === 0) {
    return { ok: false, error: 'Give a JSON array with at least one statement.' };
  }
  const scope: ScopeStatement[] = [];
  for (const [index, item] of value.entries()) {
    const where = `Statement ${index + 1}`;
    if (typeof item !== 'object' || item === null || Array.isArray(item)) {
      return { ok: false, error: `${where} must be an object.` };
    }
    const statement = item as Record<string, unknown>;
    if (statement.effect !== 'Allow') {
      return { ok: false, error: `${where}: effect must be "Allow" (a scope only narrows).` };
    }
    for (const field of ['actions', 'resources'] as const) {
      const list = statement[field];
      if (
        !Array.isArray(list) ||
        list.length === 0 ||
        !list.every((entry) => typeof entry === 'string' && entry.length > 0)
      ) {
        return { ok: false, error: `${where}: ${field} must be a list of non-empty strings.` };
      }
    }
    scope.push({
      effect: 'Allow',
      actions: statement.actions as string[],
      resources: statement.resources as string[],
    });
  }
  return { ok: true, scope };
}

export function activeKeyCount(keys: ApiKey[]): number {
  return keys.filter((key) => key.status === 'active').length;
}

/** A date for a table cell: the day, or a word when there is none. */
export function formatKeyDate(value: string | null, none: string): string {
  if (!value) return none;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return none;
  return date.toLocaleDateString();
}

/** How to use a key: the header form and the token endpoint. The key shown is
 *  the one just made, or a placeholder. */
export function usageExamples(secret: string, apiBase: string): { bearer: string; token: string } {
  const base = apiBase.replace(/\/+$/, '');
  return {
    bearer: [`curl -H "Authorization: Bearer ${secret}" \\`, `  ${base}/api/workspaces`].join('\n'),
    token: [
      `curl -X POST ${base}/api/iam/token \\`,
      `  -d grant_type=client_credentials \\`,
      `  -d client_secret=${secret}`,
    ].join('\n'),
  };
}
