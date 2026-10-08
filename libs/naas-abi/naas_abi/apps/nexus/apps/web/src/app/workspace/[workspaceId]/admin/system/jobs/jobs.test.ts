// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Result } from '../data/data-api';
import type { TracesApi } from '../traces/traces-api';
import { TRACE_ID, trace } from '../traces/traces-fixtures';
import { mount, type Mounted } from '../system-render';
import type { JobsApi } from './jobs-api';
import { job, run } from './jobs-fixtures';
import type { JobsOverview, RunDetail } from './jobs-types';
import { JobsTab } from './jobs';

let search = 'tab=jobs';
const replace = vi.fn();
const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push }),
  usePathname: () => '/workspace/w1/admin/system',
  useSearchParams: () => new URLSearchParams(search),
}));

const ok = <T,>(data: T): Promise<Result<T>> => Promise.resolve({ ok: true, data });

function fakeApi() {
  const healthy = job();
  const failing = job({
    key: 'ops.billing/sync',
    module_id: 'ops.billing',
    name: 'sync',
    triggers: [{ kind: 'cron', spec: '0 0 6 * * *', time_zone: 'UTC', summary: 'Every day at 06:00 UTC', next_at: '2026-10-03T06:00:00Z' }],
    last_run: run({ key: 'ops.billing/sync:4', module_id: 'ops.billing', job: 'sync', run_id: 'sync:4', status: 'FAILED', error: 'ValueError: boom' }),
    recent: [run({ key: 'ops.billing/sync:4', module_id: 'ops.billing', job: 'sync', run_id: 'sync:4', status: 'FAILED', error: 'ValueError: boom' })],
  });
  const overview: JobsOverview = { project: 'zen', jobs: [healthy, failing], sources: {} };
  const details: Record<string, RunDetail> = {
    'ops.billing/sync:4': {
      ...failing.recent[0],
      trace_id: TRACE_ID,
      payload: { full: true },
      result: null,
      logs: ['fetching', 'boom'],
      trace_url: `http://jaeger/trace/${TRACE_ID}`,
    },
  };
  const api: JobsApi = {
    overview: vi.fn(() => ok(overview)),
    runs: vi.fn(() => ok({ runs: [healthy.recent[0], failing.recent[0]], next: null })),
    run: vi.fn((moduleId: string, runId: string) => {
      const found = details[`${moduleId}/${runId}`];
      return found ? ok(found) : Promise.resolve({ ok: false as const, status: 404, reason: 'not found' });
    }),
    trigger: vi.fn((moduleId: string, name: string) => ok({ run_id: `${name}:9`, key: `${moduleId}/${name}:9` })),
    cancel: vi.fn(() => ok({ ok: true })),
    failures: vi.fn(() => ok({ since: '', count: 0, more: false, runs: [] })),
  };
  return { api, details };
}

