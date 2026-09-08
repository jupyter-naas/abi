import { describe, expect, it } from 'vitest';

import {
  activeSuggestions,
  suggestionHint,
  suggestionRowNavState,
  suggestionScrollStep,
} from './suggestion-row';

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

describe('suggestionHint', () => {
  it('prefers a trimmed description', () => {
    expect(
      suggestionHint({
        description: '  2 to 4 web searches, then 6-8 researched slides  ',
        value: 'Create a briefing on what is going on now.',
      }),
    ).toBe('2 to 4 web searches, then 6-8 researched slides');
  });

  it('falls back to the first line of the prompt', () => {
    expect(
      suggestionHint({
        value: 'Write a 6-slide company briefing.\nKeep the template CSS.',
      }),
    ).toBe('Write a 6-slide company briefing.');
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
