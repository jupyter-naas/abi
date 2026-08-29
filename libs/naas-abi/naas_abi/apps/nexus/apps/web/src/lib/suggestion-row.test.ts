import { describe, expect, it } from 'vitest';

import { suggestionRowNavState, suggestionScrollStep } from './suggestion-row';

describe('suggestionRowNavState', () => {
  it('hides arrows when the row fits', () => {
    expect(suggestionRowNavState(0, 400, 360)).toEqual({
      overflow: false,
      canPrev: false,
      canNext: false,
    });
  });

  it('enables next at the start of an overflowing row', () => {
    expect(suggestionRowNavState(0, 400, 900)).toEqual({
      overflow: true,
      canPrev: false,
      canNext: true,
    });
  });

  it('enables prev at the end of an overflowing row', () => {
    expect(suggestionRowNavState(500, 400, 900)).toEqual({
      overflow: true,
      canPrev: true,
      canNext: false,
    });
  });

  it('enables both arrows in the middle', () => {
    expect(suggestionRowNavState(200, 400, 900)).toEqual({
      overflow: true,
      canPrev: true,
      canNext: true,
    });
  });
});

describe('suggestionScrollStep', () => {
  it('uses three quarters of the visible width, with a 160px floor', () => {
    expect(suggestionScrollStep(400)).toBe(300);
    expect(suggestionScrollStep(100)).toBe(160);
  });
});
