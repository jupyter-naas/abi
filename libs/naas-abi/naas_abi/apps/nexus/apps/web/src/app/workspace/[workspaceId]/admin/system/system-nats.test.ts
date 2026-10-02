// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { jetstream, natsConnections, natsServer } from './system-fixtures';
import { mount, type Mounted } from './system-render';
import { SystemNats } from './system-nats';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('SystemNats', () => {
  it('shows the server, connections and streams', async () => {
    mounted = await mount(SystemNats, {
      server: { ok: true, data: natsServer },
      connections: { ok: true, data: natsConnections },
      jetstream: { ok: true, data: jetstream },
    });
    const text = mounted.host.textContent ?? '';

    expect(text).toContain('2.14.7');
    expect(text).toContain('(unnamed)');
    expect(mounted.host.querySelector('[data-stream="ABI_JOBS_zen"]')?.textContent).toContain('jobs');
  });

  it('expands a stream into its consumers', async () => {
    mounted = await mount(SystemNats, {
      server: { ok: true, data: natsServer },
      connections: { ok: true, data: natsConnections },
      jetstream: { ok: true, data: jetstream },
    });

    await mounted.click(mounted.host.querySelector('[data-stream="ABI_JOBS_zen"] button'));

    expect(mounted.host.textContent).toContain('job-a-b');
  });

  it('shows the reason when the monitor is down', async () => {
    const down = { ok: false as const, status: 503, source: 'nats_monitor', reason: 'nats.monitoring_url is not configured' };
    mounted = await mount(SystemNats, { server: down, connections: down, jetstream: down });

    expect(mounted.host.querySelector('.system-source-note')?.textContent).toContain('nats.monitoring_url is not configured');
  });
});
