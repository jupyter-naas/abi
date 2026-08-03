import { describe, expect, it } from 'vitest';
import { modelOptionHints, parseModelLabel } from './chat-agent-selector-utils';

describe('parseModelLabel', () => {
  it('splits title and badges from model names', () => {
    expect(parseModelLabel('Opus 5 High Fast')).toEqual({
      title: 'Opus 5',
      badges: ['High Fast'],
    });
  });

  it('handles names without badges', () => {
    expect(parseModelLabel('Composer 2.5')).toEqual({
      title: 'Composer 2.5',
      badges: [],
    });
  });
});

describe('modelOptionHints', () => {
  it('infers thinking and effort from model metadata', () => {
    const hints = modelOptionHints('claude-opus-5-high', 'Opus 5 High');
    expect(hints.thinking).toBe(true);
    expect(hints.effort).toBe('High');
  });
});
