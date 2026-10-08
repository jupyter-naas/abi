// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from './system-render';
import { TrafficView } from './system-traffic';
import type { TrafficEvent } from './system-traffic-model';

const base: TrafficEvent = {
  at: 1_759_392_000.123,
  kind: 'service',
  subject: 'abi.svc.document.v1.get',
  service: 'document',
  method: 'get',
  caller: 'nexus-api',
  request_bytes: 7,
  reply_bytes: 42,
  latency_ms: 1.25,
  status: 'ok',
  error_code: '',
  trace_id: '4bf92f3577b34da6a3ce929d0e0e4736',
};

const events: TrafficEvent[] = [
  base,
  { ...base, at: base.at + 1, method: 'find', subject: 'abi.svc.document.v1.find', status: 'error', error_code: 'NOT_FOUND' },
  { ...base, at: base.at + 2, kind: 'event', service: 'abc', method: 'publish', subject: 'evt.abc.e-1', reply_bytes: null, latency_ms: null, status: 'published', caller: '' },
];

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('TrafficView', () => {
  it('lists calls newest first with caller, sizes, latency and status', async () => {
    mounted = await mount(TrafficView, {
      events: [...events].reverse(),
      filters: { kind: 'all', text: '', errorsOnly: false },
      onFilters: () => {},
    });
    const rows = [...mounted.host.querySelectorAll('[data-traffic-row]')];

    expect(rows).toHaveLength(3);
    expect(rows[2].textContent).toContain('document.get');
    expect(rows[2].textContent).toContain('nexus-api');
    expect(rows[2].textContent).toContain('1.25 ms');
    expect(rows[1].textContent).toContain('NOT_FOUND');
    expect(rows[0].textContent).toContain('published');
  });

  it('summarizes per service and method', async () => {
    mounted = await mount(TrafficView, {
      events,
      filters: { kind: 'all', text: '', errorsOnly: false },
      onFilters: () => {},
    });
    const summary = mounted.host.querySelector('[data-traffic-summary="service document.get"]');

    expect(summary?.textContent).toContain('1');
  });

  it('applies the filters it is given', async () => {
    mounted = await mount(TrafficView, {
      events,
      filters: { kind: 'all', text: '', errorsOnly: true },
      onFilters: () => {},
    });

    expect(mounted.host.querySelectorAll('[data-traffic-row]')).toHaveLength(1);
  });
});

describe('TrafficView trace links', () => {
  it('opens trace ids in the Traces tab when tracing is on', async () => {
    const onOpenTrace = vi.fn();
    mounted = await mount(TrafficView, {
      events: [base],
      filters: { kind: 'all', text: '', errorsOnly: false },
      onFilters: () => {},
      tracing: true,
      onOpenTrace,
    });
    const link = mounted.host.querySelector('a[data-trace]');

    expect(link?.getAttribute('href')).toBe('?tab=traces&trace=4bf92f3577b34da6a3ce929d0e0e4736');
    expect(link?.getAttribute('target')).toBeNull();
    await mounted.click(link);
    expect(onOpenTrace).toHaveBeenCalledWith('4bf92f3577b34da6a3ce929d0e0e4736');
  });

  it('shows the short id without a link when tracing is off', async () => {
    mounted = await mount(TrafficView, {
      events: [base],
      filters: { kind: 'all', text: '', errorsOnly: false },
      onFilters: () => {},
    });

    expect(mounted.host.querySelector('a[data-trace]')).toBeNull();
    expect(mounted.host.textContent).toContain('4bf92f35');
  });
});
