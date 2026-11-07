import { describe, expect, it } from 'vitest';
import { managedPolicy, readerPolicy } from '../access-fixtures';
import { policyTree } from './policy-tree';

const policy = (id: string, name: string, parent: string | null = null) => ({ ...readerPolicy, id, name, parent_id: parent });

describe('policyTree', () => {
  it('puts each sub-policy below its parent, the roles first and the rest by name', () => {
    const rows = policyTree([
      policy('pol_w', 'W analysts', 'pol_o'),
      policy('pol_x', 'Auditors'),
      policy('pol_o', 'O access'),
      policy('pol_b', 'Bob only', 'pol_w'),
      policy('pol_a', 'A team', 'pol_o'),
      managedPolicy,
    ]);
    expect(rows.map((r) => [r.policy.name, r.depth])).toEqual([
      ['Viewer', 0],
      ['Auditors', 0],
      ['O access', 0],
      ['A team', 1],
      ['W analysts', 1],
      ['Bob only', 2],
    ]);
  });

  it('keeps at the top a sub-policy whose parent is not listed', () => {
    expect(policyTree([policy('pol_w', 'W analysts', 'pol_hidden')]).map((r) => r.depth)).toEqual([0]);
  });
});
