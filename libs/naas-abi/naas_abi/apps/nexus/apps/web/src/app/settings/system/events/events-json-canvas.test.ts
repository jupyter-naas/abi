import { describe, expect, it } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { EventsJsonCanvas, prettyEventJson } from './events-json-canvas';
import type { PlatformEvent } from './bfo-event-projection';

function event(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'evt-1',
    _class_uri: 'https://example.org/Event',
    _seq: 1,
    _stored_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('prettyEventJson', () => {
  it('pretty-prints the event payload', () => {
    const payload = event({ name: 'ping' });
    expect(prettyEventJson(payload)).toBe(JSON.stringify(payload, null, 2));
  });
});

describe('EventsJsonCanvas', () => {
  it('asks the user to select an event when none is resolved', () => {
    const html = renderToStaticMarkup(createElement(EventsJsonCanvas, { event: null }));
    expect(html).toContain('Select an event');
    expect(html).toContain('data-testid="admin-events-json-empty"');
  });
});
