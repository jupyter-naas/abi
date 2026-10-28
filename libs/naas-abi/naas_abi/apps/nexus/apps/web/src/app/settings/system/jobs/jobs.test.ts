// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Result } from '../data/data-api';
import type { TracesApi } from '../traces/traces-api';
import { TRACE_ID, trace } from '../traces/traces-fixtures';
import { mount, type Mounted } from '../system-render';
import type { JobsApi } from './jobs-api';
import { INGEST_SCHEMA, job, run, step, workflowJob } from './jobs-fixtures';
import type { Failure } from '../data/data-api';
import type { JobsOverview, JobView, RunDetail, RunStep } from './jobs-types';
import { JobsTab } from './jobs';

let search = '';
const replace = vi.fn();
const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push }),
  usePathname: () => '/settings/system/jobs',
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
      workflow: null,
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
  search = '';
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
    expect(push).toHaveBeenCalledWith(`/settings/system/traces?trace=${TRACE_ID}`);
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
      workflow: null,
    };
    await new Promise((r) => setTimeout(r, 1700));
    await mounted!.flush();
    expect(q('[aria-label="Selected run"]')?.textContent).toContain('Running');
  });

  it('cancels a running run', async () => {
    const { api, details } = fakeApi();
    details['ops.billing/sync:4'] = { ...details['ops.billing/sync:4'], status: 'RUNNING', finished_at: null, duration_ms: null };
    search = 'run=ops.billing%2Fsync%3A4';
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


// --- workflows -------------------------------------------------------------------------

const FLOW_RUN = run({ key: 'ops.flows/ingest:5', module_id: 'ops.flows', job: 'ingest', run_id: 'ingest:5' });

function flowsApi(options: { jobs?: JobView[]; steps?: RunStep[]; result?: unknown; refuse?: Failure } = {}) {
  const jobs = options.jobs ?? [job(), workflowJob()];
  const steps = options.steps ?? [
    step({ key: 'fetch', attempt: 2 }),
    step({
      key: 'map[0]',
      kind: 'call',
      child: { module_id: 'ops.flows', workflow: 'map_item', run_id: 'map_item:1', key: 'ops.flows/map_item:1' },
    }),
    step({ key: 'map[1]', kind: 'call', status: 'FAILED', error: 'ChildRunFailed: map_item:2 FAILED', child: null }),
  ];
  const details: Record<string, RunDetail> = {
    [FLOW_RUN.key]: {
      ...FLOW_RUN,
      payload: { filter: 'news' },
      result: options.result ?? { count: 2 },
      logs: [],
      trace_url: null,
      workflow: { steps, truncated: false },
    },
    'ops.flows/map_item:1': {
      ...run({ key: 'ops.flows/map_item:1', module_id: 'ops.flows', job: 'map_item', run_id: 'map_item:1' }),
      payload: {},
      result: { ok: true },
      logs: [],
      trace_url: null,
      workflow: { steps: [], truncated: false },
    },
  };
  const overview: JobsOverview = { project: 'zen', jobs, sources: {} };
  const api: JobsApi = {
    overview: vi.fn(() => ok(overview)),
    runs: vi.fn(() => ok({ runs: [FLOW_RUN], next: null })),
    run: vi.fn((moduleId: string, runId: string) => {
      const found = details[`${moduleId}/${runId}`];
      return found ? ok(found) : Promise.resolve({ ok: false as const, status: 404, reason: 'not found' });
    }),
    trigger: vi.fn((moduleId: string, name: string) =>
      options.refuse ? Promise.resolve(options.refuse) : ok({ run_id: `${name}:9`, key: `${moduleId}/${name}:9` }),
    ),
    cancel: vi.fn(() => ok({ ok: true })),
    failures: vi.fn(() => ok({ since: '', count: 0, more: false, runs: [] })),
  };
  return { api, details };
}

const dialog = () => q('[role="dialog"]') as HTMLElement;
const field = (label: string) => dialog().querySelector(`[aria-label="${label}"]`);

describe('JobsTab workflows', () => {
  it('badges workflows and filters the table by kind', async () => {
    const { api } = flowsApi();
    await open(api);

    const rows = () => [...document.querySelectorAll('[data-job]')].map((r) => r.getAttribute('data-job'));
    expect(rows()).toEqual(expect.arrayContaining(['ops.flows/ingest', 'ops.reports/digest']));
    expect(q('[data-job="ops.flows/ingest"]')?.textContent).toContain('workflow');
    expect(q('[data-job="ops.reports/digest"]')?.textContent).not.toContain('workflow');
    expect(text()).toContain('2 jobs (1 workflows)');

    await mounted!.click(button('Workflows', q('[aria-label="Kind"]') as HTMLElement));
    expect(rows()).toEqual(['ops.flows/ingest']);
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining('kind=workflow'), expect.anything());

    await mounted!.click(button('Jobs', q('[aria-label="Kind"]') as HTMLElement));
    expect(rows()).toEqual(['ops.reports/digest']);
    await mounted!.click(button('All', q('[aria-label="Kind"]') as HTMLElement));
    expect(rows()).toHaveLength(2);
  });

  it('shows plain jobs as before when there is no workflow: no badge, no kind filter', async () => {
    const { api } = flowsApi({ jobs: [job()] });
    await open(api);

    expect(q('[aria-label="Kind"]')).toBeNull();
    expect(q('[data-job="ops.reports/digest"]')?.textContent).not.toContain('workflow');
    expect(text()).toContain('1 job ·');
  });

  it('launches a workflow from a form made of its input schema', async () => {
    const { api } = flowsApi();
    await open(api);

    await mounted!.click(q('[aria-label="Run ingest now"]'));
    expect(dialog().textContent).toContain('durable run');
    // Defaults come from the schema; the required field is marked.
    expect((field('Limit') as HTMLInputElement).value).toBe('10');
    expect((field('Dry run') as HTMLInputElement).checked).toBe(false);
    expect((field('Mode') as HTMLSelectElement).value).toBe('fast');
    expect(dialog().textContent).toContain('Keyword to search for');
    expect(dialog().querySelector('[data-field="/filter"]')?.textContent).toContain('*');

    await mounted!.type(field('Filter'), 'news');
    await mounted!.type(field('Limit'), '25');
    await mounted!.click(field('Dry run'));
    await mounted!.click(button('Add tags', dialog()));
    await mounted!.type(field('Tags 1'), 'news');
    await mounted!.type(field('Days'), '7');
    await mounted!.click(button('Run', dialog()));
    await mounted!.flush();

    expect(api.trigger).toHaveBeenCalledWith('ops.flows', 'ingest', {
      filter: 'news',
      limit: 25,
      dry_run: true,
      mode: 'fast',
      tags: ['news'],
      window: { days: 7 },
    });
    expect(q('[aria-label="Selected run"]')?.textContent).toContain('Queued');
  });

  it('checks the input before sending and shows what to fix', async () => {
    const { api } = flowsApi();
    await open(api);
    await mounted!.click(q('[aria-label="Run ingest now"]'));

    // Nothing is shown before an attempt.
    expect(dialog().querySelector('.data-field-error')).toBeNull();
    await mounted!.type(field('Limit'), '0');
    await mounted!.click(button('Run', dialog()));
    await mounted!.flush();

    expect(api.trigger).not.toHaveBeenCalled();
    expect(dialog().querySelector('[data-field="/filter"]')?.textContent).toContain('Required.');
    expect(dialog().querySelector('[data-field="/limit"]')?.textContent).toContain('At least 1.');

    await mounted!.type(field('Limit'), '2.5x');
    expect(dialog().querySelector('[data-field="/limit"]')?.textContent).toContain('Enter a number.');
    await mounted!.type(field('Limit'), '3');
    await mounted!.type(field('Filter'), 'news');
    expect(dialog().querySelector('.data-field-error')).toBeNull();
    await mounted!.click(button('Run', dialog()));
    await mounted!.flush();
    expect(api.trigger).toHaveBeenCalledTimes(1);
  });

  it('shows the faults the API refused the input for, under their fields', async () => {
    const refuse: Failure = {
      ok: false,
      status: 422,
      reason: "The input does not match the workflow's input schema",
      errors: [{ path: '/filter', message: "'x' is not allowed here" }],
    };
    const { api } = flowsApi({ refuse });
    await open(api);
    await mounted!.click(q('[aria-label="Run ingest now"]'));
    await mounted!.type(field('Filter'), 'x');

    await mounted!.click(button('Run', dialog()));
    await mounted!.flush();

    expect(api.trigger).toHaveBeenCalledTimes(1);
    expect(dialog().textContent).toContain("The input does not match the workflow's input schema");
    expect(dialog().querySelector('[data-field="/filter"]')?.textContent).toContain("'x' is not allowed here");

    await mounted!.type(field('Filter'), 'xy'); // an edit clears the refusal
    expect(dialog().textContent).not.toContain("is not allowed here");
  });

  it('goes between the form and the JSON it stands for', async () => {
    const { api } = flowsApi();
    await open(api);
    await mounted!.click(q('[aria-label="Run ingest now"]'));
    await mounted!.type(field('Filter'), 'news');

    await mounted!.click(button('JSON', dialog()));
    expect(dialog().querySelector('.sf')).toBeNull();
    expect(button('Form', dialog())?.getAttribute('aria-selected')).toBe('false');

    await mounted!.click(button('Form', dialog()));
    expect((field('Filter') as HTMLInputElement).value).toBe('news');
  });

  it('falls back to the JSON editor when the schema has no form, and still checks it', async () => {
    const union = workflowJob({
      key: 'ops.flows/union',
      name: 'union',
      input_schema: {
        type: 'object',
        properties: { target: { anyOf: [{ type: 'string' }, { type: 'integer' }] } },
        required: ['target'],
      },
    });
    const { api } = flowsApi({ jobs: [union] });
    await open(api);

    await mounted!.click(q('[aria-label="Run union now"]'));

    expect(dialog().textContent).toContain('no generated form');
    expect(dialog().querySelector('[aria-label="Input editor"]')).toBeNull();
    expect(dialog().querySelector('.sf')).toBeNull();
    await mounted!.click(button('Run', dialog())); // the default {} lacks the required target
    await mounted!.flush();
    expect(api.trigger).not.toHaveBeenCalled();
    expect(dialog().querySelector('[aria-label="Problems with the input"]')?.textContent).toContain('target');
  });

  it('keeps the plain trigger dialog for a job: payload editor, no form', async () => {
    const { api } = flowsApi();
    await open(api);

    await mounted!.click(q('[aria-label="Run digest now"]'));

    expect(dialog().textContent).toContain('ctx.payload');
    expect(dialog().querySelector('[aria-label="Input editor"]')).toBeNull();
    await mounted!.click(button('Run', dialog()));
    await mounted!.flush();
    expect(api.trigger).toHaveBeenCalledWith('ops.reports', 'digest', {});
  });

  it('re-runs a workflow with the earlier input in the form', async () => {
    const { api } = flowsApi();
    search = 'run=ops.flows%2Fingest%3A5';
    await open(api);

    await mounted!.click(button('Re-run', q('[aria-label="Selected run"]') as HTMLElement));

    expect(dialog().textContent).toContain('Run ingest again');
    expect((field('Filter') as HTMLInputElement).value).toBe('news');
  });

  it('shows a workflow run as a step timeline with attempts, errors and links to child runs', async () => {
    const { api } = flowsApi();
    search = 'run=ops.flows%2Fingest%3A5';
    await open(api);

    const panel = () => q('[aria-label="Selected run"]') as HTMLElement;
    expect([...panel().querySelectorAll('[data-step]')].map((r) => r.getAttribute('data-step'))).toEqual([
      'fetch',
      'map[0]',
      'map[1]',
    ]);
    expect(button('Steps3', panel())).not.toBeNull();
    expect(panel().querySelector('[data-step="fetch"]')?.textContent).toContain('attempt 2');
    expect(panel().querySelector('[data-step="fetch"]')?.textContent).toContain('+0 ms · 1.0 s');
    expect(panel().querySelector('[data-step="map[0]"]')?.textContent).toContain('call');
    expect(panel().querySelector('[data-step="map[1]"]')?.textContent).toContain('ChildRunFailed: map_item:2 FAILED');
    expect(panel().querySelector('[data-step="map[1]"]')?.textContent).toContain('Failed');
    expect(button('Payload', panel())).toBeNull(); // a workflow's payload is its input
    expect(button('Input', panel())).not.toBeNull();

    // A child link opens the child run.
    const link = [...panel().querySelectorAll('[data-step="map[0]"] button')].find((b) => b.textContent?.includes('map_item'));
    await mounted!.click(link ?? null);
    await mounted!.flush();
    expect(api.run).toHaveBeenCalledWith('ops.flows', 'map_item:1');
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining('run=ops.flows%2Fmap_item%3A1'), expect.anything());
  });

  it('says so when a workflow run has no steps yet', async () => {
    const { api } = flowsApi({ steps: [] });
    search = 'run=ops.flows%2Fingest%3A5';
    await open(api);

    expect(q('[aria-label="Selected run"]')?.textContent).toContain('No steps yet');
  });

  it('shows the start of a result the API cut, and what to do about it', async () => {
    const { api } = flowsApi({ result: { truncated: true, bytes: 40_000, preview: '{"rows": ["aaa' } });
    search = 'run=ops.flows%2Fingest%3A5';
    await open(api);

    const panel = () => q('[aria-label="Selected run"]') as HTMLElement;
    await mounted!.click(button('Result', panel()));

    expect(panel().textContent).toContain('The result is 39 KB');
    expect(panel().textContent).toContain('object storage');
    expect(panel().textContent).toContain('{"rows": ["aaa');
  });

  it('gives a plain job run no steps tab', async () => {
    const { api, details } = fakeApi();
    details['ops.billing/sync:4'] = { ...details['ops.billing/sync:4'], workflow: null };
    search = 'run=ops.billing%2Fsync%3A4';
    await open(api);

    const panel = q('[aria-label="Selected run"]') as HTMLElement;
    expect([...panel.querySelectorAll('[role="tab"]')].map((t) => t.textContent)).toEqual(['Logs2', 'Payload', 'Output', 'Trace']);
    expect(panel.textContent).toContain('boom'); // the logs, as before
  });
});
