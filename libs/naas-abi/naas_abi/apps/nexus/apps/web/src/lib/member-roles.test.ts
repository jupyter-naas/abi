import { describe, expect, it } from 'vitest';
import { addable, defaultRole, readRoleOptions, roleProblem, withRole, withoutRole } from './member-roles';

const OPTIONS = readRoleOptions({
  groups: [
    { kind: 'level', id: 'grp_m', name: 'Members', level: 'member' },
    { kind: 'level', id: 'grp_v', name: 'Viewers', level: 'viewer' },
    { kind: 'workspace', id: 'grp_w', name: 'ABI workspace' },
    { kind: 'admins', id: 'grp_wa', name: 'ABI admins' },
    { kind: 'group', id: 'grp_r', name: 'Workflow runners' },
    { id: '' },
  ],
  policies: [{ kind: 'policy', id: 'pol_a', name: 'Alpha reports' }],
});
const byId = (id: string) => [...OPTIONS.groups, ...OPTIONS.policies].find((o) => o.id === id)!;

describe('the Role editor', () => {
  it('reads the options, and starts someone created in a workspace as a Member of it', () => {
    expect(OPTIONS.groups.map((g) => g.id)).toEqual(['grp_m', 'grp_v', 'grp_w', 'grp_wa', 'grp_r']);
    expect(defaultRole(OPTIONS)).toEqual({ groups: ['grp_w', 'grp_m'], policies: [] });
  });

  it('adds groups and policies, one level at a time, and offers only what is not there', () => {
    let role = defaultRole(OPTIONS);
    role = withRole(OPTIONS, role, byId('grp_v'));
    expect(role.groups).toEqual(['grp_w', 'grp_v']);
    role = withRole(OPTIONS, withRole(OPTIONS, role, byId('grp_r')), byId('pol_a'));
    expect(role).toEqual({ groups: ['grp_w', 'grp_v', 'grp_r'], policies: ['pol_a'] });
    expect(addable(OPTIONS, role).map((o) => o.id)).toEqual(['grp_m', 'grp_wa']);
  });

  it('removes anything but the workspace group', () => {
    const role = withRole(OPTIONS, defaultRole(OPTIONS), byId('pol_a'));
    expect(withoutRole(role, byId('grp_w'))).toEqual(role);
    expect(withoutRole(role, byId('grp_m')).groups).toEqual(['grp_w']);
    expect(withoutRole(role, byId('pol_a')).policies).toEqual([]);
  });

  it('says what the API would refuse', () => {
    expect(roleProblem(OPTIONS, defaultRole(OPTIONS))).toBeNull();
    expect(roleProblem(OPTIONS, { groups: ['grp_w'], policies: [] })).toMatch(/use nothing/);
    expect(roleProblem(OPTIONS, { groups: ['grp_w'], policies: [] }, true)).toBeNull();
    expect(roleProblem(OPTIONS, { groups: ['grp_w'], policies: ['pol_a'] })).toBeNull();
    expect(roleProblem(OPTIONS, { groups: ['grp_w', 'grp_v', 'grp_wa'], policies: [] })).toMatch(/Member/);
    expect(roleProblem(OPTIONS, { groups: ['grp_m', 'grp_v'], policies: [] })).toMatch(/one level/);
  });
});
