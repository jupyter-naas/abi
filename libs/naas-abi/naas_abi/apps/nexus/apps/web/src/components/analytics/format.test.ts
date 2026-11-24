import { describe, expect, it } from 'vitest';
import { formatBucket, formatDateTime, safeTimeZone } from './format';

describe('formatBucket', () => {
  it('labels an hourly bucket by its wall-clock hour, never shifted to the browser timezone', () => {
    expect(formatBucket('2026-11-19T00', 'hour')).toBe('00:00');
    expect(formatBucket('2026-11-19T23', 'hour')).toBe('23:00');
    expect(formatBucket('2026-11-19T07', 'hour', true)).toMatch(/19.*07:00/);
  });

  it('labels a daily bucket by its day', () => {
    expect(formatBucket('2026-11-01', 'day')).toMatch(/1/);
    expect(formatBucket('2026-11-01', 'day')).not.toMatch(/Oct|31/);
  });

  it('leaves an unknown bucket as is', () => {
    expect(formatBucket('week-47', 'day')).toBe('week-47');
  });
});

describe('times in the organization timezone', () => {
  it('formats in the given IANA timezone', () => {
    const iso = '2026-11-19T23:30:00Z';
    expect(formatDateTime(iso, 'Asia/Tokyo')).toMatch(/20/); // Nov 20, 08:30 in Tokyo
    expect(formatDateTime(iso, 'UTC')).toMatch(/19/);
  });

  it('ignores an unknown timezone name', () => {
    expect(safeTimeZone('Not/AZone')).toBeUndefined();
    expect(safeTimeZone('Europe/Paris')).toBe('Europe/Paris');
    expect(safeTimeZone(null)).toBeUndefined();
  });
});
