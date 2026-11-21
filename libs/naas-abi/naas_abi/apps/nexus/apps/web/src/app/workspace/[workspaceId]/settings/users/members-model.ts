// Workspace settings › Users: the pure part of the members table. A member is a level (Member or
// Viewer, in all their workspaces) and whether they administer this workspace (#1589).

import { LEVEL_LABELS, memberStatus, readLevel, type Level, type MemberStatus } from '@/lib/people';

export type WorkspaceMemberRow = {
  id: string;
  user_id: string;
  name: string;
  email: string;
  /** Their level; null for a role of before held directly (until the access move). */
  level: Level | null;
  /** They administer this workspace ("<W> admins"). */
  admin: boolean;
  joinedAt: Date | null;
  /** 'organization': they reach it through their org admin role; managed in Organization › Users. */
  source: 'workspace' | 'organization';
  status: MemberStatus;
};

/** A row of `GET /api/workspaces/{ws}/members`. */
export function readWorkspaceMember(m: Record<string, unknown>): WorkspaceMemberRow {
  const role = m.role;
  return {
    id: String(m.id ?? ''),
    user_id: String(m.user_id ?? ''),
    name: (typeof m.name === 'string' && m.name) || 'Unknown',
    email: (typeof m.email === 'string' && m.email) || '',
    level: readLevel(m.level),
    // An owner of before administers it too: Owner is no longer assigned.
    admin: role === 'admin' || role === 'owner',
    joinedAt: typeof m.created_at === 'string' && m.created_at ? new Date(m.created_at) : null,
    source: m.source === 'organization' ? 'organization' : 'workspace',
    status: memberStatus(m.status),
  };
}

export function levelLabel(level: Level | null): string {
  return level ? LEVEL_LABELS[level] : '—';
}

/** Whether the caller changes this member's level and admin toggle here. */
export function accessEditable(
  row: Pick<WorkspaceMemberRow, 'user_id' | 'source'>,
  { canManage, selfId }: { canManage: boolean; selfId: string | null | undefined }
): boolean {
  return canManage && row.source === 'workspace' && row.user_id !== selfId;
}

export type MemberFilter = 'all' | 'admin' | Level;

export const MEMBER_FILTERS: { value: MemberFilter; label: string }[] = [
  { value: 'all', label: 'Everyone' },
  { value: 'admin', label: 'Admins' },
  { value: 'member', label: 'Members' },
  { value: 'viewer', label: 'Viewers' },
];

export function filterMembers(rows: WorkspaceMemberRow[], filter: MemberFilter, search: string): WorkspaceMemberRow[] {
  const query = search.trim().toLowerCase();
  return rows.filter((row) => {
    if (filter === 'admin' && !row.admin) return false;
    if ((filter === 'member' || filter === 'viewer') && row.level !== filter) return false;
    return !query || row.name.toLowerCase().includes(query) || row.email.toLowerCase().includes(query);
  });
}
