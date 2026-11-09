import { authFetch } from '@/stores/auth';

/** A workflow or pipeline of the workspace's modules, as Settings › Workflows lists it. */
export interface WorkflowSetting {
  type: 'workflow' | 'pipeline';
  module_id: string;
  name: string;
  display_name: string;
  description: string;
}

export type WorkflowFilters = { query: string; type: string };

export function workflowKey(item: Pick<WorkflowSetting, 'type' | 'module_id' | 'name'>): string {
  return `${item.type}/${item.module_id}/${item.name}`;
}

/** The rows a search and the type filter keep, by module then name. */
export function filterWorkflows(items: WorkflowSetting[], filters: WorkflowFilters): WorkflowSetting[] {
  const q = filters.query.trim().toLowerCase();
  return items
    .filter((item) => {
      if (filters.type !== 'all' && item.type !== filters.type) return false;
      return (
        !q ||
        [item.display_name, item.name, item.module_id, item.description].some((text) =>
          text.toLowerCase().includes(q)
        )
      );
    })
    .sort(
      (a, b) =>
        a.module_id.localeCompare(b.module_id) ||
        a.display_name.toLowerCase().localeCompare(b.display_name.toLowerCase())
    );
}

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

const settingsUrl = (workspaceId: string) =>
  `/api/workspaces/${encodeURIComponent(workspaceId)}/workflows/settings`;

async function errorOf(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // not JSON
  }
  return fallback;
}

export async function fetchWorkflowSettings(
  workspaceId: string,
  fetcher: Fetcher = authFetch
): Promise<WorkflowSetting[]> {
  const response = await fetcher(settingsUrl(workspaceId));
  if (!response.ok) {
    throw new Error(await errorOf(response, `Could not load the workflows (HTTP ${response.status}).`));
  }
  const body = (await response.json()) as { workflows?: WorkflowSetting[] };
  return body.workflows ?? [];
}
