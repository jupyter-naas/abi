import { describe, expect, it } from 'vitest';
import { pageWindow } from './pagination';

describe('pageWindow', () => {
  it('splits rows into pages of 100', () => {
    expect(pageWindow(371, 0)).toEqual({ page: 0, pageCount: 4, start: 0, end: 100 });
    expect(pageWindow(371, 3)).toEqual({ page: 3, pageCount: 4, start: 300, end: 371 });
  });

  it('snaps out-of-range pages and handles empty tables', () => {
    expect(pageWindow(371, 9).page).toBe(3);
    expect(pageWindow(371, -1).page).toBe(0);
    expect(pageWindow(0, 0)).toEqual({ page: 0, pageCount: 1, start: 0, end: 0 });
  });
});
