import { describe, expect, it } from 'vitest';

import { parseAccountRoute } from './account-route';

describe('parseAccountRoute', () => {
  it('shows the settings list on the bare account route', () => {
    expect(parseAccountRoute('/account')).toEqual({
      isAccountRoute: true,
      isDetail: false,
      section: null,
      sectionLabel: null,
    });
  });

  it('opens a detail section for a settings slug', () => {
    expect(parseAccountRoute('/account/profile')).toEqual({
      isAccountRoute: true,
      isDetail: true,
      section: 'profile',
      sectionLabel: 'Profile',
    });
  });

  it('ignores a trailing slash on the index', () => {
    expect(parseAccountRoute('/account/')).toEqual({
      isAccountRoute: true,
      isDetail: false,
      section: null,
      sectionLabel: null,
    });
  });

  it('stops at a query string or fragment', () => {
    expect(parseAccountRoute('/account/security?tab=2fa').section).toBe('security');
    expect(parseAccountRoute('/account/api-keys#revoke').sectionLabel).toBe('API Keys');
  });

  it('does not claim routes that merely start with account', () => {
    expect(parseAccountRoute('/accounting').isAccountRoute).toBe(false);
  });

  it('treats a missing pathname as no route at all', () => {
    expect(parseAccountRoute(null).isAccountRoute).toBe(false);
    expect(parseAccountRoute(undefined).isAccountRoute).toBe(false);
  });
});
