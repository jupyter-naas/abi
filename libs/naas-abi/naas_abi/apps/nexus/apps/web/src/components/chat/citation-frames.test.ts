// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import {
  appOrigins,
  createProbeFrame,
  isAppOrigin,
  PREVIEW_FRAME_SANDBOX,
  PROBE_FRAME_SANDBOX,
} from './citation-frames';

const WEB = 'https://nexus.example.com/workspace/w/chat';
const API = 'https://api.nexus.example.com';

describe('citation frames', () => {
  it('keeps pages of the app and of the API out of every frame', () => {
    const origins = appOrigins(API, WEB);
    expect(origins).toEqual(['https://nexus.example.com', 'https://api.nexus.example.com']);
    for (const url of [
      'https://nexus.example.com/api/image-data?raw=1&url=https%3A%2F%2Fx.example%2Fa',
      'https://nexus.example.com/app-html/x/index.html',
      'https://api.nexus.example.com/api/files/a',
      'javascript:alert(1)',
      'data:text/html,<script>1</script>',
      'not a url',
    ]) {
      expect(isAppOrigin(url, origins), url).toBe(true);
    }
    expect(isAppOrigin('https://example.org/article', origins)).toBe(false);
    // A relative API base is this app's own origin.
    expect(appOrigins('/', WEB)).toEqual(['https://nexus.example.com', 'https://nexus.example.com']);
  });

  it('keeps the probe frame without script and without an origin of the app', () => {
    const frame = createProbeFrame('https://example.org/article');
    expect(frame.hasAttribute('sandbox')).toBe(true);
    expect(frame.getAttribute('sandbox')).toBe(PROBE_FRAME_SANDBOX);
    expect(PROBE_FRAME_SANDBOX).toBe('');
    expect(frame.getAttribute('referrerpolicy')).toBe('no-referrer');
    expect(frame.isConnected).toBe(false);
  });

  it('keeps the preview frame off the app origin', () => {
    const tokens = PREVIEW_FRAME_SANDBOX.split(/\s+/);
    expect(tokens).not.toContain('allow-same-origin');
    expect(tokens).not.toContain('allow-top-navigation');
  });
});
