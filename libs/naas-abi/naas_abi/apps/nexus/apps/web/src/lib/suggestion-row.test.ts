import { describe, expect, it } from 'vitest';

import { activeSuggestions, suggestionRowNavState, suggestionScrollStep } from './suggestion-row';

describe('activeSuggestions', () => {
  it('returns an empty list when the input is missing', () => {
    expect(activeSuggestions(undefined)).toEqual([]);
    expect(activeSuggestions(null)).toEqual([]);
  });

  it('drops disabled chips and keeps the rest', () => {
    expect(
      activeSuggestions([
        { label: 'Ask', value: 'ask' },
        { label: 'Soon', value: 'soon', disabled: true },
        { label: 'Apps', value: 'apps', disabled: false },
      ]),
    ).toEqual([
      { label: 'Ask', value: 'ask' },
      { label: 'Apps', value: 'apps', disabled: false },
    ]);
  });
});

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
