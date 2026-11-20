import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TIMEZONE,
  FALLBACK_TIMEZONES,
  timezoneChange,
  timezoneFrom,
  timezoneLabel,
  timezoneOptions,
} from './timezone';

describe('organization timezone select', () => {
  it('lists the browser timezones, UTC first, then by name', () => {
    const options = timezoneOptions(undefined, () => ['Europe/Paris', 'America/New_York', 'UTC', 'Asia/Tokyo']);
    expect(options).toEqual(['UTC', 'America/New_York', 'Asia/Tokyo', 'Europe/Paris']);
  });

  it('falls back to a short IANA list when the browser cannot list them', () => {
    const missing = timezoneOptions(undefined, null);
    expect(missing[0]).toBe('UTC');
    expect(missing).toContain('Europe/Paris');
    expect(new Set(missing)).toEqual(new Set(FALLBACK_TIMEZONES));
    const throwing = timezoneOptions(undefined, () => {
      throw new RangeError('unsupported');
    });
    expect(throwing).toEqual(missing);
  });

  it('always offers the saved timezone, even one the list lacks', () => {
    expect(timezoneOptions('Antarctica/Troll', () => ['UTC', 'Europe/Paris'])).toEqual([
      'UTC',
      'Antarctica/Troll',
      'Europe/Paris',
    ]);
    expect(timezoneOptions('UTC', () => ['UTC'])).toEqual(['UTC']);
  });

  it('reads the organization timezone, UTC when missing', () => {
    expect(DEFAULT_TIMEZONE).toBe('UTC');
    expect(timezoneFrom({ timezone: 'Europe/Paris' })).toBe('Europe/Paris');
    expect(timezoneFrom({ timezone: '  ' })).toBe('UTC');
    expect(timezoneFrom({})).toBe('UTC');
    expect(timezoneFrom(null)).toBe('UTC');
  });

  it('sends { timezone } in the PATCH body only when it changed', () => {
    expect(timezoneChange('UTC', 'UTC')).toEqual({});
    expect(timezoneChange('UTC', 'Europe/Paris')).toEqual({ timezone: 'Europe/Paris' });
  });

  it('labels a timezone with its current UTC offset', () => {
    const winter = new Date('2026-01-15T12:00:00Z');
    expect(timezoneLabel('UTC', winter)).toBe('UTC');
    expect(timezoneLabel('Europe/Paris', winter)).toBe('Europe/Paris (UTC+01:00)');
    expect(timezoneLabel('Not/AZone', winter)).toBe('Not/AZone');
  });
});
