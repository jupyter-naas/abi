import { describe, expect, it } from 'vitest';
import {
  addable,
  createMemberRolesApi,
  defaultRole,
  heldItems,
  readRoleOptions,
  roleProblem,
  withRole,
  withRoles,
  withoutRole,
} from './member-roles';

const OPTIONS = readRoleOptions({
  groups: [
    { kind: 'level', id: 'grp_m', name: 'Members', level: 'member' },
    { kind: 'level', id: 'grp_v', name: 'Viewers', level: 'viewer' },
    { kind: 'own', id: 'grp_w', name: 'ABI workspace' },
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

describe('a person’s page', () => {
  it('lists what they hold in order, named, one not offered as IAM names it', () => {
    const items = heldItems(OPTIONS, {
      groups: ['grp_r', 'grp_x', 'grp_m', 'grp_w'],
      policies: ['pol_a', 'pol_z'],
      names: { grp_x: 'Auditors' },
    });
    expect(items.groups.map((g) => [g.kind, g.name])).toEqual([
      ['own', 'ABI workspace'],
      ['level', 'Members'],
      ['group', 'Auditors'],
      ['group', 'Workflow runners'],
    ]);
    expect(items.policies.map((p) => p.name)).toEqual(['Alpha reports', 'pol_z']);
  });

  it('shows what their Role shows, an organization admin’s groups managed elsewhere kept', () => {
    const items = heldItems(OPTIONS, {
      groups: ['grp_m'],
      policies: [],
      names: {},
      shown: [
        { id: 'grp_w', name: 'ABI workspace', implied: true, managed: 'admins' },
        { id: 'grp_oa', name: 'Acme admins', implied: false, managed: 'organization' },
      ],
    });
    expect(items.groups.map((g) => [g.kind, g.name, g.managed])).toEqual([
      ['own', 'ABI workspace', 'admins'],
      ['group', 'Acme admins', 'organization'],
      ['level', 'Members', undefined],
    ]);
  });

  it('adds several at once, the last level picked replacing theirs', () => {
    const role = withRoles(OPTIONS, { groups: ['grp_w', 'grp_m'], policies: [] }, [byId('grp_r'), byId('grp_v'), byId('pol_a')]);
    expect(role).toEqual({ groups: ['grp_w', 'grp_r', 'grp_v'], policies: ['pol_a'] });
  });

  it('reads which workspace an organization’s workspace group places someone in', () => {
    const options = readRoleOptions({
      groups: [
        { kind: 'group', id: 'grp_sales', name: 'Sales workspace', workspace: 'ws-sales' },
        { kind: 'group', id: 'grp_sales_a', name: 'Sales admins', workspace: 'ws-sales', administers: true },
        { kind: 'group', id: 'grp_r', name: 'Workflow runners' },
      ],
    });
    expect(options.groups.map((g) => [g.id, g.workspace ?? null, g.administers ?? null])).toEqual([
      ['grp_sales', 'ws-sales', false],
      ['grp_sales_a', 'ws-sales', true],
      ['grp_r', null, null],
    ]);
  });

  it('reads the names IAM gives with what they hold', async () => {
    const api = createMemberRolesApi(async () =>
      new Response(
        JSON.stringify({
          groups: ['grp_m'],
          policies: [],
          names: { grp_m: 'Members', bad: 3 },
          shown: [{ id: 'grp_pa', name: 'Platform admins', managed: 'platform' }, { id: 'grp_m', name: 'Members', managed: 'nope' }, { name: 'x' }],
        }),
        { status: 200 }
      )
    );
    expect(await api.held({ kind: 'platform' }, 'usr_a')).toEqual({
      groups: ['grp_m'],
      policies: [],
      names: { grp_m: 'Members' },
      shown: [
        { id: 'grp_pa', name: 'Platform admins', implied: false, managed: 'platform' },
        { id: 'grp_m', name: 'Members', implied: false, managed: null },
      ],
    });
  });
});
