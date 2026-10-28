import { sourceLabel } from './system-format';
import type {
  JobSummary,
  KernelServiceStatus,
  MicroServiceInstance,
  RemoteModuleInstance,
  SourceStatus,
} from './system-types';

export type Tone = 'ok' | 'warn' | 'error' | 'muted';

export interface RemoteModuleGroup {
  module_id: string;
  instances: RemoteModuleInstance[];
  statuses: Record<string, number>;
  versions: string[];
  agents: string[];
  jobs: JobSummary[];
  soonestExpiry: number;
}

/** Replicas of one module side by side; they declare identical agents and jobs. */
export function groupRemoteModules(instances: RemoteModuleInstance[]): RemoteModuleGroup[] {
  const groups = new Map<string, RemoteModuleGroup>();
  for (const instance of [...instances].sort((a, b) => a.instance_id.localeCompare(b.instance_id))) {
    const group = groups.get(instance.module_id) ?? {
      module_id: instance.module_id,
      instances: [],
      statuses: {},
      versions: [],
      agents: instance.agents,
      jobs: instance.jobs,
      soonestExpiry: instance.expires_at,
    };
    group.instances.push(instance);
    group.statuses[instance.status] = (group.statuses[instance.status] ?? 0) + 1;
    if (!group.versions.includes(instance.package_version)) group.versions.push(instance.package_version);
    group.soonestExpiry = Math.min(group.soonestExpiry, instance.expires_at);
    groups.set(instance.module_id, group);
  }
  return [...groups.values()].sort((a, b) => a.module_id.localeCompare(b.module_id));
}

export function unavailableSources(
  sources: Record<string, SourceStatus>,
): { source: string; label: string; reason: string }[] {
  return Object.entries(sources)
    .filter(([, status]) => !status.available)
    .map(([source, status]) => ({ source, label: sourceLabel(source), reason: status.reason }));
}

export function serviceTone(status: KernelServiceStatus): Tone {
  if (status === 'serving') return 'ok';
  if (status === 'silent') return 'warn';
  return 'muted';
}

export function moduleTone(status: string): Tone {
  if (status === 'READY') return 'ok';
  if (status === 'STARTING' || status === 'DEGRADED') return 'warn';
  if (status === 'DRAINING' || status === 'STOPPED') return 'muted';
  return 'error';
}

/** Mean latency over every request the instances answered. */
export function averageLatency(instances: MicroServiceInstance[]): number {
  let requests = 0;
  let total = 0;
  for (const instance of instances) {
    for (const endpoint of instance.endpoints) {
      requests += endpoint.requests;
      total += endpoint.average_ms * endpoint.requests;
    }
  }
  return requests ? Math.round((total / requests) * 100) / 100 : 0;
}
