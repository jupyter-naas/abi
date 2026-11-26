import { describe, expect, it } from 'vitest';
import { isOrgTarget, orgTarget, targetApiPath } from './target';

describe('the target of Access › Features, Services and Modules', () => {
  it('is a workspace by its id, or an organization (org:<id>), each answered at its own API', () => {
    expect(targetApiPath('ws-1')).toBe('/api/workspaces/ws-1');
    expect(orgTarget('acme')).toBe('org:acme');
    expect(isOrgTarget(orgTarget('acme'))).toBe(true);
    expect(isOrgTarget('ws-1')).toBe(false);
    expect(targetApiPath(orgTarget('acme'))).toBe('/api/organizations/acme');
  });
});
