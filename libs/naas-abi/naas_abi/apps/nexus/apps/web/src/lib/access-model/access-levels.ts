/**
 * Access levels (`GET|PUT /api/workspaces/{id}/access-levels?kind=&policy=`): how far people go
 * with each Nexus feature (`kind=feature`, its `nexus:` actions) or core service (`kind=service`,
 * an engine service's actions: the triple store's graphs, object storage...). In "<W> access" a
 * level is a cap for everyone in the workspace (`mode: 'cap'`, Denies above it); in another policy
 * what it grants its holders (`mode: 'grant'`, Allows up to it).
 */
import { authFetch } from '@/stores/auth';
import { targetApiPath } from './target';

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export type AccessLevel = 'none' | 'read' | 'write' | 'admin';
export type LevelKind = 'feature' | 'service';

export const LEVEL_LABELS: Record<AccessLevel, string> = {
  none: 'None',
  read: 'Read',
  write: 'Write',
  admin: 'Admin',
};

export type LevelRow = {
  /** `feature:<key>` or `service:<service>`. */
  key: string;
  kind: LevelKind;
  /** The feature key or the service name. */
  name: string;
  label: string;
  level: AccessLevel;
  /** The levels it may take, lowest first. */
  choices: AccessLevel[];
  /** Its actions by the level that brings them (`read`: list and read). */
  actions: Partial<Record<'read' | 'write' | 'admin', string[]>>;
};

type PolicyRef = { id: string; name: string; owner_scope: string };

export type LevelsState = {
  workspace_id: string;
  kind: LevelKind;
  /** `cap` in "<W> access" (everyone, admins included), `grant` in another policy. */
  mode: 'cap' | 'grant';
  access_policy: PolicyRef | null;
  policy: PolicyRef | null;
  policies: PolicyRef[];
  editable: boolean;
  reason: string | null;
  rows: LevelRow[];
};

export class AccessLevelsError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'AccessLevelsError';
    this.status = status;
  }
}

async function failure(response: Response, fallback: string): Promise<AccessLevelsError> {
  let detail = '';
  try {
    const raw = (await response.json())?.detail;
    if (typeof raw === 'string') detail = raw;
    else if (Array.isArray(raw) && raw[0]?.msg) detail = String(raw[0].msg);
  } catch {
    // no JSON body
  }
  return new AccessLevelsError(detail || fallback, response.status);
}

/** The hint of a level, as the policy edited reads it. */
export function levelHint(level: AccessLevel, mode: 'cap' | 'grant'): string {
  if (mode === 'cap') {
    if (level === 'none') return 'Denied: nobody under this policy uses it, admins included, whatever another policy grants.';
    if (level === 'admin') return 'No cap: each person’s level decides.';
    return `Nobody in the workspace goes beyond ${LEVEL_LABELS[level]}, admins included; each person’s level still applies below.`;
  }
  return level === 'none' ? 'This policy grants nothing of it.' : `Whoever holds this policy goes up to ${LEVEL_LABELS[level]}, within the workspace’s offer.`;
}

export function createAccessLevelsApi(fetcher: Fetcher = authFetch) {
  const path = (workspaceId: string, kind: LevelKind, policyId?: string | null) =>
    `${targetApiPath(workspaceId)}/access-levels?kind=${kind}${
      policyId ? `&policy=${encodeURIComponent(policyId)}` : ''
    }`;
  return {
    read: async (workspaceId: string, kind: LevelKind, policyId?: string | null): Promise<LevelsState> => {
      const response = await fetcher(path(workspaceId, kind, policyId));
      if (!response.ok) throw await failure(response, `Could not read the access levels (HTTP ${response.status}).`);
      return (await response.json()) as LevelsState;
    },
    /** One write of the policy edited: every change or none (403, 422 name why). */
    save: async (
      workspaceId: string,
      kind: LevelKind,
      changes: Record<string, AccessLevel>,
      policyId?: string | null,
    ): Promise<LevelsState> => {
      const response = await fetcher(path(workspaceId, kind, policyId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save the access levels (HTTP ${response.status}).`);
      return (await response.json()) as LevelsState;
    },
  };
}

export type AccessLevelsApi = ReturnType<typeof createAccessLevelsApi>;
