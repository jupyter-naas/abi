import { describe, expect, it } from 'vitest';
import { ORG, WS } from '../access-fixtures';
import { ownedBy, ownerHref, ownerLabel } from './policy-owners';

describe('policy owners', () => {
  it('names an owner by its containers, what it sits in between parentheses', () => {
    expect(ownerLabel('abi:')).toBe('Platform');
    expect(ownerLabel(null)).toBe('Platform');
    expect(ownerLabel(ORG)).toBe('Organization acme');
    expect(ownerLabel(WS)).toBe('Workspace ws-1 (acme)');
    expect(ownerLabel(WS, { [WS]: 'Alpha', [ORG]: 'Acme' })).toBe('Workspace Alpha (Acme)');
    expect(ownerLabel(`${WS}/crm:project/p1`, { [WS]: 'Alpha' })).toBe('Project p1 (Alpha, acme)');
    expect(ownedBy('Workspace Alpha (Acme)')).toBe('Owned by workspace Alpha (Acme)');
    expect(ownedBy('Platform')).toBe('Owned by the platform');
  });

  it('links to the owner’s Roles & permissions, on its Policies at the policy', () => {
    expect(ownerHref('abi:', 'pol_1')).toBe('/settings/roles?section=policies&policy=pol_1');
    expect(ownerHref(ORG, 'pol_1')).toBe('/organizations/acme/settings/roles?section=policies&policy=pol_1');
    expect(ownerHref(WS, 'pol_1')).toBe('/workspace/ws-1/settings/permissions?section=policies&policy=pol_1');
    expect(ownerHref('abi:nexus:workspace/solo')).toBe('/workspace/solo/settings/permissions?section=policies');
    // A container another module declares has no settings page.
    expect(ownerHref(`${WS}/crm:project/p1`, 'pol_1')).toBeNull();
  });
});
