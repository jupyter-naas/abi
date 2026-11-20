import { describe, expect, it } from 'vitest';
import {
  CAPABILITY_GROUPS,
  LEVEL_POLICIES,
  groupKind,
  groupRank,
  levelPolicyOf,
  levelSummary,
  orgAdminsGroupName,
  orgPeopleGroupName,
  workspaceAdminsGroupName,
  workspaceGroupName,
} from './levels';

const W = 'abi:nexus:organization/acme/nexus:workspace/ws-1';
const O = 'abi:nexus:organization/acme';
const group = (name: string, over: Record<string, unknown> = {}) => ({ name, owner_scope: 'abi:', ...over });

describe('the names of the access model (S2, #1585)', () => {
  it('names the groups made with each container', () => {
    expect(workspaceGroupName('Sales')).toBe('Sales workspace');
    expect(workspaceAdminsGroupName('Sales')).toBe('Sales admins');
    expect(orgAdminsGroupName('Acme')).toBe('Acme admins');
    expect(orgPeopleGroupName('Acme')).toBe('Acme people');
  });

  it('has three generic level policies, written once', () => {
    expect(LEVEL_POLICIES.map((p) => p.name)).toEqual(['Viewer access', 'Member access', 'Workspace admin access']);
    expect(levelPolicyOf({ name: 'Member access' })?.level).toBe('member');
    expect(levelPolicyOf({ name: 'Sales access' })).toBeNull();
  });

  it('says in plain words what each level policy grants', () => {
    expect(levelSummary('viewer')).toMatch(/read/i);
    expect(levelSummary('viewer')).toMatch(/no model/i);
    expect(levelSummary('member')).toMatch(/chat/);
    expect(levelSummary('member')).toMatch(/member model set/);
    expect(levelSummary('admin')).toMatch(/every model/i);
  });

  it('lists the two capability groups', () => {
    expect(CAPABILITY_GROUPS.map((c) => c.name)).toEqual(['Workflow runners', 'Models · all']);
  });
});

describe('what a group is', () => {
  it('reads the markers first', () => {
    expect(groupKind(group('Anything', { level_group: true }))).toBe('level');
    expect(groupKind(group('Anything', { membership_of: W, owner_scope: W }))).toBe('workspace');
    expect(groupKind(group('Anything', { membership_of: O, owner_scope: O }))).toBe('people');
  });

  it('else its name and owner', () => {
    expect(groupKind(group('Members'))).toBe('level');
    expect(groupKind(group('Viewers'))).toBe('level');
    expect(groupKind(group('Sales workspace', { owner_scope: W }))).toBe('workspace');
    expect(groupKind(group('Sales admins', { owner_scope: W }))).toBe('workspace-admins');
    expect(groupKind(group('Acme admins', { owner_scope: O }))).toBe('org-admins');
    expect(groupKind(group('Acme people', { owner_scope: O }))).toBe('people');
    expect(groupKind(group('Workflow runners', { owner_scope: O }))).toBe('capability');
    expect(groupKind(group('Models · all'))).toBe('capability');
    expect(groupKind(group('Platform admins'))).toBe('platform-admins');
    // The platform's "Workspace admins" (every "<W> admins" and "<O> admins" person).
    expect(groupKind(group('Workspace admins'))).toBe('workspace-admins');
    expect(groupKind(group('Data team', { owner_scope: W }))).toBe('custom');
    // "Members" owned by a workspace is someone's own group, not the level.
    expect(groupKind(group('Members', { owner_scope: W }))).toBe('custom');
  });

  it('ranks the model groups before custom ones: platform admins, levels, admins, workspaces, people, capabilities', () => {
    const kinds = ['custom', 'capability', 'people', 'workspace', 'workspace-admins', 'org-admins', 'level', 'platform-admins'] as const;
    expect([...kinds].sort((a, b) => groupRank(a) - groupRank(b))).toEqual([
      'platform-admins',
      'level',
      'org-admins',
      'workspace-admins',
      'workspace',
      'people',
      'capability',
      'custom',
    ]);
  });
});
