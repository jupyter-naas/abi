/** Wire types of /api/admin/system/jobs (sysadmin jobs domain). */

/** SKIPPED: the run had nothing to do (the handler called ctx.skip); hidden by default. */
export type RunStatus = 'RUNNING' | 'RETRYING' | 'SUCCEEDED' | 'SKIPPED' | 'FAILED' | 'TIMED_OUT' | 'CANCELLED';

export interface JobTrigger {
  kind: 'cron' | 'every' | 'event' | string;
  spec: string;
  time_zone: string;
  summary: string;
  next_at: string | null;
}

export interface RunSummary {
  key: string;
  module_id: string;
  job: string;
  run_id: string;
  status: RunStatus | string;
  attempt: number;
  max_attempts: number;
  trigger: { kind: 'schedule' | 'manual' | 'event' | string; scheduler: string };
  fired_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  instance: string;
  error: string;
  trace_id: string;
  skip_reason: string;
}

export interface RunDetail extends RunSummary {
  payload: unknown;
  result: unknown;
  logs: string[];
  trace_url: string | null;
}

export interface JobView {
  key: string;
  module_id: string;
  name: string;
  description: string;
  location: 'engine' | 'remote' | string;
  instances: number;
  triggers: JobTrigger[];
  next_at: string | null;
  max_concurrency: number;
  max_attempts: number;
  timeout_seconds: number | null;
  queued: number | null;
  in_flight: number | null;
  running: number;
  last_run: RunSummary | null;
  recent: RunSummary[];
  /** The latest run that had nothing to do (not in ``recent``). */
  last_skipped: RunSummary | null;
}

export interface SourceStatus {
  available: boolean;
  reason: string;
}

export interface JobsOverview {
  project: string;
  jobs: JobView[];
  sources: Record<string, SourceStatus>;
}

export interface RunsPage {
  runs: RunSummary[];
  next: string | null;
}

/** Runs that failed or timed out since ``since`` (the Jobs notification). */
export interface JobFailures {
  since: string;
  count: number;
  more: boolean;
  runs: RunSummary[];
}
