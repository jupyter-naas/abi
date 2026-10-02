/** Test data for the trace viewer. */
import type { Span, Trace, TraceSummary } from './traces-types';

export const TRACE_ID = '4bf92f3577b34da6a3ce929d0e0e4736';

export function span(overrides: Partial<Span> & Pick<Span, 'span_id'>): Span {
  return {
    parent_id: null,
    name: 'op',
    service: 'nexus-api',
    kind: 'internal',
    start_ms: 0,
    duration_ms: 1,
    status: 'unset',
    status_message: '',
    attributes: {},
    resource: {},
    events: [],
    links: [],
    ...overrides,
  };
}

/** GET /jobs/run → job digest → document.get + vector.search (the second fails). */
export function trace(overrides: Partial<Trace> = {}): Trace {
  const spans = [
    span({ span_id: 'a', name: 'POST /api/admin/system/jobs/run', kind: 'server', duration_ms: 120, status: 'ok', attributes: { 'http.method': 'POST', 'http.status_code': 202 } }),
    span({ span_id: 'b', parent_id: 'a', name: 'job digest', service: 'ops.reports', start_ms: 10, duration_ms: 100, attributes: { 'abi.job': 'digest' }, events: [{ name: 'started', offset_ms: 1, attributes: {} }] }),
    span({ span_id: 'c', parent_id: 'b', name: 'document.get', service: 'document', kind: 'client', start_ms: 20, duration_ms: 30, attributes: { 'rpc.method': 'get' } }),
    span({ span_id: 'd', parent_id: 'b', name: 'vector.search', service: 'vector', kind: 'client', start_ms: 40, duration_ms: 50, status: 'error', status_message: 'collection missing', links: [{ trace_id: 'f'.repeat(32), span_id: 'e' }] }),
  ];
  return {
    trace_id: TRACE_ID,
    start: '2026-10-02T12:00:00Z',
    duration_ms: 120,
    services: [
      { name: 'nexus-api', spans: 1, errors: 0 },
      { name: 'ops.reports', spans: 1, errors: 0 },
      { name: 'document', spans: 1, errors: 0 },
      { name: 'vector', spans: 1, errors: 1 },
    ],
    spans,
    truncated: false,
    ...overrides,
  };
}

export function summary(overrides: Partial<TraceSummary> = {}): TraceSummary {
  return {
    trace_id: TRACE_ID,
    root: { service: 'nexus-api', name: 'POST /api/admin/system/jobs/run' },
    start: '2026-10-02T12:00:00Z',
    duration_ms: 120,
    spans: 4,
    errors: 1,
    services: trace().services,
    ...overrides,
  };
}

export const POLLING_ID = 'a'.repeat(32);

/** A chat stream: submit, then 6 status polls 100 ms apart (the fourth fails), each reading one document. */
export function pollingTrace(): Trace {
  const polls = Array.from({ length: 6 }, (_, i) => [
    span({ span_id: `p${i}`, parent_id: 'r', name: 'agent/status', kind: 'client', start_ms: 50 + i * 100, duration_ms: 10, status: i === 3 ? 'error' : 'unset' }),
    span({ span_id: `g${i}`, parent_id: `p${i}`, name: 'document/get', service: 'document', start_ms: 52 + i * 100, duration_ms: 5 }),
  ]).flat();
  const spans = [
    span({ span_id: 'r', name: 'POST /api/chat/stream', kind: 'server', duration_ms: 700 }),
    span({ span_id: 's', parent_id: 'r', name: 'agent/submit', kind: 'client', start_ms: 10, duration_ms: 30 }),
    ...polls,
  ];
  return {
    trace_id: POLLING_ID,
    start: '2026-10-02T12:00:00Z',
    duration_ms: 700,
    services: [
      { name: 'nexus-api', spans: 8, errors: 1 },
      { name: 'document', spans: 6, errors: 0 },
    ],
    spans,
    truncated: false,
  };
}
