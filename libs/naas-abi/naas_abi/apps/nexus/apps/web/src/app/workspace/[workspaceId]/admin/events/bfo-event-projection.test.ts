import { describe, expect, it } from 'vitest';
import {
  BFO_COLUMNS,
  UNKNOWN,
  projectEventToBfo,
  type PlatformEvent,
} from './bfo-event-projection';

function baseEvent(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'http://ontology.naas.ai/abi/agent/evt-1',
    _class_uri: 'http://ontology.naas.ai/abi/agent/AgentToolCalled',
    _seq: 42,
    _stored_at: '2026-07-31T12:00:00Z',
    ...overrides,
  };
}

describe('projectEventToBfo', () => {
  it('uses book column order', () => {
    expect(BFO_COLUMNS.map((c) => c.key)).toEqual([
      'materialEntity',
      'process',
      'site',
      'ice',
      'quality',
      'realizable',
      'temporalRegion',
    ]);
  });

  it('maps ICE, site, process, and temporal from stored event metadata', () => {
    const buckets = projectEventToBfo(
      baseEvent({
        _site: 'deploy.example',
        created_at: '2026-07-31T12:01:00Z',
        user_id: 'user-123',
        tool_name: 'search',
        status: 'ok',
        latency_ms: 12,
      })
    );

    expect(buckets.ice).toBe('event-log#seq=42');
    expect(buckets.site).toBe('deploy.example');
    expect(buckets.process).toBe('AgentToolCalled');
    expect(buckets.temporalRegion).toBe('2026-07-31T12:01:00Z');
    expect(buckets.materialEntity).toBe('user-123');
    expect(buckets.realizable).toBe('search');
    expect(buckets.quality).toBe('ok · 12ms');
  });

  it('falls back to Unknown for unmapped material, quality, realizable', () => {
    const buckets = projectEventToBfo(baseEvent({ _site: 'deploy.example' }));
    expect(buckets.materialEntity).toBe(UNKNOWN);
    expect(buckets.quality).toBe(UNKNOWN);
    expect(buckets.realizable).toBe(UNKNOWN);
    expect(buckets.ice).not.toBe(UNKNOWN);
    expect(buckets.site).not.toBe(UNKNOWN);
  });

  it('uses Unknown for site when deploy host is absent', () => {
    const buckets = projectEventToBfo(baseEvent());
    expect(buckets.site).toBe(UNKNOWN);
  });

  it('uses agent_name as material when user_id is absent', () => {
    const buckets = projectEventToBfo(baseEvent({ agent_name: 'ResearchAgent' }));
    expect(buckets.materialEntity).toBe('ResearchAgent');
  });

  it('uses event URI for ICE when seq is missing', () => {
    const buckets = projectEventToBfo(
      baseEvent({ _seq: null, _uri: 'http://example.com/e1' })
    );
    expect(buckets.ice).toBe('http://example.com/e1');
  });
});