let mounted: Mounted | null = null;
beforeEach(() => {
  search = 'tab=jobs';
  replace.mockClear();
  push.mockClear();
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const q = (selector: string) => document.querySelector(selector);
const text = () => document.body.textContent ?? '';
const button = (label: string, root: ParentNode = document) =>
  ([...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement | undefined) ?? null;

const tracesApi: TracesApi = {
  services: vi.fn(),
  operations: vi.fn(),
  search: vi.fn(),
  trace: vi.fn(() => Promise.resolve({ ok: true as const, data: trace() })),
};

async function open(api: JobsApi) {
  mounted = await mount(JobsTab, { api, tracesApi });
  await mounted.flush();
  await mounted.flush();
}

describe('JobsTab', () => {
  it('lists jobs with schedules, failing ones first', async () => {
    const { api } = fakeApi();
    await open(api);

    const rows = [...document.querySelectorAll('[data-job]')].map((r) => r.getAttribute('data-job'));
    expect(rows).toEqual(['ops.billing/sync', 'ops.reports/digest']);
    expect(text()).toContain('Every day at 06:00 UTC');
    expect(text()).toContain('Every 10 minutes');
    expect(text()).toContain('2 jobs');
    expect(text()).toContain('1 failing');
  });

  it('opens a job with its triggers, health and runs', async () => {
    const { api } = fakeApi();
    await open(api);

    await mounted!.click(q('[data-job="ops.billing/sync"]'));
    await mounted!.flush();

    expect(q('.job-detail')?.textContent).toContain('0 0 6 * * *');
    expect(q('.job-detail')?.textContent).toContain('ValueError');
    expect(api.runs).toHaveBeenLastCalledWith(expect.objectContaining({ module: 'ops.billing', job: 'sync' }));
  });

  it('opens a run from the strip with its timeline, error, logs, payload and trace', async () => {
    const { api } = fakeApi();
    await open(api);

    await mounted!.click(q('[aria-label="Failed run sync:4"]'));
    await mounted!.flush();

    const panel = () => q('[aria-label="Selected run"]');
    expect(panel()?.textContent).toContain('Triggered');
    expect(panel()?.textContent).toContain('ValueError: boom');
    expect(panel()?.textContent).toContain('boom');
    await mounted!.click(button('Payload', panel() ?? document));
    expect(panel()?.textContent).toContain('full');
    await mounted!.click(button('Trace', panel() ?? document));
    await mounted!.flush();
    expect(tracesApi.trace).toHaveBeenCalledWith(TRACE_ID);
    expect(panel()?.querySelectorAll('[role="treeitem"]')).toHaveLength(4);
    expect(panel()?.querySelector('.trace-header a')?.getAttribute('href')).toBe(`http://jaeger/trace/${TRACE_ID}`);
    await mounted!.click(button('Open in Traces', panel() ?? document));
    expect(push).toHaveBeenCalledWith(`/workspace/w1/admin/system?tab=traces&trace=${TRACE_ID}`);
  });

  it('runs a job now and follows the run from queued to started', async () => {
    const { api, details } = fakeApi();
    await open(api);

    await mounted!.click(q('[aria-label="Run digest now"]'));
    await mounted!.click(button('Run', q('[role="dialog"]') ?? document));
    await mounted!.flush();

    expect(api.trigger).toHaveBeenCalledWith('ops.reports', 'digest', {});
    expect(q('[aria-label="Selected run"]')?.textContent).toContain('Queued');
    expect(q('.data-toasts')?.textContent).toContain('Started digest');

    details['ops.reports/digest:9'] = {
      ...run({ key: 'ops.reports/digest:9', run_id: 'digest:9', status: 'RUNNING', finished_at: null, duration_ms: null }),
      payload: {},
      result: null,
      logs: [],
      trace_url: null,
    };
    await new Promise((r) => setTimeout(r, 1700));
    await mounted!.flush();
    expect(q('[aria-label="Selected run"]')?.textContent).toContain('Running');
  });

  it('cancels a running run', async () => {
    const { api, details } = fakeApi();
    details['ops.billing/sync:4'] = { ...details['ops.billing/sync:4'], status: 'RUNNING', finished_at: null, duration_ms: null };
    search = 'tab=jobs&run=ops.billing%2Fsync%3A4';
    await open(api);

    await mounted!.click(button('Cancel', q('[aria-label="Selected run"]') ?? document));
    await mounted!.click(button('Cancel run', q('[role="dialog"]') ?? document));
    await mounted!.flush();

    expect(api.cancel).toHaveBeenCalledWith('ops.billing', 'sync:4');
    expect(q('.data-toasts')?.textContent).toContain('Cancellation sent');
  });

  it('filters the run feed by status', async () => {
    const { api } = fakeApi();
    await open(api);

    await mounted!.click(button('Runs'));
    await mounted!.flush();
    expect(document.querySelectorAll('[data-run]')).toHaveLength(2);

    await mounted!.click(button('Failed'));
    await mounted!.flush();
    expect(api.runs).toHaveBeenLastCalledWith(expect.objectContaining({ statuses: ['FAILED', 'TIMED_OUT'] }));
  });
});


describe('JobsTab failure notification', () => {
  it('lists runs that failed since the admin last looked, and marks them seen', async () => {
    const { api } = fakeApi();
    const onFailuresSeen = vi.fn();
    const failed = run({ key: 'ops.billing/sync:4', module_id: 'ops.billing', job: 'sync', run_id: 'sync:4', status: 'FAILED' });
    mounted = await mount(JobsTab, {
      api,
      tracesApi,
      failures: { since: '2026-10-01T09:00:00+00:00', count: 2, more: false, runs: [failed, failed] },
      onFailuresSeen,
    });
    await mounted.flush();

    const banner = document.querySelector('[data-failures]');
    expect(banner?.textContent).toContain('2 runs failed');
    expect(banner?.textContent).toContain('sync');

    await mounted.click(button('Show failed runs', banner ?? document));
    expect(api.runs).toHaveBeenLastCalledWith(expect.objectContaining({ statuses: ['FAILED', 'TIMED_OUT'] }));

    await mounted.click(button('Mark as seen', banner ?? document));
    expect(onFailuresSeen).toHaveBeenCalled();
  });

  it('shows no banner without failures', async () => {
    const { api } = fakeApi();
    mounted = await mount(JobsTab, { api, tracesApi, failures: { since: '', count: 0, more: false, runs: [] } });
    await mounted.flush();

    expect(document.querySelector('[data-failures]')).toBeNull();
  });
});
