import { describe, expect, it } from 'vitest';
import { cellText, compareCells, NULL_LABEL } from './table-cells';

describe('cellText', () => {
  it('formats every value type', () => {
    expect(cellText(null)).toBe(NULL_LABEL);
    expect(cellText(undefined)).toBe(NULL_LABEL);
    expect(cellText('owner')).toBe('owner');
    expect(cellText(3)).toBe('3');
    expect(cellText(false)).toBe('false');
    expect(cellText({ a: 1 })).toBe('{"a":1}');
  });
});

describe('compareCells', () => {
  it('sorts NULLs last and numbers by value', () => {
    const values = [null, 10, 2, null, 1];
    expect([...values].sort(compareCells)).toEqual([1, 2, 10, null, null]);
  });

  it('puts true before false and compares text naturally', () => {
    expect([false, true].sort(compareCells)).toEqual([true, false]);
    expect(['ws-10', 'ws-2'].sort(compareCells)).toEqual(['ws-2', 'ws-10']);
  });
});
