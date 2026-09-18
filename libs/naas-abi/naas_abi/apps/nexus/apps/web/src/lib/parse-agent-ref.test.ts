import { describe, expect, it } from 'vitest';

import { parseAgentRef, pickAgentByRef } from './parse-agent-ref';

describe('parseAgentRef', () => {
  it('splits module and class', () => {
    expect(parseAgentRef('operations.counter_uas CounterUASAgent')).toEqual({
      moduleName: 'operations.counter_uas',
      className: 'CounterUASAgent',
    });
  });

  it('rejects bare class names', () => {
    expect(parseAgentRef('CounterUASAgent')).toBeNull();
  });
});

describe('pickAgentByRef', () => {
  const roster = [
    {
      id: 'apps',
      enabled: true,
      class_name: 'naas_abi.agents.AppsAgent/AppsAgent',
    },
    {
      id: 'cuas',
      enabled: true,
      class_name: 'operations.counter_uas.agents.CounterUASAgent/CounterUASAgent',
    },
  ];

  it('prefers module prefix match', () => {
    expect(
      pickAgentByRef(roster, 'operations.counter_uas CounterUASAgent')?.id,
    ).toBe('cuas');
  });

  it('falls back to Apps agent when ref is missing from roster', () => {
    expect(pickAgentByRef(roster, 'missing MissingAgent')).toBeUndefined();
  });
});
