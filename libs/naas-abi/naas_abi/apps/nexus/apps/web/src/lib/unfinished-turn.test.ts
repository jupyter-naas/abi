import { describe, expect, it } from 'vitest';

import { endsOnUnfinishedTurn } from './unfinished-turn';

const ask = { role: 'user', content: 'List the files in my workspace' };

describe('endsOnUnfinishedTurn', () => {
  it('is true for the caret a stream left when its page went away', () => {
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: '▌' }])).toBe(true);
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: 'Here are▌' }])).toBe(true);
  });

  it('is true for the empty row the server fills when the turn ends', () => {
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: '' }])).toBe(true);
  });

  it('is false for a finished answer, a question waiting, or an empty thread', () => {
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: 'Nine folders.' }])).toBe(false);
    expect(endsOnUnfinishedTurn([ask])).toBe(false);
    expect(endsOnUnfinishedTurn([])).toBe(false);
  });

  it('is false for structured content', () => {
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: [{ type: 'image' }] }])).toBe(
      false,
    );
  });
});
