import { describe, expect, it } from 'vitest';

import { pendingDomainCount, verifiedDomains } from './domain';

describe('verifiedDomains', () => {
  it('lists the verified domains only, sorted, once each', () => {
    expect(
      verifiedDomains([
        { domain: 'draft.example', is_verified: false },
        { domain: 'Acme.example ', is_verified: true },
        { domain: 'acme.fr', is_verified: true },
        { domain: 'acme.example', is_verified: true },
      ])
    ).toEqual(['acme.example', 'acme.fr']);
  });

  it('is empty without domains, and never falls back to the current host', () => {
    expect(verifiedDomains([])).toEqual([]);
    expect(verifiedDomains(undefined)).toEqual([]);
    expect(verifiedDomains([{ domain: 'draft.example' }])).toEqual([]);
  });
});

describe('pendingDomainCount', () => {
  it('counts the domains not verified yet', () => {
    expect(
      pendingDomainCount([
        { domain: 'draft.example', is_verified: false },
        { domain: 'acme.example', is_verified: true },
        { domain: '  ' },
      ])
    ).toBe(1);
  });
});
