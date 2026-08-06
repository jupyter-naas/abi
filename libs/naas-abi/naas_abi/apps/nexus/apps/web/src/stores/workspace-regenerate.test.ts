import { describe, expect, it } from 'vitest';

import { getModelHistory, type Message } from './workspace';

/**
 * Regression guard for the chat "refresh" (regenerate) feature, which was
 * silently deleted from the frontend by an unrelated refactor while the whole
 * backend half stayed in place.
 *
 * Every message below is *rendered* in the thread — getModelHistory only decides
 * what the model is given on later turns. A refresh must not hand the model the
 * answer it is re-running, or it repeats it instead of redoing the work.
 */

const message = (overrides: Partial<Message> & Pick<Message, 'id' | 'role'>): Message => ({
  content: '',
  timestamp: new Date('2026-08-06T19:48:31Z'),
  ...overrides,
});

describe('getModelHistory', () => {
  it('passes an ordinary transcript through untouched', () => {
    const messages = [
      message({ id: 'u1', role: 'user', content: 'How many tweets in the last 24h?' }),
      message({ id: 'a1', role: 'assistant', content: '19 019 tweets.' }),
    ];
    expect(getModelHistory(messages).map((m) => m.id)).toEqual(['u1', 'a1']);
  });

  it('drops the replayed prompt and the answer a completed refresh replaced', () => {
    const messages = [
      message({ id: 'u1', role: 'user', content: 'How many tweets in the last 24h?' }),
      message({ id: 'a1', role: 'assistant', content: '19 019 tweets.' }),
      message({
        id: 'u2',
        role: 'user',
        content: 'How many tweets in the last 24h?',
        replayedPrompt: true,
        regenerateOf: 'a1',
      }),
      message({
        id: 'a2',
        role: 'assistant',
        content: '19 214 tweets.',
        regenerateOf: 'a1',
      }),
    ];

    // The superseded answer and the duplicate question leave the model's
    // context; both stay in `messages` for display, storage and export.
    expect(getModelHistory(messages).map((m) => m.id)).toEqual(['u1', 'a2']);
    expect(messages).toHaveLength(4);
  });

  it('keeps the original answer while the refresh is still empty', () => {
    const messages = [
      message({ id: 'u1', role: 'user', content: 'How many tweets?' }),
      message({ id: 'a1', role: 'assistant', content: '19 019 tweets.' }),
      message({
        id: 'u2',
        role: 'user',
        content: 'How many tweets?',
        replayedPrompt: true,
        regenerateOf: 'a1',
      }),
      message({ id: 'a2', role: 'assistant', content: '▌', regenerateOf: 'a1' }),
    ];
    expect(getModelHistory(messages).map((m) => m.id)).toEqual(['u1', 'a1', 'a2']);
  });

  it('keeps the original answer when the refresh failed', () => {
    const messages = [
      message({ id: 'u1', role: 'user', content: 'How many tweets?' }),
      message({ id: 'a1', role: 'assistant', content: '19 019 tweets.' }),
      message({
        id: 'a2',
        role: 'assistant',
        content: '❌ Error: provider timed out',
        regenerateOf: 'a1',
      }),
    ];
    expect(getModelHistory(messages).map((m) => m.id)).toEqual(['u1', 'a1', 'a2']);
  });

  it('drops answers the server marked superseded, so a reload agrees with the live thread', () => {
    const messages = [
      message({ id: 'u1', role: 'user', content: 'How many tweets?' }),
      message({ id: 'a1', role: 'assistant', content: '19 019 tweets.', supersededBy: 'a2' }),
      message({
        id: 'u2',
        role: 'user',
        content: 'How many tweets?',
        replayedPrompt: true,
        regenerateOf: 'a1',
      }),
      message({ id: 'a2', role: 'assistant', content: '19 214 tweets.', regenerateOf: 'a1' }),
    ];
    expect(getModelHistory(messages).map((m) => m.id)).toEqual(['u1', 'a2']);
  });

  it('handles a chain of refreshes, keeping only the newest answer', () => {
    const messages = [
      message({ id: 'u1', role: 'user', content: 'How many tweets?' }),
      message({ id: 'a1', role: 'assistant', content: 'first' }),
      message({ id: 'u2', role: 'user', content: 'How many tweets?', replayedPrompt: true }),
      message({ id: 'a2', role: 'assistant', content: 'second', regenerateOf: 'a1' }),
      message({ id: 'u3', role: 'user', content: 'How many tweets?', replayedPrompt: true }),
      message({ id: 'a3', role: 'assistant', content: 'third', regenerateOf: 'a2' }),
    ];
    expect(getModelHistory(messages).map((m) => m.id)).toEqual(['u1', 'a3']);
  });
});
