import { describe, expect, it } from 'vitest';
import {
  SYSTEM_VIEWS,
  isSystemView,
  legacySystemTabPath,
  systemTracePath,
  systemViewPath,
} from './system-tabs';

describe('system views', () => {
  it('lists the pages in order, Events last and Access gone to Roles & permissions', () => {
    expect(SYSTEM_VIEWS.map((v) => v.id)).toEqual([
      'overview',
      'services',
      'data',
      'jobs',
      'agents',
      'modules',
      'nats',
      'traffic',
      'traces',
      'events',
    ]);
    expect(isSystemView('access')).toBe(false);
    expect(isSystemView('nats')).toBe(true);
  });

  it('gives each one a path under /settings/system', () => {
    expect(systemViewPath('overview')).toBe('/settings/system');
    expect(systemViewPath('traffic')).toBe('/settings/system/traffic');
    expect(systemTracePath('a b')).toBe('/settings/system/traces?trace=a%20b');
  });

  it('turns an old ?tab= link into its page, keeping the other parameters', () => {
    const go = (query: string) => legacySystemTabPath(new URLSearchParams(query));
    expect(go('')).toBe('/settings/system');
    expect(go('tab=nope')).toBe('/settings/system');
    expect(go('tab=jobs&run=ops.billing%2Fsync%3A4')).toBe(
      '/settings/system/jobs?run=ops.billing%2Fsync%3A4'
    );
    expect(go('tab=traces&trace=abc&span=d')).toBe('/settings/system/traces?trace=abc&span=d');
    expect(go('tab=access')).toBe('/settings/roles');
  });
});
