import { describe, expect, it } from 'vitest';
import {
  WORKSPACE_ACCESS_ONLY,
  orgUserRoleLabel,
  orgUserRoleRank,
  organizationRemoval,
  removableFromOrganization,
  removalConfirmation,
} from './users-model';

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

describe('Remove from organization', () => {
  it('applies to members and to people with workspace access only, never an owner nor oneself', () => {
    expect(removableFromOrganization('member', 'u-1', 'me')).toBe(true);
    expect(removableFromOrganization('admin', 'u-1', 'me')).toBe(true);
    expect(removableFromOrganization(null, 'u-1', 'me')).toBe(true);
    expect(removableFromOrganization('owner', 'u-1', 'me')).toBe(false);
    expect(removableFromOrganization('member', 'me', 'me')).toBe(false);
    expect(removableFromOrganization(null, 'me', 'me')).toBe(false);
  });

  it('takes all of the access of someone with workspace access only, the org role of a member', () => {
    expect(organizationRemoval(null)).toBe('all-access');
    expect(organizationRemoval('member')).toBe('org-role');
    expect(organizationRemoval('admin')).toBe('org-role');
  });

  it('says what is taken and that the account stays', () => {
    const all = removalConfirmation('Flo', null, ['Sales', 'Ops']);
    expect(all.title).toBe('Remove Flo from the organization?');
    expect(all.description).toContain('every workspace of this organization (Sales, Ops)');
    expect(all.description).toContain('account stays');
    const role = removalConfirmation('Bob', 'member', ['Sales']);
    expect(role.description).toContain('workspace access stays (Sales)');
  });
});
