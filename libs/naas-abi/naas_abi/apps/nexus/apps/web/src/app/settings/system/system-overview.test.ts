// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { natsServer } from './system-fixtures';
import { mount, type Mounted } from './system-render';
import { SystemOverview } from './system-overview';
import type { Overview } from './system-types';

const overview: Overview = {
  sources: {
    engine: { available: true, reason: '' },
    nats: { available: true, reason: '' },
    discovery: { available: true, reason: '' },
    nats_monitor: { available: false, reason: 'nats.monitoring_url is not configured' },
  },
  kernel_services: 15,
  serving_services: 13,
  service_instances: 14,
  requests: 12_345,
  engine_modules: 9,
  remote_modules: { READY: 2, STARTING: 1 },
  server: natsServer,
  jetstream_streams: 3,
  jetstream_consumers: 4,
  jetstream_messages: 10,
  telemetry: { enabled: true, service_name: 'zen-engine', ui_url: 'http://localhost:16686' },
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('SystemOverview', () => {
  it('summarises services, modules and NATS', async () => {
    mounted = await mount(SystemOverview, { overview });
    const text = mounted.host.textContent ?? '';

    expect(text).toContain('13 / 15');
    expect(text).toContain('12.3k');
    expect(text).toContain('2 ready of 3');
    expect(text).toContain('2.14.7');
  });

  it('lists every source with its state', async () => {
    mounted = await mount(SystemOverview, { overview });
    const rows = [...mounted.host.querySelectorAll('[data-source]')];

    expect(rows.map((r) => r.getAttribute('data-source'))).toEqual(['engine', 'nats', 'discovery', 'nats_monitor']);
    expect(rows[3].textContent).toContain('nats.monitoring_url is not configured');
  });
});

describe('SystemOverview tracing', () => {
  it('links to the trace viewer', async () => {
    mounted = await mount(SystemOverview, { overview });
    const link = mounted.host.querySelector('a[data-trace-ui]');

    expect(link?.getAttribute('href')).toBe('http://localhost:16686');
    expect(mounted.host.textContent).toContain('zen-engine');
  });
});
