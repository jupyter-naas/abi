import { describe, expect, it } from 'vitest';
import { isActive, isCancellable, runDuration, splitKey, statusLabel, statusTone } from './agents-model';
import type { AgentRunSummary } from './agents-types';

const run = (patch: Partial<AgentRunSummary> = {}): AgentRunSummary => ({
  key: 'acme.agents/r1',
  module_id: 'acme.agents',
  run_id: 'r1',
  agent: 'Researcher',
  invocation_id: 'inv-1',
  status: 'RUNNING',
  thread_id: 't-1',
  caller: 'api',
  owner: 'i-1',
  submitted_at: '2026-10-02T09:00:00+00:00',
  finished_at: null,
  duration_ms: null,
  error_code: '',
  error_message: '',
  trace_id: '',
  events: 0,
  ...patch,
});

describe('agents model', () => {
  it('labels and colors every status', () => {
    expect(statusLabel('TIMED_OUT')).toBe('Timed out');
    expect(statusLabel('SOMETHING_NEW')).toBe('Something_new');
    expect(statusTone('FAILED')).toBe('danger');
    expect(statusTone('CANCELLING')).toBe('warn');
    expect(statusTone('CANCELLED')).toBe('neutral');
  });

  it('cancels only what the host still executes', () => {
    expect(isActive('CANCELLING') && !isCancellable('CANCELLING')).toBe(true);
    expect(isCancellable('ACCEPTED') && isCancellable('RUNNING')).toBe(true);
    expect(isCancellable('SUCCEEDED')).toBe(false);
  });

  it('measures finished runs and the live ones up to now', () => {
    expect(runDuration(run({ duration_ms: 12500, status: 'SUCCEEDED' }))).toBe(12500);
    expect(runDuration(run(), Date.parse('2026-10-02T09:00:04+00:00'))).toBe(4000);
    expect(runDuration(run({ submitted_at: null }))).toBeNull();
    expect(runDuration(run({ status: 'FAILED' }))).toBeNull();
  });

  it('splits run keys on the first slash', () => {
    expect(splitKey('acme.agents/abc')).toEqual(['acme.agents', 'abc']);
  });
});
