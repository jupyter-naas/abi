import { describe, expect, it } from 'vitest';
import {
  appendTraffic,
  liveSourceLabel,
  traceLink,
  filterTraffic,
  parseSseFrames,
  summarizeTraffic,
  type TrafficEvent,
} from './system-traffic-model';

function event(overrides: Partial<TrafficEvent> = {}): TrafficEvent {
  return {
    at: 1_000,
    kind: 'service',
    subject: 'abi.svc.document.v1.get',
    service: 'document',
    method: 'get',
    caller: 'api',
    request_bytes: 10,
    reply_bytes: 20,
    latency_ms: 2,
    status: 'ok',
    error_code: '',
    trace_id: '',
    ...overrides,
  };
}

describe('parseSseFrames', () => {
  it('returns complete data frames and keeps the partial rest', () => {
    const { frames, rest } = parseSseFrames(
      'data: {"type":"status","state":"live"}\n\n: keepalive\n\ndata: {"type":"traffic","eve',
    );

    expect(frames).toEqual([{ type: 'status', state: 'live' }]);
    expect(rest).toBe('data: {"type":"traffic","eve');
  });

  it('skips frames that are not JSON', () => {
    expect(parseSseFrames('data: nope\n\ndata: {"a":1}\n\n').frames).toEqual([{ a: 1 }]);
  });
});

describe('traffic model', () => {
  it('keeps the newest events first, bounded', () => {
    const list = appendTraffic([event({ at: 1 })], [event({ at: 2 }), event({ at: 3 })], 2);

    expect(list.map((e) => e.at)).toEqual([3, 2]);
  });

  it('filters by kind, text and errors', () => {
    const events = [
      event({ at: 1 }),
      event({ at: 2, kind: 'discovery', service: 'zen', method: 'list_modules', subject: 'abi.discovery.zen.v1.list_modules' }),
      event({ at: 3, status: 'error', error_code: 'NOT_FOUND', caller: 'ops.researcher@host' }),
    ];

    expect(filterTraffic(events, { kind: 'discovery', text: '', errorsOnly: false }).map((e) => e.at)).toEqual([2]);
    expect(filterTraffic(events, { kind: 'all', text: 'researcher', errorsOnly: false }).map((e) => e.at)).toEqual([3]);
    expect(filterTraffic(events, { kind: 'all', text: '', errorsOnly: true }).map((e) => e.at)).toEqual([3]);
  });

  it('summarizes calls per service and method', () => {
    const summary = summarizeTraffic([
      event({ latency_ms: 2 }),
      event({ latency_ms: 4, status: 'error', error_code: 'X' }),
      event({ kind: 'event', service: 'abc', method: 'publish', latency_ms: null, reply_bytes: null, status: 'published' }),
    ]);

    expect(summary).toEqual([
      { key: 'service document.get', kind: 'service', service: 'document', method: 'get', calls: 2, errors: 1, averageMs: 3, bytes: 60 },
      { key: 'event abc.publish', kind: 'event', service: 'abc', method: 'publish', calls: 1, errors: 0, averageMs: 0, bytes: 10 },
    ]);
  });
});

describe('traceLink', () => {
  it('opens the trace in the configured viewer', () => {
    expect(traceLink('http://localhost:16686/', 'abc')).toBe('http://localhost:16686/trace/abc');
    expect(traceLink(null, 'abc')).toBeNull();
    expect(traceLink('http://localhost:16686', '')).toBeNull();
  });
});

describe('liveSourceLabel', () => {
  it('names the source and why the preferred one was skipped', () => {
    expect(liveSourceLabel('traces', {})).toBe('Live from traces');
    expect(liveSourceLabel('nats', {})).toBe('Live from the NATS bus');
    expect(liveSourceLabel('nats', { tracing: 'connection refused' })).toBe(
      'Live from the NATS bus (tracing unavailable: connection refused)',
    );
    expect(liveSourceLabel(null, {})).toBe('Live');
  });
});
