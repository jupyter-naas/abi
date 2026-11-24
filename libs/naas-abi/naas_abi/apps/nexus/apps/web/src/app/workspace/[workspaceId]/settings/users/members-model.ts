// Workspace settings › Users: the pure part of the members table. A member's Role is the groups
// they are in and the policies attached to them that bear on the workspace; their level (Member or
// Viewer, in all their workspaces) is one of those groups.

import { LEVEL_LABELS, memberStatus, readLevel, type Level, type MemberStatus } from '@/lib/people';

/** One of a member's roles here: a group they are in, or a policy attached to them. */
export type MemberRole = {
  kind: 'group' | 'policy';
  id: string;
  name: string;
  scope: string | null;
  /** The workspace's own group, shown for an admin who reaches the workspace through an admins group. */
  implied: boolean;
};

export type WorkspaceMemberRow = {
  id: string;
  user_id: string;
  /** Their IAM id, which their page (Edit) opens; null when IAM does not name them. */
  principalId: string | null;
  name: string;
  email: string;
  /** Their level; null for a role of before held directly (until the access move). */
  level: Level | null;
  /** They administer this workspace ("<W> admins"). */
  admin: boolean;
  joinedAt: Date | null;
  /** For a membership older than its date (made before the access move): they joined before this. */
  joinedBefore: Date | null;
  /** 'organization': they reach it through their org admin role; managed in Organization › Users. */
  source: 'workspace' | 'organization';
  status: MemberStatus;
  /** Their groups and policies that bear on the workspace. */
  roles: MemberRole[];
};

function readRoles(value: unknown): MemberRole[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((r) => {
    if (!r || typeof r !== 'object') return [];
    const { kind, id, name, scope, implied } = r as Record<string, unknown>;
    if ((kind !== 'group' && kind !== 'policy') || typeof id !== 'string') return [];
    return [
      {
        kind,
        id,
        name: typeof name === 'string' && name ? name : id,
        scope: typeof scope === 'string' ? scope : null,
        implied: implied === true,
      },
    ];
  });
}

/** A row of `GET /api/workspaces/{ws}/members`. */
export function readWorkspaceMember(m: Record<string, unknown>): WorkspaceMemberRow {
  const role = m.role;
  return {
    id: String(m.id ?? ''),
    user_id: String(m.user_id ?? ''),
    principalId: typeof m.principal_id === 'string' && m.principal_id ? m.principal_id : null,
    name: (typeof m.name === 'string' && m.name) || 'Unknown',
    email: (typeof m.email === 'string' && m.email) || '',
    level: readLevel(m.level),
    // An owner of before administers it too: Owner is no longer assigned.
    admin: role === 'admin' || role === 'owner',
    joinedAt: typeof m.created_at === 'string' && m.created_at ? new Date(m.created_at) : null,
    joinedBefore: typeof m.joined_before === 'string' && m.joined_before ? new Date(m.joined_before) : null,
    source: m.source === 'organization' ? 'organization' : 'workspace',
    status: memberStatus(m.status),
    roles: readRoles(m.roles),
  };
}

export function levelLabel(level: Level | null): string {
  return level ? LEVEL_LABELS[level] : '—';
}

// -- the table: columns that sort and filter, as Platform settings › Users -----------------

export type MemberColumnId = 'member' | 'role' | 'joined';

export const MEMBER_COLUMNS: { id: MemberColumnId; label: string }[] = [
  { id: 'member', label: 'Member' },
  { id: 'role', label: 'Role' },
  { id: 'joined', label: 'Joined' },
];

export const NO_ROLE = 'No role';
export const NO_DATE = 'No date';
const INVITED = 'Invited';

const day = (at: Date | null) => (at && !Number.isNaN(at.getTime()) ? at.toISOString().slice(0, 10) : '');

/** `YYYY-MM-DD` of the day they joined, "before YYYY-MM-DD" for a membership older than its date; '' when unknown. */
export function joinedDay(row: Pick<WorkspaceMemberRow, 'joinedAt' | 'joinedBefore'>): string {
  if (day(row.joinedAt)) return day(row.joinedAt);
  return day(row.joinedBefore) ? `before ${day(row.joinedBefore)}` : '';
}

/** The day to sort by: the day they joined, else the day they joined before. */
function joinedSortDay(row: Pick<WorkspaceMemberRow, 'joinedAt' | 'joinedBefore'>): string {
  return day(row.joinedAt) || day(row.joinedBefore);
}

/** The texts of a cell, as the column filters and their facets see them. */
export function memberCellValues(row: WorkspaceMemberRow, column: MemberColumnId): string[] {
  switch (column) {
    case 'member':
      return [row.name, row.email].filter((v, i, all) => v && all.indexOf(v) === i);
    case 'role':
      return row.roles.length > 0 ? [...new Set(row.roles.map((r) => r.name))] : [NO_ROLE];
    case 'joined':
      return [joinedDay(row) || NO_DATE];
  }
}

/** Everything the search looks in: every column, their level, and whether they are invited. */
export function memberSearchTexts(row: WorkspaceMemberRow): string[] {
  return [
    ...MEMBER_COLUMNS.flatMap((column) => memberCellValues(row, column.id)),
    row.level ? levelLabel(row.level) : '',
    row.status === 'invited' ? INVITED : '',
  ];
}

export type SortDir = 'asc' | 'desc';

function sortText(row: WorkspaceMemberRow, column: MemberColumnId): string {
  if (column === 'member') return (row.name || row.email).toLowerCase();
  if (column === 'joined') return joinedSortDay(row);
  return memberCellValues(row, column).join(' ').toLowerCase();
}

/** Sorted by a column, those with no date last whichever way; ties by email. */
export function sortMembers(rows: WorkspaceMemberRow[], column: MemberColumnId, dir: SortDir): WorkspaceMemberRow[] {
  const sign = dir === 'asc' ? 1 : -1;
  const undated = (row: WorkspaceMemberRow) => (column === 'joined' && !joinedSortDay(row) ? 1 : 0);
  return [...rows].sort(
    (a, b) =>
      undated(a) - undated(b) ||
      sign * sortText(a, column).localeCompare(sortText(b, column)) ||
      a.email.localeCompare(b.email)
  );
}
