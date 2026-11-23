/**
 * The route General › Platform Files calls (`/api/workspaces/{id}/platform-files`): whether the
 * workspace gives its people Platform Files, and whether the caller (a platform admin) may change it.
 */
import { authFetch } from '@/stores/auth';

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export type PlatformFilesMode = 'off' | 'read' | 'write';

export interface PlatformFilesState {
  workspace_id: string;
  mode: PlatformFilesMode;
  can_change: boolean;
}

export class PlatformFilesError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'PlatformFilesError';
    this.status = status;
  }
}

async function failure(response: Response, fallback: string): Promise<PlatformFilesError> {
  let detail = '';
  try {
    const raw = (await response.json())?.detail;
    if (typeof raw === 'string') detail = raw;
  } catch {
    // no JSON body
  }
  return new PlatformFilesError(detail || fallback, response.status);
}

export function createPlatformFilesApi(fetcher: Fetcher = authFetch) {
  const path = (workspaceId: string) => `/api/workspaces/${encodeURIComponent(workspaceId)}/platform-files`;
  return {
    read: async (workspaceId: string): Promise<PlatformFilesState> => {
      const response = await fetcher(path(workspaceId));
      if (!response.ok) throw await failure(response, `Could not read Platform Files (HTTP ${response.status}).`);
      return (await response.json()) as PlatformFilesState;
    },
    save: async (workspaceId: string, mode: PlatformFilesMode): Promise<PlatformFilesState> => {
      const response = await fetcher(path(workspaceId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (!response.ok) throw await failure(response, `Could not save (HTTP ${response.status}).`);
      return (await response.json()) as PlatformFilesState;
    },
  };
}

export type PlatformFilesApi = ReturnType<typeof createPlatformFilesApi>;
