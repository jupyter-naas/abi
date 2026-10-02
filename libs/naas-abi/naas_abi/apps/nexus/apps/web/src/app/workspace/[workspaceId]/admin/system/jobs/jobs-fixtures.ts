/** Test fixtures for the Jobs tab. */
import type { JobView, RunSummary } from './jobs-types';

export const run = (overrides: Partial<RunSummary> = {}): RunSummary => ({
  key: 'ops.reports/digest:1',
  module_id: 'ops.reports',
  job: 'digest',
  run_id: 'digest:1',
  status: 'SUCCEEDED',
  attempt: 1,
  max_attempts: 3,
  trigger: { kind: 'schedule', scheduler: 'abi.jobs.zen.schedule.a.b.0' },
  fired_at: '2026-10-02T10:00:00+00:00',
  started_at: '2026-10-02T10:00:02+00:00',
  finished_at: '2026-10-02T10:00:05+00:00',
  duration_ms: 3000,
  instance: 'i-1',
  error: '',
  trace_id: '',
  ...overrides,
});

export const job = (overrides: Partial<JobView> = {}): JobView => ({
  key: 'ops.reports/digest',
  module_id: 'ops.reports',
  name: 'digest',
  description: 'Counts runs.',
  location: 'engine',
  instances: 1,
  triggers: [{ kind: 'every', spec: '10m', time_zone: '', summary: 'Every 10 minutes', next_at: '2026-10-02T10:10:00+00:00' }],
  next_at: '2026-10-02T10:10:00+00:00',
  max_concurrency: 1,
  max_attempts: 3,
  timeout_seconds: 60,
  queued: 0,
  in_flight: 0,
  running: 0,
  last_run: run(),
  recent: [run()],
  ...overrides,
});
