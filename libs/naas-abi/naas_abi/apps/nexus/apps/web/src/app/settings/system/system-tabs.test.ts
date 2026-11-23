import { describe, expect, it } from 'vitest';
import {
  SYSTEM_VIEWS,
  isSystemView,
  legacyDataPath,
  legacySystemTabPath,
  systemTracePath,
  systemViewPath,
} from './system-tabs';

describe('system views', () => {
  it('lists the pages in order, Events last, Access gone to Roles & permissions and Data to the services', () => {
    expect(SYSTEM_VIEWS.map((v) => v.id)).toEqual([
      'overview',
      'services',
      'modules',
      'agents',
      'jobs',
      'nats',
      'traffic',
      'traces',
      'events',
    ]);
    expect(isSystemView('access')).toBe(false);
    expect(isSystemView('data')).toBe(false);
    expect(isSystemView('nats')).toBe(true);
  });

  it('gives System views a path under /settings/system, Activity views under /settings/activity', () => {
    expect(systemViewPath('overview')).toBe('/settings/system');
    expect(systemViewPath('nats')).toBe('/settings/system/nats');
    expect(systemViewPath('traffic')).toBe('/settings/activity/traffic');
    expect(systemViewPath('events')).toBe('/settings/activity/events');
    expect(systemTracePath('a b')).toBe('/settings/activity/traces?trace=a%20b');
  });

  it('sends a link to the old Data tab to the service page, the place in it kept', () => {
    const go = (query: string) => legacyDataPath(new URLSearchParams(query));
    expect(go('service=cache')).toBe('/settings/data/cache');
    expect(go('service=document&in=%5B%5D&item=ns%2Fa')).toBe('/settings/data/documents?in=%5B%5D&item=ns%2Fa');
    expect(go('service=secret')).toBe('/settings/resources/secrets');
    expect(go('')).toBe('/settings/data/knowledge-graph');
  });

  it('turns an old ?tab= link into its page, keeping the other parameters', () => {
    const go = (query: string) => legacySystemTabPath(new URLSearchParams(query));
    expect(go('')).toBe('/settings/system');
    expect(go('tab=nope')).toBe('/settings/system');
    expect(go('tab=jobs&run=ops.billing%2Fsync%3A4')).toBe(
      '/settings/system/jobs?run=ops.billing%2Fsync%3A4'
    );
    expect(go('tab=traces&trace=abc&span=d')).toBe('/settings/activity/traces?trace=abc&span=d');
    expect(go('tab=access')).toBe('/settings/roles');
    expect(go('tab=data&service=cache')).toBe('/settings/data/cache');
  });
});
