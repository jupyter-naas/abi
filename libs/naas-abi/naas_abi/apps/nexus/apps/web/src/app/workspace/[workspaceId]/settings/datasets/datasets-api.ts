/** The route Settings › Datasets calls: `/api/workspaces/{id}/offer/datasets` (or an organization's). */
import { authFetch } from '@/stores/auth';
import { targetApiPath } from '@/lib/access-model/target';
import type { DatasetsState } from './datasets-model';

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export class DatasetsOfferError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'DatasetsOfferError';
    this.status = status;
  }
}

async function failure(response: Response, fallback: string): Promise<DatasetsOfferError> {
  let detail = '';
  try {
    const raw = (await response.json())?.detail;
    if (typeof raw === 'string') detail = raw;
    else if (Array.isArray(raw) && raw[0]?.msg) detail = String(raw[0].msg);
  } catch {
    // no JSON body
  }
  return new DatasetsOfferError(detail || fallback, response.status);
}

export function createDatasetsOfferApi(fetcher: Fetcher = authFetch) {
  // `?policy=`: another policy of the workspace, picked in the Settings column.
  const path = (target: string, policyId?: string | null) =>
    `${targetApiPath(target)}/offer/datasets${policyId ? `?policy=${encodeURIComponent(policyId)}` : ''}`;
  return {
    read: async (target: string, policyId?: string | null): Promise<DatasetsState> => {
      const response = await fetcher(path(target, policyId));
      if (!response.ok) throw await failure(response, `Could not read the datasets (HTTP ${response.status}).`);
      return (await response.json()) as DatasetsState;
    },
    /** `{namespace: offered}`, in one write; answers the datasets after. */
    save: async (target: string, changes: Record<string, boolean>, policyId?: string | null): Promise<DatasetsState> => {
      const response = await fetcher(path(target, policyId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save (HTTP ${response.status}).`);
      return (await response.json()) as DatasetsState;
    },
  };
}

export type DatasetsOfferApi = ReturnType<typeof createDatasetsOfferApi>;
