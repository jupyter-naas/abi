/** Test fixtures for the Jobs tab. */
import type { JobView, RunStep, RunSummary } from './jobs-types';

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
  skip_reason: '',
  ...overrides,
});

export const job = (overrides: Partial<JobView> = {}): JobView => ({
  key: 'ops.reports/digest',
  module_id: 'ops.reports',
  name: 'digest',
  description: 'Counts runs.',
  location: 'engine',
  instances: 1,
  kind: 'job',
  input_schema: null,
  output_schema: null,
  triggers: [{ kind: 'every', spec: '10m', time_zone: '', input: null, summary: 'Every 10 minutes', next_at: '2026-10-02T10:10:00+00:00' }],
  next_at: '2026-10-02T10:10:00+00:00',
  max_concurrency: 1,
  max_attempts: 3,
  timeout_seconds: 60,
  queued: 0,
  in_flight: 0,
  running: 0,
  last_run: run(),
  recent: [run()],
  last_skipped: null,
  ...overrides,
});

/** The schema of ``ingest``: a string, an integer, a boolean, an enum, a list of strings and a nested object. */
export const INGEST_SCHEMA = {
  type: 'object',
  title: 'IngestInput',
  properties: {
    filter: { type: 'string', title: 'Filter', description: 'Keyword to search for' },
    limit: { type: 'integer', minimum: 1, default: 10 },
    ratio: { type: 'number' },
    dry_run: { type: 'boolean', default: false },
    mode: { enum: ['fast', 'full'], default: 'fast' },
    tags: { type: 'array', items: { type: 'string' } },
    window: {
      type: 'object',
      properties: { days: { type: 'integer' }, label: { type: 'string' } },
    },
  },
  required: ['filter'],
};

export const workflowJob = (overrides: Partial<JobView> = {}): JobView =>
  job({
    key: 'ops.flows/ingest',
    module_id: 'ops.flows',
    name: 'ingest',
    description: 'Fetches and maps items.',
    location: 'remote',
    kind: 'workflow',
    input_schema: INGEST_SCHEMA,
    output_schema: { type: 'object', properties: { count: { type: 'integer' } } },
    triggers: [
      {
        kind: 'cron',
        spec: '0 0 6 * * *',
        time_zone: 'UTC',
        input: { filter: 'news' },
        summary: 'Every day at 06:00 UTC',
        next_at: '2026-10-03T06:00:00+00:00',
      },
    ],
    last_run: run({ key: 'ops.flows/ingest:5', module_id: 'ops.flows', job: 'ingest', run_id: 'ingest:5' }),
    recent: [run({ key: 'ops.flows/ingest:5', module_id: 'ops.flows', job: 'ingest', run_id: 'ingest:5' })],
    ...overrides,
  });

export const step = (overrides: Partial<RunStep> = {}): RunStep => ({
  key: 'fetch',
  kind: 'step',
  status: 'SUCCEEDED',
  attempt: 1,
  started_at: '2026-10-02T10:00:02+00:00',
  finished_at: '2026-10-02T10:00:03+00:00',
  duration_ms: 1000,
  error: '',
  child: null,
  result_bytes: 64,
  ...overrides,
});
