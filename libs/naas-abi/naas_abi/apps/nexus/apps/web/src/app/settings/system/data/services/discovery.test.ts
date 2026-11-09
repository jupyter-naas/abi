// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { discoveryView, leaseLabel, leaseTone, statusMix } from './discovery';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const render = async (node: ReactNode) => {
  mounted = await mount(() => createElement('div', null, node), {});
  return mounted.host;
};

const soon = (seconds: number) => new Date(Date.now() + seconds * 1000).toISOString();

const moduleEntry: ResourceEntry = {
  id: 'ops.researcher',
  name: 'ops.researcher',
  kind: 'container',
  actions: [],
  size: null,
  modified: null,
  attributes: {
    instances: '3',
    status: 'READY 2, STARTING 1',
    agents: 'Researcher',
    jobs: 'digest',
    versions: '0.1.0',
    lease_expires_at: soon(600),
  },
};

const detail: ResourceDetail = {
  entry: {
    id: 'ops.researcher/abc123',
    name: 'abc123',
    kind: 'item',
    actions: ['read', 'delete'],
    size: null,
    modified: null,
    attributes: { status: 'READY', version: '0.1.0', lease_expires_at: soon(30) },
  },
  content: { encoding: 'text', text: '{"module_id": "ops.researcher"}', size: 30, truncated: false },
  view: {
    type: 'status',
    phase: 'READY',
    fields: { Module: 'ops.researcher', Version: '0.1.0', 'Lease expires': 'x' },
    lease_expires_at: soon(30),
    agents: [{ name: 'Researcher', description: 'Finds things', capabilities: ['agent.invoke.v1'] }],
    jobs: [{ name: 'digest', triggers: ['every 10m'], max_concurrency: 1, max_attempts: 3, timeout_seconds: 60 }],
    dependencies: [{ module_id: 'store', contract_major: 1 }],
  },
};

describe('discovery view', () => {
  it('reads the status mix and lease urgency', () => {
    expect(statusMix('READY 2, STARTING 1')).toEqual([
      ['READY', 2],
      ['STARTING', 1],
    ]);
    expect(leaseTone(600)).toBe('success');
    expect(leaseTone(30)).toBe('warn');
    expect(leaseTone(-5)).toBe('danger');
    expect(leaseLabel(-90)).toBe('expired 2 min ago');
    expect(leaseLabel(null)).toBe('—');
  });

  it('shows modules as cards with status pills, agents and jobs', async () => {
    const level = discoveryView.level!(0, '');
    const host = await render(level.card!(moduleEntry));

    expect(level.layout).toBe('cards');
    expect(host.textContent).toContain('2 ready');
    expect(host.textContent).toContain('1 starting');
    expect(host.textContent).toContain('Researcher');
    expect(host.textContent).toContain('digest');
  });

  it('counts down an instance lease in its column', async () => {
    const lease = discoveryView.level!(1, 'ops.researcher').columns!.find((c) => c.id === 'lease')!;
    const host = await render(lease.render(detail.entry));

    expect(host.querySelector('.data-discovery-lease-warn')?.textContent).toMatch(/renews within \d+ s/);
  });

  it('previews an instance with agents, jobs and dependencies', async () => {
    const host = await render(discoveryView.preview!(detail, {}));

    expect(host.textContent).toContain('Finds things');
    expect(host.textContent).toContain('every 10m');
    expect(host.textContent).toContain('3 attempts');
    expect(host.textContent).toContain('store v1');
    expect(host.textContent).not.toContain('Lease expires');
  });

  it('names modules and instances, and explains eviction', () => {
    expect(discoveryView.nounFor!(moduleEntry, 0).one).toBe('module');
    expect(discoveryView.nounFor!(detail.entry, 1).one).toBe('instance');
    expect(discoveryView.deleteWarning!(detail.entry)).toContain('registers again under the same instance id');
  });
});
