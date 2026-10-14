import { describe, expect, it } from 'vitest';
import {
  decodeJobsLocation,
  encodeJobsLocation,
  filterJobs,
  formatMs,
  health,
  moduleLabel,
  runDuration,
  sortJobs,
  splitKey,
  startDelay,
  statusLabel,
  statusTone,
} from './jobs-model';
import { STATUS_FILTERS } from './runs-list';
import { job, run } from './jobs-fixtures';

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
    const location = { view: 'runs' as const, job: 'ops.reports/digest', run: 'ops.reports/digest:7', statuses: ['FAILED', 'TIMED_OUT'] };
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
