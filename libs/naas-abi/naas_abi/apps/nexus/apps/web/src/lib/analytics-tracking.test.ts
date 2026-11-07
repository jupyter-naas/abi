// @vitest-environment jsdom
/**
 * The analytics tracker in a view ("View as"): the viewer's page views are not the person's
 * activity, and the server refuses every POST of a view: nothing is sent.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearViewFlag, setViewFlag } from './view-flag';
import { trackEvent, trackPageView } from './analytics-tracking';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 202 })));
});
afterEach(() => {
  clearViewFlag();
  vi.unstubAllGlobals();
});

describe('trackEvent', () => {
  it('posts the event outside a view', () => {
    trackPageView({ workspace_id: 'ws-alpha' });
    expect(fetch).toHaveBeenCalledOnce();
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe('https://api.example.test/api/analytics/events');
  });

  it('sends nothing in a view', () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, Date.now() + 15 * 60_000);
    trackEvent('page_viewed', { workspace_id: 'ws-alpha' });
    trackPageView({ workspace_id: 'ws-alpha' });
    expect(fetch).not.toHaveBeenCalled();
  });
});
