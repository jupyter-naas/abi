import { describe, expect, it } from 'vitest';
import {
  decodeJobsLocation,
  encodeJobsLocation,
  filterJobs,
  formatMs,
  health,
  isWorkflow,
  moduleLabel,
  runDuration,
  sortJobs,
  splitKey,
  startDelay,
  statusLabel,
  statusTone,
  stepBars,
  truncatedResult,
} from './jobs-model';
import { STATUS_FILTERS } from './runs-list';
import { job, run, step, workflowJob } from './jobs-fixtures';

describe('jobs model', () => {
  it('formats durations and delays', () => {
    expect(formatMs(820)).toBe('820 ms');
    expect(formatMs(4200)).toBe('4.2 s');
    expect(formatMs(185_000)).toBe('3 min 05 s');
    expect(formatMs(4_320_000)).toBe('1 h 12 min');
    expect(formatMs(null)).toBe('—');
    expect(startDelay(run())).toBe(2000);
    const live = run({ status: 'RUNNING', finished_at: null, duration_ms: null });
    expect(runDuration(live, Date.parse('2026-10-02T10:00:12+00:00'))).toBe(10_000);
  });

  it('measures health over finished runs', () => {
    const h = health([run(), run({ status: 'FAILED', duration_ms: 1000 }), run({ status: 'RUNNING', duration_ms: null })]);
    expect(h).toMatchObject({ total: 2, succeeded: 1, failed: 1, rate: 0.5, averageMs: 2000 });
    expect(health([]).rate).toBeNull();
  });

  it('puts failing then running jobs first, then the next tick', () => {
    const later = job({ key: 'a/later', name: 'later', next_at: '2026-10-02T12:00:00Z' });
    const soon = job({ key: 'b/soon', name: 'soon', next_at: '2026-10-02T10:01:00Z' });
    const failing = job({ key: 'c/failing', last_run: run({ status: 'FAILED' }) });
    const busy = job({ key: 'd/busy', running: 1 });
    expect(sortJobs([later, soon, failing, busy]).map((j) => j.key)).toEqual(['c/failing', 'd/busy', 'b/soon', 'a/later']);
    expect(filterJobs([later, soon], 'SOON').map((j) => j.key)).toEqual(['b/soon']);
  });

  it('round-trips the location and splits keys', () => {
    const location = {
      view: 'runs' as const,
      job: 'ops.reports/digest',
      run: 'ops.reports/digest:7',
      statuses: ['FAILED', 'TIMED_OUT'],
      kind: 'workflow' as const,
    };
    expect(decodeJobsLocation(encodeJobsLocation(location, new URLSearchParams('tab=jobs')))).toEqual(location);
    expect(splitKey('ops.reports/digest:7')).toEqual(['ops.reports', 'digest:7']);
    expect(moduleLabel('operations.projects.nats_probe.researcher')).toBe('researcher');
    expect([statusTone('SUCCEEDED'), statusTone('FAILED'), statusTone('RETRYING')]).toEqual(['success', 'danger', 'warn']);
  });

  it('treats skipped runs as nothing to do, never as failures', () => {
    expect(statusLabel('SKIPPED')).toBe('Skipped');
    expect(statusTone('SKIPPED')).toBe('neutral');
    const h = health([run(), run({ status: 'SKIPPED', duration_ms: 5 }), run({ status: 'FAILED', duration_ms: 1000 })]);
    expect(h).toMatchObject({ total: 2, succeeded: 1, failed: 1, rate: 0.5, averageMs: 2000 });
    expect(STATUS_FILTERS.find((f) => f.id === 'skipped')?.statuses).toEqual(['SKIPPED']);
  });
});

