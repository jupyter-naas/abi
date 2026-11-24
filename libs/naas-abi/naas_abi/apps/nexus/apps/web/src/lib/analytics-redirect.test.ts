import { describe, expect, it } from 'vitest';
import { organizationAnalyticsPath } from './analytics-redirect';

const workspaces = [
  { id: 'ws-1', organizationId: 'org-1' },
  { id: 'ws-2', organizationId: 'org-2' },
  { id: 'ws-3' },
];

describe('organizationAnalyticsPath', () => {
  it("leads to the current workspace's organization's Analytics section", () => {
    expect(organizationAnalyticsPath(workspaces, 'ws-2')).toBe(
      '/organizations/org-2/settings/analytics',
    );
  });

  it('is nothing for a current workspace with no organization', () => {
    expect(organizationAnalyticsPath(workspaces, 'ws-3')).toBeNull();
  });

  it("with no current workspace, takes the one organization of the user's workspaces", () => {
    const oneOrg = [
      { id: 'a', organizationId: 'org-1' },
      { id: 'b', organizationId: 'org-1' },
    ];
    expect(organizationAnalyticsPath(oneOrg, null)).toBe('/organizations/org-1/settings/analytics');
    expect(organizationAnalyticsPath(workspaces, null)).toBeNull();
    expect(organizationAnalyticsPath([], undefined)).toBeNull();
  });

  it('treats a current workspace it no longer knows as none', () => {
    expect(organizationAnalyticsPath([{ id: 'a', organizationId: 'org-1' }], 'ws-gone')).toBe(
      '/organizations/org-1/settings/analytics',
    );
    expect(organizationAnalyticsPath(workspaces, 'ws-gone')).toBeNull();
  });

  it('encodes the organization id', () => {
    expect(organizationAnalyticsPath([{ id: 'a', organizationId: 'org/1' }], 'a')).toBe(
      '/organizations/org%2F1/settings/analytics',
    );
  });
});
