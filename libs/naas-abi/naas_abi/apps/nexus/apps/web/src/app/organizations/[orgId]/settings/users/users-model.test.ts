import { describe, expect, it } from 'vitest';
import {
  WORKSPACE_ACCESS_ONLY,
  orgUserRoleLabel,
  orgUserRoleRank,
  removableFromOrganization,
  removalConfirmation,
  workspacesBody,
} from './users-model';

const user = (over: Partial<{ role: 'admin' | 'member' | 'viewer' | null; orgAdmin: boolean; level: 'member' | 'viewer' | null }>) => ({
  role: null,
  orgAdmin: false,
  level: null,
  ...over,
});

describe('the access column of Organization settings › Users', () => {
  it('names an org admin, else the level, else workspace access only', () => {
    expect(orgUserRoleLabel(user({ role: 'admin', orgAdmin: true, level: 'member' }))).toBe('Org admin');
    expect(orgUserRoleLabel(user({ role: 'member', level: 'member' }))).toBe('Member');
    expect(orgUserRoleLabel(user({ role: null, level: 'viewer' }))).toBe('Viewer');
    expect(orgUserRoleLabel(user({ role: 'viewer' }))).toBe('Viewer');
    expect(orgUserRoleLabel(user({ role: null }))).toBe(WORKSPACE_ACCESS_ONLY);
  });

  it('sorts org admins first, then Members, Viewers, and workspace access only', () => {
    const users = [user({}), user({ level: 'viewer' }), user({ orgAdmin: true, role: 'admin' }), user({ level: 'member' })];
    expect(
      [...users].sort((a, b) => orgUserRoleRank(a) - orgUserRoleRank(b)).map((u) => orgUserRoleLabel(u))
    ).toEqual(['Org admin', 'Member', 'Viewer', WORKSPACE_ACCESS_ONLY]);
  });
});

describe('Remove from organization', () => {
  it('applies to anyone but oneself: the API keeps the last org admin', () => {
    expect(removableFromOrganization('u-1', 'me')).toBe(true);
    expect(removableFromOrganization('me', 'me')).toBe(false);
  });

  it('says that every group of the organization is left, and that the account and level stay', () => {
    const all = removalConfirmation('Flo', ['Sales', 'Ops']);
    expect(all.title).toBe('Remove Flo from the organization?');
    expect(all.description).toContain('every workspace of this organization (Sales, Ops)');
    expect(all.description).toContain('org admin');
    expect(all.description).toContain('account and level stay');
  });
});

describe('the workspaces of a member', () => {
  it('are sent with "admin" kept for those they administer', () => {
    expect(
      workspacesBody(['ws-1', 'ws-2'], [
        { user_id: 'u', workspace_id: 'ws-1', role: 'admin' },
        { user_id: 'u', workspace_id: 'ws-3', role: 'member' },
        { user_id: 'v', workspace_id: 'ws-2', role: 'admin' },
      ], 'u')
    ).toEqual({ workspaces: [{ id: 'ws-1', admin: true }, { id: 'ws-2', admin: false }] });
  });
});
