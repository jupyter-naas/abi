import { describe, expect, it } from 'vitest';

import { displayOrgDomain } from './domain';

describe('displayOrgDomain', () => {
  it('prefers a verified domain over unverified ones', () => {
    expect(
      displayOrgDomain(
        [
          { domain: 'draft.example', is_verified: false },
          { domain: 'nexus.localhost', is_verified: true },
        ],
        'fallback.host'
      )
    ).toBe('nexus.localhost');
  });

  it('falls back to the first stored domain when none are verified', () => {
    expect(
      displayOrgDomain([{ domain: 'acme.example', is_verified: false }], 'fallback.host')
    ).toBe('acme.example');
  });

  it('falls back to the current host when no domain is stored', () => {
    expect(displayOrgDomain([], 'nexus.localhost')).toBe('nexus.localhost');
    expect(displayOrgDomain(undefined, 'nexus.localhost')).toBe('nexus.localhost');
  });
});
