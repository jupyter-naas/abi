import { authFetch } from '@/stores/auth';

/** Module resources a workspace's set may hold, by their plural, as the API counts them. */
export type ResourceKind = 'agents' | 'apps' | 'workflows' | 'pipelines';

export interface ModuleResources {
  module: string;
  agents: number;
  apps: number;
  workflows: number;
  pipelines: number;
}

/**
 * What a workspace has: its effective set (its own within its organization's), read-only
 * (`GET /api/workspaces/{id}/resources`, for its admins). `can_edit_set`: whether the caller
 * changes it, on the organization's Modules & features page.
 */
export interface WorkspaceResources {
  organization_id: string | null;
  can_edit_set: boolean;
  features: string[];
  modules: ModuleResources[];
  totals: Record<ResourceKind, number>;
}

type Fetcher = (url: string) => Promise<Response>;

/** The workspace's resources; null when the caller may not read them (or the call fails). */
export async function fetchWorkspaceResources(
  workspaceId: string,
  fetcher: Fetcher = authFetch
): Promise<WorkspaceResources | null> {
  try {
    const response = await fetcher(`/api/workspaces/${encodeURIComponent(workspaceId)}/resources`);
    if (!response.ok) return null;
    return (await response.json()) as WorkspaceResources;
  } catch {
    return null;
  }
}

/** "2 agents · 1 app": a module's resources in the set, for General. */
export function describeModuleResources(entry: ModuleResources): string {
  const parts: string[] = [];
  const add = (count: number, noun: string) => {
    if (count > 0) parts.push(`${count} ${count === 1 ? noun : `${noun}s`}`);
  };
  add(entry.agents, 'agent');
  add(entry.apps, 'app');
  add(entry.workflows, 'workflow');
  add(entry.pipelines, 'pipeline');
  return parts.join(' · ');
}
