import { describe, expect, it } from 'vitest';
import { updateMessageInList } from './message-target';

const thread = [
  { id: 'u1', content: 'first question' },
  { id: 'a1', content: 'first answer' },
  { id: 'u2', content: 'second question' },
  { id: 'a2', content: '▌' },
];
const setTo = (content: string) => (m: { id: string; content: string }) => ({ ...m, content });

describe('updateMessageInList', () => {
  it('writes into the targeted bubble, not the newest one', () => {
    const next = updateMessageInList(thread, 'a1', setTo('first answer … [interrupted]'));
    expect(next.map((m) => m.content)).toEqual([
      'first question',
      'first answer … [interrupted]',
      'second question',
      '▌',
    ]);
  });

  it('falls back to the last message only when no id is known', () => {
    expect(updateMessageInList(thread, null, setTo('hi'))[3].content).toBe('hi');
  });

  it('leaves the thread alone when the target is gone', () => {
    expect(updateMessageInList(thread, 'removed', setTo('x'))).toBe(thread);
  });
});
