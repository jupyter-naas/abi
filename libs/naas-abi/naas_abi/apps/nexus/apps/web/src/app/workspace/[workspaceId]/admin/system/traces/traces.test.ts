// @vitest-environment jsdom
import { act, createElement, type ComponentProps } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Result } from '../data/data-api';
import { mount, type Mounted } from '../system-render';
import type { TracesApi } from './traces-api';
import { POLLING_ID, TRACE_ID, pollingTrace, summary, trace } from './traces-fixtures';
import type { Trace } from './traces-types';
import { TraceView } from './trace-view';
import { TracesTab } from './traces';

let search = 'tab=traces';
const replace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  usePathname: () => '/workspace/w1/admin/system',
  useSearchParams: () => new URLSearchParams(search),
}));

const ok = <T,>(data: T): Promise<Result<T>> => Promise.resolve({ ok: true, data });
const fail = (status: number, reason: string, source?: string) =>
  Promise.resolve({ ok: false as const, status, reason, source });

function fakeApi(traces: Record<string, Trace> = { [TRACE_ID]: trace(), [POLLING_ID]: pollingTrace() }): TracesApi {
  return {
    services: vi.fn(() => ok({ services: ['document', 'nexus-api', 'ops.reports'], ui_url: 'http://jaeger' })),
    operations: vi.fn(() => ok({ operations: [{ name: 'job digest', kind: 'internal' }, { name: 'job digest', kind: 'server' }] })),
    search: vi.fn(() =>
      ok({ traces: [summary(), summary({ trace_id: 'b'.repeat(32), duration_ms: 3, errors: 0, root: { service: 'document', name: 'document.get' } })] }),
    ),
    trace: vi.fn((id: string) => (traces[id] ? ok(traces[id]) : fail(404, 'not found'))),
  };
}

