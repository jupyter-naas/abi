import { authFetch } from '@/stores/auth';

/** Module resources the caller may use in a workspace, by their plural, as the API counts them. */
export type ResourceKind = 'agents' | 'apps' | 'workflows' | 'pipelines';

export interface ModuleResources {
  module: string;
  agents: number;
  apps: number;
  workflows: number;
  pipelines: number;
}

/**
 * What the caller may use in a workspace, read-only (`GET /api/workspaces/{id}/resources`):
 * the enabled features they hold (IAM `UseFeature`) and, per module, the agents, apps,
 * workflows and pipelines they may use.
 */
export interface WorkspaceResources {
  organization_id: string | null;
  features: string[];
  modules: ModuleResources[];
  totals: Record<ResourceKind, number>;
  /** Kinds a source did not answer for (discovery, the jobs): their totals may be short. */
  unavailable?: ResourceKind[];
}

type Fetcher = (url: string) => Promise<Response>;

/**
 * The workspace's resources. `denied`: the caller may not read them (401, 403), a stable
 * answer; `failed`: no answer this time (an error, the network), which is never kept.
 */
export type ResourcesAnswer =
  | { kind: 'ok'; resources: WorkspaceResources }
  | { kind: 'denied' }
  | { kind: 'failed' };

export async function fetchWorkspaceResources(
  workspaceId: string,
  fetcher: Fetcher = authFetch
): Promise<ResourcesAnswer> {
  try {
    const response = await fetcher(`/api/workspaces/${encodeURIComponent(workspaceId)}/resources`);
    if (response.status === 401 || response.status === 403) return { kind: 'denied' };
    if (!response.ok) return { kind: 'failed' };
    return { kind: 'ok', resources: (await response.json()) as WorkspaceResources };
  } catch {
    return { kind: 'failed' };
  }
}

/** "2 agents · 1 app": what the caller may use of a module, for General. */
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
