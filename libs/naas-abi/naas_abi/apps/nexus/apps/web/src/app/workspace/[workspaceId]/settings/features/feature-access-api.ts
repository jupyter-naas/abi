/**
 * The route General › Features calls (`/api/workspaces/{id}/feature-access`): whether the
 * workspace offers each feature. The workspace offer editor (Access › "<W> access") calls it too.
 */
import { authFetch } from '@/stores/auth';
import { targetApiPath } from '@/lib/access-model/target';
import type { FeatureAccessState, FeatureChange } from './feature-access-model';

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

/** `?policy=<id>`: the policy edited, "<W> access" (the workspace's offer) when left out. */
export const policyQuery = (policyId?: string | null) => (policyId ? `?policy=${encodeURIComponent(policyId)}` : '');

export function createFeatureAccessApi(fetcher: Fetcher = authFetch) {
  const path = (workspaceId: string, policyId?: string | null) =>
    `${targetApiPath(workspaceId)}/feature-access${policyQuery(policyId)}`;
  return {
    read: async (workspaceId: string, policyId?: string | null): Promise<FeatureAccessState> => {
      const response = await fetcher(path(workspaceId, policyId));
      if (!response.ok) throw await failure(response, `Could not read who uses the features (HTTP ${response.status}).`);
      return (await response.json()) as FeatureAccessState;
    },
    /** Several features in one step; refused ones come back in `errors`, the rest is saved. */
    save: async (
      workspaceId: string,
      changes: FeatureChange[],
      policyId?: string | null,
    ): Promise<FeatureAccessState> => {
      const response = await fetcher(path(workspaceId, policyId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save (HTTP ${response.status}).`);
      return (await response.json()) as FeatureAccessState;
    },
  };
}

export type FeatureAccessApi = ReturnType<typeof createFeatureAccessApi>;
