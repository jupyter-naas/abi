import { describe, expect, it, vi } from 'vitest';
import { createAccessDirectory, toMembers } from '../access-directory';
import { PLATFORM_ACCESS_SCOPE, organizationAccessScope, ownedHere, workspaceAccessScope } from '../access-scope';
import { assignableRoles, changeMemberRole, isRoleCompanion, roleChangeable, roleOfPolicy } from './role-change';

const ok = (body: unknown) => ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as Response;

describe('changeMemberRole', () => {
  it('changes a role through the membership route of its level', async () => {
    const fetcher = vi.fn().mockResolvedValue(ok({}));
    await changeMemberRole({ level: 'workspace', workspaceId: 'ws 1' }, 'usr_bob', 'admin', fetcher);
    await changeMemberRole({ level: 'organization', organizationId: 'acme' }, 'usr_bob', 'member', fetcher);
    expect(fetcher.mock.calls.map(([url, init]) => [url, init.method, init.body])).toEqual([
      ['/api/workspaces/ws%201/members/usr_bob', 'PATCH', '{"role":"admin"}'],
      ['/api/organizations/acme/members/usr_bob', 'PATCH', '{"role":"member"}'],
    ]);
  });

  it('says what IAM refused', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 403, json: () => Promise.resolve({ detail: 'Only owners may do this' }) });
    await expect(changeMemberRole({ level: 'workspace', workspaceId: 'w' }, 'u', 'admin', fetcher)).rejects.toThrow('Only owners may do this');
  });
});

describe('roles', () => {
  it('gives only roles below owner, and an organization no viewer', () => {
    expect(assignableRoles('workspace')).toEqual(['member', 'viewer', 'admin']);
    expect(assignableRoles('organization')).toEqual(['member', 'admin']);
    expect(assignableRoles('platform')).toEqual([]);
  });

  it('never changes an owner’s, an inherited or one’s own role', () => {
    const base = { role: 'member' as const, inherited: false, userId: 'u', selfId: 'me' };
    expect(roleChangeable(base)).toBe(true);
    expect(roleChangeable({ ...base, role: 'owner' })).toBe(false);
    expect(roleChangeable({ ...base, inherited: true })).toBe(false);
    expect(roleChangeable({ ...base, selfId: 'u' })).toBe(false);
  });

  it('knows a role’s policy', () => {
    expect(roleOfPolicy('builtin.viewer')).toBe('viewer');
    expect(roleOfPolicy('builtin.platform_admin')).toBeNull();
    expect(roleOfPolicy('pol_1')).toBeNull();
  });

  it('keeps the platform companions with a role', () => {
    expect(isRoleCompanion('builtin.platform.member')).toBe(true);
    expect(isRoleCompanion('builtin.platform.viewer')).toBe(true);
    expect(isRoleCompanion('builtin.member')).toBe(false);
  });
});

describe('the scope', () => {
  it('names the level the API answers for, and what it owns', () => {
    expect(PLATFORM_ACCESS_SCOPE.value).toBeNull();
    expect(organizationAccessScope('acme').value).toBe('abi:acme:-');
    expect(workspaceAccessScope('acme', 'ws-1').value).toBe('abi:acme:ws-1');
    expect(ownedHere(PLATFORM_ACCESS_SCOPE, undefined)).toBe(true);
    expect(ownedHere(organizationAccessScope('acme'), 'abi:acme:-')).toBe(true);
    expect(ownedHere(workspaceAccessScope('acme', 'ws-1'), 'abi:acme:-')).toBe(false);
  });
});

describe('the directory', () => {
  it('reads a workspace’s and an organization’s members, nobody at the platform', async () => {
    const fetcher = vi.fn().mockResolvedValue(ok([{ user_id: 'u1', name: 'Ann', email: 'a@x', role: 'admin', source: 'organization' }]));
    const directory = createAccessDirectory(fetcher);
    expect(await directory.members(workspaceAccessScope('acme', 'ws-1'))).toEqual([
      { userId: 'u1', name: 'Ann', email: 'a@x', role: 'admin', inherited: true },
    ]);
    await directory.members(organizationAccessScope('acme'));
    expect(await directory.members(PLATFORM_ACCESS_SCOPE)).toEqual([]);
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/workspaces/ws-1/members', '/api/organizations/acme/members']);
    expect(toMembers([{ name: 'no id' }, { user_id: 'u2', role: 'nope' }])).toEqual([
      { userId: 'u2', name: '', email: '', role: null, inherited: false },
    ]);
  });
});
