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

// -- the table: columns that sort and filter, as Platform settings › Users -----------------

export type MemberColumnId = 'member' | 'level' | 'admin' | 'joined';

export const MEMBER_COLUMNS: { id: MemberColumnId; label: string }[] = [
  { id: 'member', label: 'Member' },
  { id: 'level', label: 'Level' },
  { id: 'admin', label: 'Workspace admin' },
  { id: 'joined', label: 'Joined' },
];

export const ADMIN = 'Admin';
export const NOT_ADMIN = 'Not admin';
export const NO_DATE = 'No date';
const INVITED = 'Invited';
const VIA_ORGANIZATION = 'Via organization';

/** `YYYY-MM-DD` of the day they joined; '' when unknown. */
export function joinedDay(row: Pick<WorkspaceMemberRow, 'joinedAt'>): string {
  return row.joinedAt && !Number.isNaN(row.joinedAt.getTime()) ? row.joinedAt.toISOString().slice(0, 10) : '';
}

/** The texts of a cell, as the column filters and their facets see them. */
export function memberCellValues(row: WorkspaceMemberRow, column: MemberColumnId): string[] {
  switch (column) {
    case 'member':
      return [row.name, row.email].filter((v, i, all) => v && all.indexOf(v) === i);
    case 'level':
      return [levelLabel(row.level)];
    case 'admin':
      return [row.admin ? ADMIN : NOT_ADMIN];
    case 'joined':
      return [joinedDay(row) || NO_DATE];
  }
}

/** Everything the search looks in: every column, whether they are invited, and how they reach it. */
export function memberSearchTexts(row: WorkspaceMemberRow): string[] {
  return [
    ...MEMBER_COLUMNS.flatMap((column) => memberCellValues(row, column.id)),
    row.status === 'invited' ? INVITED : '',
    row.source === 'organization' ? VIA_ORGANIZATION : '',
  ];
}

export type SortDir = 'asc' | 'desc';

function sortText(row: WorkspaceMemberRow, column: MemberColumnId): string {
  if (column === 'member') return (row.name || row.email).toLowerCase();
  return memberCellValues(row, column).join(' ').toLowerCase();
}

/** Sorted by a column, those with no date last whichever way; ties by email. */
export function sortMembers(rows: WorkspaceMemberRow[], column: MemberColumnId, dir: SortDir): WorkspaceMemberRow[] {
  const sign = dir === 'asc' ? 1 : -1;
  const undated = (row: WorkspaceMemberRow) => (column === 'joined' && !joinedDay(row) ? 1 : 0);
  return [...rows].sort(
    (a, b) =>
      undated(a) - undated(b) ||
      sign * sortText(a, column).localeCompare(sortText(b, column)) ||
      a.email.localeCompare(b.email)
  );
}