let mounted: Mounted | null = null;
beforeEach(() => {
  search = 'tab=traces';
  replace.mockClear();
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const q = (selector: string) => document.querySelector(selector);
const text = () => document.body.textContent ?? '';
const rows = () => [...document.querySelectorAll('[role="treeitem"]')].map((r) => r.getAttribute('data-span'));
const button = (label: string, root: ParentNode = document) =>
  ([...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement | undefined) ?? null;

async function choose(label: string, value: string) {
  const select = q(`select[aria-label="${label}"]`) as HTMLSelectElement;
  await act(async () => {
    select.value = value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await mounted!.flush();
}

async function open(api: TracesApi) {
  mounted = await mount(TracesTab, { api });
  await mounted.flush();
  await mounted.flush();
}

describe('TracesTab search', () => {
  it('lists recent traces with root, services, duration and errors', async () => {
    const api = fakeApi();
    await open(api);

    const results = [...document.querySelectorAll('[data-trace]')].map((r) => r.getAttribute('data-trace'));
    expect(results).toEqual([TRACE_ID, 'b'.repeat(32)]);
    expect(q(`[data-trace="${TRACE_ID}"]`)?.textContent).toContain('POST /api/admin/system/jobs/run');
    expect(q(`[data-trace="${TRACE_ID}"]`)?.textContent).toContain('1 error');
    expect(q(`[data-trace="${TRACE_ID}"]`)?.textContent).toContain('120 ms');
    const dots = q('[aria-label="Traces by start time and duration"]')?.querySelectorAll('button');
    expect(dots).toHaveLength(2);
    expect(dots?.[0].className).toContain('trace-dot-error');
    expect(api.search).toHaveBeenLastCalledWith(expect.objectContaining({ lookback: '1h', service: null, errors: false }));
  });

  it('narrows by service, operation, window and errors', async () => {
    const api = fakeApi();
    await open(api);

    await choose('Service', 'ops.reports');
    expect(api.operations).toHaveBeenCalledWith('ops.reports');
    const operations = [...(q('select[aria-label="Operation"]') as HTMLSelectElement).options].map((o) => o.value);
    expect(operations).toEqual(['', 'job digest']);
    await choose('Operation', 'job digest');
    await choose('Time window', '24h');
    await mounted!.click(q('.trace-errors-toggle input'));
    await mounted!.flush();

    expect(api.search).toHaveBeenLastCalledWith(
      expect.objectContaining({ service: 'ops.reports', operation: 'job digest', lookback: '24h', errors: true }),
    );
    expect(replace).toHaveBeenLastCalledWith(
      '/workspace/w1/admin/system?tab=traces&service=ops.reports&operation=job+digest&lookback=24h&errors=true',
      { scroll: false },
    );
  });

  it('opens a trace from its dot in the scatter', async () => {
    const api = fakeApi();
    await open(api);

    await mounted!.click(q('[aria-label="Traces by start time and duration"] button'));
    await mounted!.flush();

    expect(api.trace).toHaveBeenCalledWith(TRACE_ID);
    expect(rows()).toEqual(['a', 'b', 'c', 'd']);
  });

  it('says when tracing is not configured', async () => {
    const api = fakeApi();
    api.search = vi.fn(() => fail(503, 'Tracing is off (telemetry.query_url).', 'tracing'));
    await open(api);

    expect(q('.data-notice')?.textContent).toContain('Tracing is off');
    expect(text()).not.toContain('No traces match');
  });

  it('jumps to a trace id', async () => {
    const api = fakeApi();
    await open(api);

    await mounted!.type(q('input[aria-label="Go to trace id"]'), TRACE_ID.toUpperCase());
    await act(async () => q('form.trace-jump')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    await mounted!.flush();

    expect(api.trace).toHaveBeenCalledWith(TRACE_ID);
    expect(rows()).toEqual(['a', 'b', 'c', 'd']);
  });
});

describe('TracesTab trace', () => {
  it('opens a result as a waterfall and a span with its attributes, error and parent', async () => {
    const api = fakeApi();
    await open(api);

    await mounted!.click(q(`[data-trace="${TRACE_ID}"]`));
    await mounted!.flush();

    expect(rows()).toEqual(['a', 'b', 'c', 'd']);
    expect(q('.trace-stats')?.textContent).toContain('Spans4');
    expect(q('.trace-stats')?.textContent).toContain('Errors1');
    expect(q('.trace-header a')?.getAttribute('href')).toBe(`http://jaeger/trace/${TRACE_ID}`);
    expect(replace).toHaveBeenLastCalledWith(`/workspace/w1/admin/system?tab=traces&trace=${TRACE_ID}`, { scroll: false });

    await mounted!.click(q('[data-span="d"]'));
    const detail = () => q('[aria-label="Selected span"]');
    expect(detail()?.textContent).toContain('vector.search');
    expect(detail()?.textContent).toContain('collection missing');
    expect(detail()?.textContent).toContain('Links · 1');
    expect(replace).toHaveBeenLastCalledWith(`/workspace/w1/admin/system?tab=traces&trace=${TRACE_ID}&span=d`, { scroll: false });

    await mounted!.click(button('job digest', detail() ?? document));
    expect(detail()?.textContent).toContain('ABI');
    expect(detail()?.textContent).toContain('abi.job');
    expect(detail()?.textContent).toContain('Events · 1');
    expect(q('[data-span="b"]')?.getAttribute('aria-selected')).toBe('true');

    await mounted!.click(button('Search'));
    await mounted!.flush();
    expect(q('[role="listbox"]')).not.toBeNull();
  });

  it('opens straight from a deep link with the span selected', async () => {
    search = `tab=traces&trace=${TRACE_ID}&span=c`;
    const api = fakeApi();
    await open(api);

    expect(api.search).not.toHaveBeenCalled();
    expect(q('[aria-label="Selected span"]')?.textContent).toContain('document.get');
  });

  it('filters spans keeping their ancestors, and collapses subtrees', async () => {
    search = `tab=traces&trace=${TRACE_ID}`;
    await open(fakeApi());

    await mounted!.type(q('input[aria-label="Filter spans"]'), 'vector');
    expect(rows()).toEqual(['a', 'b', 'd']);
    expect(text()).toContain('3 of 4 spans');
    await mounted!.type(q('input[aria-label="Filter spans"]'), '');

    await mounted!.click(q('[data-span="b"] button[aria-label="Collapse"]'));
    expect(rows()).toEqual(['a', 'b']);
    expect(q('[data-span="b"]')?.textContent).toContain('+2');
    await mounted!.click(q('button[aria-label="Expand all"]'));
    expect(rows()).toEqual(['a', 'b', 'c', 'd']);

    await mounted!.click(q('button[aria-label="Collapse all"]'));
    expect(rows()).toEqual(['a']);
    await mounted!.click(q('[data-span="a"] button[aria-label="Expand"]'));
    expect(rows()).toEqual(['a', 'b']);
  });

  it('explains a trace that is not there (yet)', async () => {
    search = `tab=traces&trace=${'c'.repeat(32)}`;
    await open(fakeApi());

    expect(text()).toContain('Trace not found');
  });
});

/** Embedded, the host (Jobs) provides the tooltip context. */
const Embedded = (props: ComponentProps<typeof TraceView>) => createElement(Tooltip.Provider, null, createElement(TraceView, props));

describe('TracesTab repeated calls', () => {
  const group = () => q('[data-group="r|nexus-api|agent/status"]');
  const spans = () => rows().filter(Boolean);

  it('folds repeated calls into one row with their count, failures and cadence', async () => {
    search = `tab=traces&trace=${POLLING_ID}`;
    await open(fakeApi());

    expect(spans()).toEqual(['r', 's']);
    expect(group()?.textContent).toContain('agent/status');
    expect(group()?.textContent).toContain('6×');
    expect(group()?.textContent).toContain('60.0 ms total · every 100 ms');
    expect(group()?.getAttribute('title')).toContain('1 failed');
    expect(group()?.querySelectorAll('.trace-group-tick')).toHaveLength(6);
    expect(text()).toContain('14 spans · 1 folded');
  });

  it('unfolds a group into one row per call and can list every span', async () => {
    search = `tab=traces&trace=${POLLING_ID}`;
    await open(fakeApi());

    await mounted!.click(group());
    expect(spans()).toEqual(['r', 's', 'p0', 'p1', 'p2', 'p3', 'p4', 'p5']);
    expect(group()?.getAttribute('aria-expanded')).toBe('true');
    await mounted!.click(q('[data-span="p3"] button[aria-label="Expand"]'));
    expect(spans()).toEqual(['r', 's', 'p0', 'p1', 'p2', 'p3', 'g3', 'p4', 'p5']);
    await mounted!.click(group()!.querySelector('button[aria-label="Fold calls"]'));
    expect(spans()).toEqual(['r', 's']);

    await mounted!.click(q('button[aria-label="Fold repeated calls"]'));
    expect(group()).toBeNull();
    expect(spans()).toHaveLength(14);
  });

  it('opens the group holding a linked span', async () => {
    search = `tab=traces&trace=${POLLING_ID}&span=g3`;
    await open(fakeApi());

    expect(spans()).toContain('g3');
    expect(q('[data-span="g3"]')?.getAttribute('aria-selected')).toBe('true');
    expect(q('[aria-label="Selected span"]')?.textContent).toContain('document/get');
  });

  it('lists matching spans flat while filtering', async () => {
    search = `tab=traces&trace=${POLLING_ID}`;
    await open(fakeApi());

    await mounted!.type(q('input[aria-label="Filter spans"]'), 'document');
    expect(group()).toBeNull();
    expect(spans()).toEqual(['r', 'p0', 'g0', 'p1', 'g1', 'p2', 'g2', 'p3', 'g3', 'p4', 'g4', 'p5', 'g5']);
  });
});

describe('TraceView embedded', () => {
  it('shows the trace compactly with a way to open it in Traces', async () => {
    const api = fakeApi();
    const onExpand = vi.fn();
    mounted = await mount(Embedded, { api, traceId: TRACE_ID, compact: true, onExpand });
    await mounted.flush();

    expect(q('.trace-view-compact')).not.toBeNull();
    expect(rows()).toEqual(['a', 'b', 'c', 'd']);
    await mounted.click(button('Open in Traces'));
    expect(onExpand).toHaveBeenCalled();

    await mounted.click(q('[data-span="c"]'));
    expect(q('[aria-label="Selected span"]')?.textContent).toContain('document.get');
    await mounted.click(q('[data-span="c"]'));
    expect(q('[aria-label="Selected span"]')).toBeNull();
  });
});
