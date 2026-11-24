import { describe, expect, it } from 'vitest';
import { accessEditable, filterMembers, levelLabel, readWorkspaceMember, type WorkspaceMemberRow } from './members-model';

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

  it('is filtered by level or admin, and by name or email', () => {
    const rows: WorkspaceMemberRow[] = [
      readWorkspaceMember(raw({ user_id: 'a', name: 'Ann', role: 'admin' })),
      readWorkspaceMember(raw({ user_id: 'b', name: 'Bob', role: 'viewer', level: 'viewer' })),
      readWorkspaceMember(raw({ user_id: 'c', name: 'Cid', email: 'cid@example.com' })),
    ];
    expect(filterMembers(rows, 'all', '').map((r) => r.user_id)).toEqual(['a', 'b', 'c']);
    expect(filterMembers(rows, 'admin', '').map((r) => r.user_id)).toEqual(['a']);
    expect(filterMembers(rows, 'viewer', '').map((r) => r.user_id)).toEqual(['b']);
    expect(filterMembers(rows, 'member', '').map((r) => r.user_id)).toEqual(['a', 'c']);
    expect(filterMembers(rows, 'all', 'cid@').map((r) => r.user_id)).toEqual(['c']);
  });
});
