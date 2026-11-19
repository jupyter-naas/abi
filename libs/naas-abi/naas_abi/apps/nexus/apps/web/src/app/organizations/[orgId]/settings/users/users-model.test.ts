import { describe, expect, it } from 'vitest';
import { WORKSPACE_ACCESS_ONLY, orgUserRoleLabel, orgUserRoleRank } from './users-model';

describe('the role column of Organization settings › Users', () => {
  it('names the org role, else "Workspace access only"', () => {
    expect(orgUserRoleLabel({ role: 'admin' })).toBe('Admin');
    expect(orgUserRoleLabel({ role: null })).toBe(WORKSPACE_ACCESS_ONLY);
  });

  it('sorts owners first and workspace access only last', () => {
    const roles = [null, 'member', 'owner', 'admin'] as const;
    expect([...roles].sort((a, b) => orgUserRoleRank({ role: a }) - orgUserRoleRank({ role: b }))).toEqual([
      'owner',
      'admin',
      'member',
      null,
    ]);
  });
});
