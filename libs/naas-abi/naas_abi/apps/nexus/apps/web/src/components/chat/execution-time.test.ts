import { describe, expect, it } from 'vitest';
import { elapsedSecondsSince } from './execution-time';

describe('elapsedSecondsSince', () => {
  it('measures from the send time of the current turn', () => {
    expect(elapsedSecondsSince(1_000_000, 1_009_250)).toBe(9.25);
  });

  it('is undefined without a send time or with a clock running backwards', () => {
    expect(elapsedSecondsSince(null, 1_000)).toBeUndefined();
    expect(elapsedSecondsSince(undefined, 1_000)).toBeUndefined();
    expect(elapsedSecondsSince(2_000, 1_000)).toBeUndefined();
  });
});
