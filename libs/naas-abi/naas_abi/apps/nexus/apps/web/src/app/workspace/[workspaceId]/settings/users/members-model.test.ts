import { describe, expect, it } from 'vitest';
import {
  levelLabel,
  memberCellValues,
  memberSearchTexts,
  readWorkspaceMember,
  sortMembers,
  type WorkspaceMemberRow,
} from './members-model';

const raw = (over: Record<string, unknown> = {}) => ({
  id: 'm1',
  workspace_id: 'ws-1',
  user_id: 'usr_bob',
  role: 'member',
  level: 'member',
  email: 'bob@example.com',
  name: 'Bob',
  created_at: '2026-11-01T10:00:00',
  source: 'workspace',
  status: 'active',
  ...over,
});

describe('a member of the workspace', () => {
  it('reads as a level and whether they administer it', () => {
    const row = readWorkspaceMember(raw({ role: 'admin', level: 'member' }));
    expect(row).toMatchObject({ user_id: 'usr_bob', level: 'member', admin: true, source: 'workspace', status: 'active' });
    expect(row.joinedAt?.toISOString().startsWith('2026-11-01')).toBe(true);
    expect(readWorkspaceMember(raw({ role: 'viewer', level: 'viewer' }))).toMatchObject({ level: 'viewer', admin: false });
  });

  it('has no level when they hold a role of before, and no owner', () => {
    const row = readWorkspaceMember(raw({ role: 'owner', level: null, name: null, email: null, created_at: null }));
    expect(row).toMatchObject({ level: null, admin: true, name: 'Unknown', email: '', joinedAt: null });
    expect(levelLabel(null)).toBe('—');
    expect(levelLabel('viewer')).toBe('Viewer');
  });

  it('reads their roles, and gives each column the texts its filter and facets see', () => {
    const ann = readWorkspaceMember(
      raw({
        user_id: 'a',
        principal_id: 'usr_a',
        name: 'Ann',
        email: 'ann@example.com',
        roles: [
          { kind: 'group', id: 'grp_1', name: 'Alpha workspace', implied: true },
          { kind: 'policy', id: 'pol_1', name: 'Alpha reports', scope: 'abi:nexus:organization/o/nexus:workspace/w' },
          { kind: 'nonsense', id: 'x' },
        ],
      })
    );
    expect(ann.principalId).toBe('usr_a');
    expect(ann.roles).toEqual([
      { kind: 'group', id: 'grp_1', name: 'Alpha workspace', scope: null, implied: true },
      { kind: 'policy', id: 'pol_1', name: 'Alpha reports', scope: 'abi:nexus:organization/o/nexus:workspace/w', implied: false },
    ]);
    expect(memberCellValues(ann, 'member')).toEqual(['Ann', 'ann@example.com']);
    expect(memberCellValues(ann, 'role')).toEqual(['Alpha workspace', 'Alpha reports']);
    expect(memberCellValues(ann, 'joined')).toEqual(['2026-11-01']);
    const old = readWorkspaceMember(raw({ role: 'viewer', level: null, created_at: null, principal_id: null }));
    expect(old.principalId).toBeNull();
    expect(memberCellValues(old, 'role')).toEqual(['No role']);
    expect(memberCellValues(old, 'joined')).toEqual(['No date']);
    const moved = readWorkspaceMember(raw({ created_at: null, joined_before: '2026-11-24T09:00:00Z' }));
    expect(moved.joinedBefore?.toISOString().startsWith('2026-11-24')).toBe(true);
    expect(memberCellValues(moved, 'joined')).toEqual(['before 2026-11-24']);
  });

  it('is found by any column, by their level and by Invited', () => {
    const row = readWorkspaceMember(raw({ status: 'invited', source: 'organization' }));
    const texts = memberSearchTexts(row).join(' ');
    for (const word of ['Bob', 'bob@example.com', 'Member', 'Invited']) {
      expect(texts).toContain(word);
    }
  });

  it('sorts by a column either way, the undated last, ties by email', () => {
    const rows: WorkspaceMemberRow[] = [
      readWorkspaceMember(raw({ user_id: 'c', name: 'Cid', email: 'cid@example.com', created_at: '2026-10-01T09:00:00' })),
      readWorkspaceMember(raw({ user_id: 'a', name: 'Ann', email: 'ann@example.com', role: 'admin', created_at: null })),
      readWorkspaceMember(raw({ user_id: 'b', name: 'Bob', role: 'viewer', level: 'viewer', created_at: '2026-11-05T09:00:00' })),
    ];
    const ids = (sorted: WorkspaceMemberRow[]) => sorted.map((r) => r.user_id);
    expect(ids(sortMembers(rows, 'member', 'asc'))).toEqual(['a', 'b', 'c']);
    expect(ids(sortMembers(rows, 'member', 'desc'))).toEqual(['c', 'b', 'a']);
    expect(ids(sortMembers(rows, 'role', 'asc'))).toEqual(['a', 'b', 'c']);
    expect(ids(sortMembers(rows, 'joined', 'asc'))).toEqual(['c', 'b', 'a']);
    expect(ids(sortMembers(rows, 'joined', 'desc'))).toEqual(['b', 'c', 'a']);
  });
});
