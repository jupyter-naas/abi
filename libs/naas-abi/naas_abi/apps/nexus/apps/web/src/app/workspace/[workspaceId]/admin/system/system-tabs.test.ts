import { describe, expect, it } from 'vitest';
import { SYSTEM_TABS, parseSystemTab } from './system-tabs';

describe('system tabs', () => {
  it('lists the tabs in order', () => {
    expect(SYSTEM_TABS.map((t) => t.id)).toEqual(['overview', 'services', 'data', 'jobs', 'modules', 'nats', 'traffic', 'traces']);
  });

  it('falls back to the overview for missing or unknown tabs', () => {
    expect(parseSystemTab(null)).toBe('overview');
    expect(parseSystemTab('nope')).toBe('overview');
    expect(parseSystemTab('nats')).toBe('nats');
  });
});
