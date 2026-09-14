import { describe, expect, it } from 'vitest';

import { createHealthCheckGate } from './api-health-check';

describe('createHealthCheckGate', () => {
  it('ignores a stale timeout after a newer check succeeded', () => {
    const gate = createHealthCheckGate();
    const first = gate.begin();
    const second = gate.begin();
    expect(gate.isCurrent(second)).toBe(true);
    expect(gate.isCurrent(first)).toBe(false);
  });
});
