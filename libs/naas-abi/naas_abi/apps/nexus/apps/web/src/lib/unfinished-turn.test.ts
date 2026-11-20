import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  endsOnUnfinishedTurn,
  serverReplyContent,
  stopTurn,
  UNFINISHED_TURN_POLL_MS,
  UNFINISHED_TURN_POLLS,
  watchUnfinishedTurn,
} from './unfinished-turn';

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

describe('serverReplyContent', () => {
  it('ends a reply the server is still writing on the caret, so the thread shows it streaming', () => {
    expect(serverReplyContent('Here are the first', 'streaming')).toBe('Here are the first▌');
    expect(serverReplyContent('', 'streaming')).toBe('▌');
    expect(
      endsOnUnfinishedTurn([ask, { role: 'assistant', content: serverReplyContent('Here', 'streaming') }]),
    ).toBe(true);
  });

  it('leaves a finished, stopped or older reply as it is', () => {
    expect(serverReplyContent('Nine folders.', 'done')).toBe('Nine folders.');
    expect(serverReplyContent('Nine', 'stopped')).toBe('Nine');
    expect(serverReplyContent('Nine folders.', undefined)).toBe('Nine folders.');
  });
});

describe('watchUnfinishedTurn', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('gives up after its asks bring nothing new', () => {
    const load = vi.fn();
    watchUnfinishedTurn(load, () => 'Here are▌');

    vi.advanceTimersByTime(UNFINISHED_TURN_POLL_MS * (UNFINISHED_TURN_POLLS + 10));

    expect(load).toHaveBeenCalledTimes(UNFINISHED_TURN_POLLS);
  });

  it('keeps asking while the server copy grows', () => {
    const load = vi.fn();
    let written = '';
    watchUnfinishedTurn(load, () => written);

    for (let tick = 0; tick < UNFINISHED_TURN_POLLS * 2; tick += 1) {
      written += 'word ';
      vi.advanceTimersByTime(UNFINISHED_TURN_POLL_MS);
    }

    expect(load).toHaveBeenCalledTimes(UNFINISHED_TURN_POLLS * 2 + 1);
  });

  it('stops asking once the thread is done with it', () => {
    const load = vi.fn();
    const stop = watchUnfinishedTurn(load, () => 'Here are▌');

    stop();
    vi.advanceTimersByTime(UNFINISHED_TURN_POLL_MS * 5);

    expect(load).toHaveBeenCalledTimes(1);
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
