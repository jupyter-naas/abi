import { describe, expect, it } from 'vitest';
import {
  accessEditable,
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

  it('is changed here only by a manager, never themselves nor someone reaching it through the organization', () => {
    const row = readWorkspaceMember(raw());
    expect(accessEditable(row, { canManage: true, selfId: 'usr_me' })).toBe(true);
    expect(accessEditable(row, { canManage: false, selfId: 'usr_me' })).toBe(false);
    expect(accessEditable(row, { canManage: true, selfId: 'usr_bob' })).toBe(false);
    expect(accessEditable({ ...row, source: 'organization' }, { canManage: true, selfId: 'usr_me' })).toBe(false);
  });

  it('gives each column the texts its filter and facets see', () => {
    const ann = readWorkspaceMember(raw({ user_id: 'a', name: 'Ann', email: 'ann@example.com', role: 'admin' }));
    expect(memberCellValues(ann, 'member')).toEqual(['Ann', 'ann@example.com']);
    expect(memberCellValues(ann, 'level')).toEqual(['Member']);
    expect(memberCellValues(ann, 'admin')).toEqual(['Admin']);
    expect(memberCellValues(ann, 'joined')).toEqual(['2026-11-01']);
    const old = readWorkspaceMember(raw({ role: 'viewer', level: null, created_at: null }));
    expect(memberCellValues(old, 'level')).toEqual(['—']);
    expect(memberCellValues(old, 'admin')).toEqual(['Not admin']);
    expect(memberCellValues(old, 'joined')).toEqual(['No date']);
  });

  it('is found by any column, by Invited, and by Via organization', () => {
    const row = readWorkspaceMember(raw({ status: 'invited', source: 'organization' }));
    const texts = memberSearchTexts(row).join(' ');
    for (const word of ['Bob', 'bob@example.com', 'Member', 'Not admin', 'Invited', 'Via organization']) {
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
    expect(ids(sortMembers(rows, 'level', 'asc'))).toEqual(['a', 'c', 'b']);
    expect(ids(sortMembers(rows, 'admin', 'asc'))).toEqual(['a', 'b', 'c']);
    expect(ids(sortMembers(rows, 'joined', 'asc'))).toEqual(['c', 'b', 'a']);
    expect(ids(sortMembers(rows, 'joined', 'desc'))).toEqual(['b', 'c', 'a']);
  });
});
