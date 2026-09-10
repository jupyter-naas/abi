import { describe, expect, it } from 'vitest';
import type { PlatformEvent } from './bfo-event-projection';
import {
  eventKind,
  formatRelativeTime,
  projectEventToFeedItem,
  shortenFeedId,
} from './event-feed';

function baseEvent(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'http://ontology.naas.ai/abi/object_storage/evt-1',
    _class_uri: 'http://ontology.naas.ai/abi/object_storage/ObjectPut',
    _seq: 269184,
    _stored_at: '2026-09-10T00:36:00Z',
    _site: 'localhost',
    ...overrides,
  };
}

describe('projectEventToFeedItem', () => {
  it('builds a 3-line card from process, object id, site, and seq', () => {
    const now = Date.parse('2026-09-10T00:36:36Z');
    const item = projectEventToFeedItem(baseEvent({ key: 'logo.svg' }), now);
    expect(item.kind).toBe('object');
    expect(item.line1).toBe('ObjectPut');
    expect(item.line2).toBe('logo.svg');
    expect(item.line3).toBe('localhost · seq 269184');
    expect(item.line4).toBeNull();
    expect(item.timeLabel).toBe('36s ago');
  });

  it('omits Unknown buckets instead of printing them', () => {
    const item = projectEventToFeedItem(baseEvent());
    expect(item.line1).toBe('ObjectPut');
    expect(item.line2).toBe('evt-1');
    expect(item.line3).toBe('localhost · seq 269184');
    expect(item.line4).toBeNull();
    expect(JSON.stringify(item)).not.toMatch(/Unknown/);
  });

  it('shortens a long object key on line 2', () => {
    const item = projectEventToFeedItem(
      baseEvent({ key: '9340bdb29cc66744383b444ed0123456789abcdef' }),
    );
    expect(item.line2).toBe('9340bdb29c...');
    expect(item.line2.length).toBeLessThan(20);
  });

  it('puts actor and process on line 1 and quality plus realizable on line 4', () => {
    const item = projectEventToFeedItem(
      baseEvent({
        _class_uri: 'http://ontology.naas.ai/abi/agent/AgentToolCalled',
        agent_name: 'ResearchAgent',
        tool_name: 'search',
        status: 'ok',
        latency_ms: 12,
      }),
    );
    expect(item.line1).toBe('ResearchAgent · AgentToolCalled');
    expect(item.line2).toBe('evt-1');
    expect(item.line3).toBe('localhost · seq 269184');
    expect(item.line4).toBe('ok · 12ms · search');
  });
});

describe('shortenFeedId', () => {
  it('keeps a short last segment and trims a long one', () => {
    expect(shortenFeedId('http://ontology.naas.ai/abi/object_storage/evt-1')).toBe('evt-1');
    expect(shortenFeedId('9340bdb29cc66744383b444ed0123456789abcdef')).toBe('9340bdb29c...');
  });
});

describe('eventKind', () => {
  it('classifies agent and error types', () => {
    expect(
      eventKind(baseEvent({ _class_uri: 'http://ontology.naas.ai/abi/agent/AgentRouted' })),
    ).toBe('agent');
    expect(
      eventKind(baseEvent({ _class_uri: 'http://ontology.naas.ai/abi/bus/BusError' })),
    ).toBe('error');
  });
});

describe('formatRelativeTime', () => {
  it('uses minutes after 60 seconds', () => {
    const now = Date.parse('2026-09-10T00:38:00Z');
    expect(formatRelativeTime('2026-09-10T00:36:00Z', now)).toBe('2m ago');
  });
});
