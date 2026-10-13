import { describe, expect, it } from 'vitest';
import { averageLatency, groupRemoteModules, moduleTone, serviceTone, unavailableSources } from './system-model';
import type { MicroServiceInstance, RemoteModuleInstance } from './system-types';

const job = { name: 'digest', description: '', triggers: ['every 10m'], max_concurrency: 1, max_attempts: 1, timeout_seconds: 60 };

function instance(overrides: Partial<RemoteModuleInstance>): RemoteModuleInstance {
  return {
    module_id: 'ops.researcher',
    instance_id: 'r-1',
    package_version: '0.1.0',
    contract_major: 1,
    status: 'READY',
    expires_at: 2000,
    agents: ['Researcher'],
    jobs: [job],
    ...overrides,
  };
}

describe('system model', () => {
  it('groups replicas of a module and keeps the soonest lease expiry', () => {
    const groups = groupRemoteModules([
      instance({ instance_id: 'r-2', status: 'STARTING', expires_at: 1500 }),
      instance({}),
      instance({ module_id: 'ops.orchestrator', instance_id: 'o-1', agents: ['Orchestrator'], jobs: [] }),
    ]);

    expect(groups.map((g) => g.module_id)).toEqual(['ops.orchestrator', 'ops.researcher']);
    const researcher = groups[1];
    expect(researcher.instances.map((i) => i.instance_id)).toEqual(['r-1', 'r-2']);
    expect(researcher.statuses).toEqual({ READY: 1, STARTING: 1 });
    expect(researcher.soonestExpiry).toBe(1500);
    expect(researcher.agents).toEqual(['Researcher']);
    expect(researcher.jobs.map((j) => j.name)).toEqual(['digest']);
    expect(researcher.versions).toEqual(['0.1.0']);
  });

  it('lists only unavailable sources, with labels', () => {
    expect(
      unavailableSources({
        nats: { available: true, reason: '' },
        nats_monitor: { available: false, reason: 'nats.monitoring_url is not configured' },
      }),
    ).toEqual([
      { source: 'nats_monitor', label: 'NATS monitoring', reason: 'nats.monitoring_url is not configured' },
    ]);
  });

  it('maps statuses to tones', () => {
    expect(serviceTone('serving')).toBe('ok');
    expect(serviceTone('silent')).toBe('warn');
    expect(serviceTone('not_exposed')).toBe('muted');
    expect(moduleTone('READY')).toBe('ok');
    expect(moduleTone('STARTING')).toBe('warn');
    expect(moduleTone('DEGRADED')).toBe('warn');
    expect(moduleTone('DRAINING')).toBe('muted');
    expect(moduleTone('UNAVAILABLE')).toBe('error');
  });
});

describe('averageLatency', () => {
  const endpoint = (requests: number, average_ms: number) => ({
    name: 'get', subject: 'abi.svc.document.v1.get', requests, errors: 0, average_ms, last_error: '',
  });
  const micro = (endpoints: ReturnType<typeof endpoint>[]): MicroServiceInstance => ({
    name: 'document', instance_id: 'd', version: '1', started: '', endpoints,
    requests: endpoints.reduce((n, e) => n + e.requests, 0), errors: 0,
  });

  it('weights each endpoint by its requests across instances', () => {
    expect(averageLatency([micro([endpoint(3, 2), endpoint(1, 6)]), micro([endpoint(0, 0)])])).toBe(3);
  });

  it('is zero without requests', () => {
    expect(averageLatency([micro([endpoint(0, 0)])])).toBe(0);
  });
});
