/**
 * A workspace's offer: what "<W> access" lists (S3, #1586). `GET` / `PUT
 * /api/workspaces/{id}/offer` cover its agents, apps, workflows and pipelines, by module (a
 * shared module offered whole is `<module>/*`); its features are General › Features'
 * (`/feature-access`, Everyone or Nobody). Everyone in "<W> workspace" reaches what it offers;
 * their level decides what they may do with it.
 */
import { authFetch } from '@/stores/auth';

export type OfferKind = 'agents' | 'apps' | 'workflows' | 'pipelines';

export const OFFER_KINDS: { kind: OfferKind; label: string; type: string }[] = [
  { kind: 'agents', label: 'Agents', type: 'agent' },
  { kind: 'apps', label: 'Apps', type: 'app' },
  { kind: 'workflows', label: 'Workflows', type: 'workflow' },
  { kind: 'pipelines', label: 'Pipelines', type: 'pipeline' },
];

/** The item name that offers a module whole. */
export const WHOLE_MODULE = '*';

export type OfferItem = { module: string; name: string };

export type OfferState = {
  workspace_id: string;
  scope: string;
  /** "<W> access"; null for a workspace that has none yet. */
  access_policy: { id: string; name: string; owner_scope: string } | null;
  /** IAM lets the caller update "<W> access". */
  editable: boolean;
  whole_module: string;
  offered: Record<OfferKind, OfferItem[]>;
};

export type OfferChange = { kind: OfferKind; module: string; name: string; offered: boolean };

export class OfferError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'OfferError';
    this.status = status;
  }
}

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

async function failure(response: Response, fallback: string): Promise<OfferError> {
  let detail = '';
  try {
    const raw = (await response.json())?.detail;
    if (typeof raw === 'string') detail = raw;
    else if (Array.isArray(raw) && raw[0]?.msg) detail = String(raw[0].msg);
  } catch {
    // no JSON body
  }
  if (!detail && response.status === 403) detail = 'You may not change what this workspace offers.';
  return new OfferError(detail || fallback, response.status);
}

export function createOfferApi(fetcher: Fetcher = authFetch) {
  const path = (workspaceId: string) => `/api/workspaces/${encodeURIComponent(workspaceId)}/offer`;
  return {
    read: async (workspaceId: string): Promise<OfferState> => {
      const response = await fetcher(path(workspaceId));
      if (!response.ok) throw await failure(response, `Could not read the workspace's offer (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
    /** One write of "<W> access": every change or none (403, 422 name why). */
    save: async (workspaceId: string, changes: OfferChange[]): Promise<OfferState> => {
      const response = await fetcher(path(workspaceId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes }),
      });
      if (!response.ok) throw await failure(response, `Could not save the offer (HTTP ${response.status}).`);
      return (await response.json()) as OfferState;
    },
  };
}

export type OfferApi = ReturnType<typeof createOfferApi>;
