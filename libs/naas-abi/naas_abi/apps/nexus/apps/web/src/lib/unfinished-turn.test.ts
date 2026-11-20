import { describe, expect, it, vi } from 'vitest';

import { endsOnUnfinishedTurn, stopTurn } from './unfinished-turn';

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

  it('is false for a stopped reply, even one stopped before its first word', () => {
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: '', stopped: true }])).toBe(
      false,
    );
  });

  it('is false for structured content', () => {
    expect(endsOnUnfinishedTurn([ask, { role: 'assistant', content: [{ type: 'image' }] }])).toBe(
      false,
    );
  });
});

describe('stopTurn', () => {
  it('asks the server to stop the turn of the conversation', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true });

    expect(await stopTurn('conv-1a2b', fetcher)).toBe(true);
    expect(fetcher).toHaveBeenCalledWith('/api/chat/conversations/conv-1a2b/stop', {
      method: 'POST',
    });
  });

  it('is false when the server refuses or cannot be reached', async () => {
    expect(await stopTurn('conv-1', vi.fn().mockResolvedValue({ ok: false }))).toBe(false);
    expect(await stopTurn('conv-1', vi.fn().mockRejectedValue(new TypeError('offline')))).toBe(
      false,
    );
  });
});
