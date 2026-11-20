/**
 * The routes General › Features calls: its own (`/api/workspaces/{id}/feature-access`), and who
 * Only… may name (the workspace's members, its groups as IAM lists them to the caller).
 */
import { toMembers } from '@/components/access/access-directory';
import { createIamAdminApi } from '@/lib/iam-admin/api';
import { authFetch } from '@/stores/auth';
import type { FeatureAccessState, FeatureChange, PrincipalRef } from './feature-access-model';

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export class FeatureAccessError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'FeatureAccessError';
    this.status = status;
  }
}

async function failure(response: Response, fallback: string): Promise<FeatureAccessError> {
  let detail = '';
  try {
    const raw = (await response.json())?.detail;
    if (typeof raw === 'string') detail = raw;
    else if (Array.isArray(raw) && raw[0]?.msg) detail = String(raw[0].msg);
  } catch {
    // no JSON body
  }
  if (!detail && response.status === 403) detail = 'You may not see who uses the features here.';
  return new FeatureAccessError(detail || fallback, response.status);
}

export function createFeatureAccessApi(fetcher: Fetcher = authFetch) {
  const path = (workspaceId: string) => `/api/workspaces/${encodeURIComponent(workspaceId)}/feature-access`;
  const iam = createIamAdminApi(fetcher);
  return {
    read: async (workspaceId: string): Promise<FeatureAccessState> => {
      const response = await fetcher(path(workspaceId));
      if (!response.ok) throw await failure(response, `Could not read who uses the features (HTTP ${response.status}).`);
      return (await response.json()) as FeatureAccessState;
    },
    /** Several features in one step; refused ones come back in `errors`, the rest is saved. */
    save: async (workspaceId: string, changes: FeatureChange[]): Promise<FeatureAccessState> => {
      const response = await fetcher(path(workspaceId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save (HTTP ${response.status}).`);
      return (await response.json()) as FeatureAccessState;
    },
    /** The members (by their IAM id) and groups of the workspace; what cannot be read is left out. */
    candidates: async (workspaceId: string, scope: string): Promise<PrincipalRef[]> => {
      const [members, groups] = await Promise.all([
        fetcher(`/api/workspaces/${encodeURIComponent(workspaceId)}/members`)
          .then(async (response) => (response.ok ? toMembers(await response.json()) : []))
          .catch(() => []),
        iam
          .listGroups(scope)
          .then((page) => page.items)
          .catch(() => []),
      ]);
      return [
        ...members.flatMap((m) =>
          m.principalId ? [{ id: m.principalId, kind: 'user', name: m.name || m.email || m.principalId }] : [],
        ),
        ...groups.map((g) => ({ id: g.id, kind: 'group', name: g.name || g.id })),
      ];
    },
  };
}

export type FeatureAccessApi = ReturnType<typeof createFeatureAccessApi>;
