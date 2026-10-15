// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Result } from '../data/data-api';
import { mount, type Mounted } from '../system-render';
import type { AgentsApi } from './agents-api';
import type { AgentRunDetail, AgentRunSummary } from './agents-types';
import { AgentsTab } from './agents';

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push }),
  usePathname: () => '/workspace/w1/admin/system',
  useSearchParams: () => new URLSearchParams('tab=agents'),
}));

const ok = <T,>(data: T): Promise<Result<T>> => Promise.resolve({ ok: true, data });

const summary = (patch: Partial<AgentRunSummary>): AgentRunSummary => ({
  key: 'acme.agents/r2',
  module_id: 'acme.agents',
  run_id: 'r2',
  agent: 'Researcher',
  invocation_id: 'inv-2',
  status: 'SUCCEEDED',
  thread_id: 't-2',
  caller: 'api',
  owner: 'i-1',
  submitted_at: '2026-10-02T09:00:00+00:00',
  finished_at: '2026-10-02T09:00:12.500000+00:00',
  duration_ms: 12500,
  error_code: '',
  error_message: '',
  trace_id: 'c'.repeat(32),
  events: 2,
  ...patch,
});

const running = summary({
  key: 'acme.agents/r4',
  run_id: 'r4',
  invocation_id: 'inv-4',
  status: 'RUNNING',
  caller: 'orchestrator',
  owner: 'i-2',
  finished_at: null,
  duration_ms: null,
  trace_id: '',
});
const done = summary({});
const failed = summary({
  key: 'acme.other/r3',
  module_id: 'acme.other',
  run_id: 'r3',
  agent: 'Writer',
  status: 'FAILED',
  error_code: 'AGENT_FAILED',
  error_message: 'Agent execution failed; inspect provider logs',
});

function fakeApi(): AgentsApi {
  const details: Record<string, AgentRunDetail> = {
    'acme.agents/r2': {
      ...done,
      event_list: [
        { sequence: 1, event: 'message', preview: 'Looking it up', truncated: false },
        { sequence: 2, event: 'done', preview: '[DONE]', truncated: false },
      ],
      trace_url: `http://jaeger/trace/${'c'.repeat(32)}`,
    },
    'acme.agents/r4': { ...running, event_list: [], trace_url: null },
  };
  return {
    runs: vi.fn((filters) =>
      ok({
        runs: filters?.statuses?.length ? [failed] : [running, failed, done],
        next: null,
      }),
    ),
    run: vi.fn((moduleId: string, runId: string) => {
      const found = details[`${moduleId}/${runId}`];
      return found ? ok(found) : Promise.resolve({ ok: false as const, status: 404, reason: 'not found' });
    }),
    cancel: vi.fn(() => ok({ ok: true })),
  };
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  push.mockClear();
});

const text = () => document.body.textContent ?? '';
const button = (label: string) =>
  ([...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement | undefined) ??
  null;
const row = (key: string) => document.querySelector(`[data-run="${key}"]`);

async function open(api: AgentsApi) {
  mounted = await mount(AgentsTab, { api });
  await mounted.flush();
  return mounted;
}

describe('agents tab', () => {
  it('lists runs newest first with their agent, module and caller', async () => {
    await open(fakeApi());

    expect([...document.querySelectorAll('[data-run]')].map((r) => r.getAttribute('data-run'))).toEqual([
      'acme.agents/r4',
      'acme.other/r3',
      'acme.agents/r2',
    ]);
    expect(row('acme.other/r3')?.textContent).toContain('Writer');
    expect(row('acme.agents/r4')?.textContent).toContain('orchestrator');
    expect(text()).toContain('1 running');
  });

  it('filters by status on the server', async () => {
    const api = fakeApi();
    const m = await open(api);

    await m.click(button('Failed'));
    await m.flush();

    expect(api.runs).toHaveBeenLastCalledWith(expect.objectContaining({ statuses: ['FAILED', 'TIMED_OUT'] }));
    expect(document.querySelectorAll('[data-run]')).toHaveLength(1);
  });

  it('opens a run with its events, error and trace', async () => {
    const m = await open(fakeApi());

    await m.click(row('acme.agents/r2'));
    await m.flush();

    const panel = document.querySelector('[aria-label="Selected agent run"]');
    expect(panel?.textContent).toContain('inv-2');
    expect(panel?.textContent).toContain('Looking it up');
    expect(panel?.textContent).toContain('[DONE]');
    expect(button('Cancel')).toBeNull();
    await m.click(button('Open trace'));
    expect(push).toHaveBeenCalledWith(`/workspace/w1/admin/system?tab=traces&trace=${'c'.repeat(32)}`);

    await m.click(row('acme.other/r3'));
    await m.flush();
  });

  it('cancels a running run after confirming, through the audited API', async () => {
    const api = fakeApi();
    const m = await open(api);

    await m.click(row('acme.agents/r4'));
    await m.flush();
    await m.click(button('Cancel'));
    expect(text()).toContain('Cancel Researcher?');
    await m.click(button('Cancel run'));
    await m.flush();

    expect(api.cancel).toHaveBeenCalledWith('acme.agents', 'r4');
    expect(text()).toContain('Cancellation sent to Researcher');
  });

  it('shows why runs cannot be read', async () => {
    const api = fakeApi();
    api.runs = vi.fn(() =>
      Promise.resolve({ ok: false as const, status: 503, source: 'discovery', reason: 'NATS mode is off' }),
    );

    await open(api);

    expect(text()).toContain('NATS mode is off');
  });
});