describe('workflows in the jobs model', () => {
  it('filters by kind, then by text', () => {
    const plain = job();
    const flow = workflowJob();

    expect([plain, flow].map(isWorkflow)).toEqual([false, true]);
    expect(filterJobs([plain, flow], '', 'workflow').map((j) => j.key)).toEqual(['ops.flows/ingest']);
    expect(filterJobs([plain, flow], '', 'job').map((j) => j.key)).toEqual(['ops.reports/digest']);
    expect(filterJobs([plain, flow], 'INGEST', 'all').map((j) => j.key)).toEqual(['ops.flows/ingest']);
    expect(filterJobs([plain, flow], 'ingest', 'job')).toEqual([]);
    expect(filterJobs([plain, flow], '')).toHaveLength(2);
  });

  it('keeps the kind filter in the URL only when it is not "all"', () => {
    const base = { view: 'jobs' as const, job: null, run: null, statuses: [] };

    expect(encodeJobsLocation({ ...base, kind: 'all' }, new URLSearchParams('tab=jobs')).toString()).toBe('tab=jobs');
    expect(encodeJobsLocation({ ...base, kind: 'workflow' }, new URLSearchParams('tab=jobs')).toString()).toBe('tab=jobs&kind=workflow');
    expect(decodeJobsLocation(new URLSearchParams('kind=workflow')).kind).toBe('workflow');
    expect(decodeJobsLocation(new URLSearchParams('kind=nonsense')).kind).toBe('all');
  });

  it('lays the steps out on one time axis', () => {
    const bars = stepBars([
      step({ key: 'a', started_at: '2026-10-02T10:00:00+00:00', finished_at: '2026-10-02T10:00:02+00:00', duration_ms: 2000 }),
      step({ key: 'b', started_at: '2026-10-02T10:00:02+00:00', finished_at: '2026-10-02T10:00:08+00:00', duration_ms: 6000 }),
      step({ key: 'c', started_at: '2026-10-02T10:00:08+00:00', finished_at: '2026-10-02T10:00:10+00:00', duration_ms: 2000 }),
    ]);

    expect(bars.map((b) => [b.step.key, b.offsetMs, b.durationMs])).toEqual([
      ['a', 0, 2000],
      ['b', 2000, 6000],
      ['c', 8000, 2000],
    ]);
    expect(bars.map((b) => Math.round(b.left))).toEqual([0, 20, 80]);
    expect(bars.map((b) => Math.round(b.width))).toEqual([20, 60, 20]);
  });

  it('times a running step against now, and draws a very short one as a mark', () => {
    const now = Date.parse('2026-10-02T10:00:05+00:00');
    const bars = stepBars(
      [
        step({ key: 'done', started_at: '2026-10-02T10:00:00+00:00', finished_at: '2026-10-02T10:00:00.010+00:00', duration_ms: 10 }),
        step({ key: 'live', status: 'RUNNING', started_at: '2026-10-02T10:00:01+00:00', finished_at: null, duration_ms: null }),
        step({ key: 'later', status: 'RUNNING', started_at: null, finished_at: null, duration_ms: null }),
      ],
      now,
    );

    expect(bars[0].width).toBeGreaterThanOrEqual(0.8);
    expect([bars[1].offsetMs, bars[1].durationMs]).toEqual([1000, 4000]);
    expect([bars[2].offsetMs, bars[2].durationMs]).toEqual([null, null]);
    expect(stepBars([])).toEqual([]);
  });

  it('recognises a result cut for display', () => {
    expect(truncatedResult({ truncated: true, bytes: 20000, preview: '{"rows"' })).toEqual({ bytes: 20000, preview: '{"rows"' });
    // the job host's own marker has no byte count
    expect(truncatedResult({ truncated: true, preview: '{"rows"' })).toEqual({ preview: '{"rows"' });
    expect(truncatedResult({ truncated: true })).toBeNull();
    expect(truncatedResult({ truncated: false, preview: 'x' })).toBeNull();
    expect(truncatedResult({ count: 3 })).toBeNull();
    expect(truncatedResult(null)).toBeNull();
    expect(truncatedResult('text')).toBeNull();
  });
});
