import { describe, expect, it } from 'vitest';
import { formatBytes, formatCount, formatExpiry, formatMs, sourceLabel } from './system-format';

describe('system format', () => {
  it('formats byte sizes with binary units', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1536)).toBe('1.5 KiB');
    expect(formatBytes(8 * 1024 * 1024)).toBe('8 MiB');
  });

  it('formats counts compactly', () => {
    expect(formatCount(999)).toBe('999');
    expect(formatCount(12_345)).toBe('12.3k');
    expect(formatCount(2_500_000)).toBe('2.5M');
  });

  it('formats milliseconds', () => {
    expect(formatMs(0)).toBe('–');
    expect(formatMs(0.42)).toBe('0.42 ms');
    expect(formatMs(1500)).toBe('1.5 s');
  });

  it('formats a lease expiry relative to now', () => {
    const now = 1_000_000;
    expect(formatExpiry(now + 130, now)).toBe('in 2m 10s');
    expect(formatExpiry(now + 5, now)).toBe('in 5s');
    expect(formatExpiry(now - 3, now)).toBe('expired');
  });

  it('names every source the API reports', () => {
    expect(sourceLabel('nats')).toBe('NATS services');
    expect(sourceLabel('nats_monitor')).toBe('NATS monitoring');
    expect(sourceLabel('discovery')).toBe('Discovery');
    expect(sourceLabel('something_else')).toBe('something_else');
  });
});
