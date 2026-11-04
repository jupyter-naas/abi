/**
 * Platform Settings › Users: the pure part (the rows' cells, filters, sort and
 * export, the person's page, the delete confirmation, the API's words).
 */

/** Platform Settings › Users (no React: the middleware reads it too). */
export const PLATFORM_USERS_PATH = '/settings/users';

export interface AdminUserOrganization {
  id: string;
  name: string;
  role: string;
}

export interface AdminUser {
  /** The Nexus user id; someone invited who has no account yet: `invited:<email>`. */
  id: string;
  kind: 'account' | 'invitation';
  email: string;
  name: string;
  avatar: string | null;
  /** Their IAM id, which the person's page opens on (null: IAM has none yet). */
  principal_id: string | null;
  /** Signed in at least once, or invited and not yet. */
  status: 'signed_in' | 'invited';
  deactivated: boolean;
  is_superadmin: boolean;
  created_at: string;
  organizations: AdminUserOrganization[];
  provider: string | null;
  /** What the identity provider could not follow, after a change. */
  warning?: string | null;
}

export interface InviteOutcome {
  user: AdminUser;
  user_created: boolean;
  sign_in_email_sent: boolean;
  provisioning_skipped: boolean;
  renewed: boolean;
  warning: string | null;
}

export interface Deletion {
  user: AdminUser;
  /** Why the account cannot be deleted (it alone owns an organization...), else null. */
  blocked: string | null;
  /** What deleting leaves behind (a provider that keeps their account), else null. */
  warning?: string | null;
  goes: {
    provider_account: { provider: string; display_name: string; managed_in_provider: boolean } | null;
    iam_user: string | null;
    attachments: number;
    memberships: { scope: string; label: string; role: string }[];
    groups: number;
    sessions: number;
    api_keys: number;
    invitations: number;
  };
  stays: { workspaces: { id: string; name: string }[] };
}

export interface InvitationProvider {
  name: string;
  display_name: string;
  provisioning: string;
  managed_in_provider: boolean;
}

export interface InvitationProviders {
  enabled: boolean;
  default_provider: string | null;
  providers: InvitationProvider[];
}

/** The lifecycle actions, as `GET /api/iam/admin/access` names them at the platform. */
export const USER_ACTIONS = {
  list: 'nexus:ListUsers',
  invite: 'nexus:InviteUser',
  update: 'nexus:UpdateUser',
  suspend: 'nexus:SuspendUser',
  resume: 'nexus:ResumeUser',
  remove: 'nexus:DeleteUser',
} as const;

export type ColumnId = 'user' | 'iam' | 'status' | 'superadmin' | 'organizations' | 'created';

export const COLUMNS: { id: ColumnId; label: string }[] = [
  { id: 'user', label: 'User' },
  { id: 'iam', label: 'IAM id' },
  { id: 'status', label: 'Status' },
  { id: 'superadmin', label: 'Superadmin' },
  { id: 'organizations', label: 'Organizations' },
  { id: 'created', label: 'Created' },
];

export const SIGNED_IN = 'Signed in';
export const INVITED = 'Invited, not yet';
export const DEACTIVATED = 'Deactivated';
export const ACTIVE = 'Active';
export const SUPERADMIN = 'Superadmin';
export const NOT_SUPERADMIN = 'Not superadmin';
export const NO_ORGANIZATION = 'No organization';
export const NO_IAM_ID = 'None yet';

export function statusLabel(user: AdminUser): string {
  return user.status === 'signed_in' ? SIGNED_IN : INVITED;
}

/** `YYYY-MM-DD`, or the text as it came when it is not a date. */
export function createdDay(user: AdminUser): string {
  const at = new Date(user.created_at);
  return Number.isNaN(at.getTime()) ? user.created_at || '' : at.toISOString().slice(0, 10);
}

/** The texts of a cell, as the column filters and their facets see them. */
export function cellValues(user: AdminUser, column: ColumnId): string[] {
  switch (column) {
    case 'user':
      return [user.name || user.email, user.email].filter((v, i, all) => v && all.indexOf(v) === i);
    case 'iam':
      return [user.principal_id || NO_IAM_ID];
    case 'status':
      return [statusLabel(user), user.deactivated ? DEACTIVATED : ACTIVE];
    case 'superadmin':
      return [user.is_superadmin ? SUPERADMIN : NOT_SUPERADMIN];
    case 'organizations':
      return user.organizations.length > 0
        ? [...new Set(user.organizations.map((o) => o.name || o.id))].sort((a, b) => a.localeCompare(b))
        : [NO_ORGANIZATION];
    case 'created':
      return [createdDay(user)];
  }
}

/** Everything the global search looks in: every column, the ids and the provider. */
export function searchTexts(user: AdminUser): string[] {
  return [
    ...COLUMNS.flatMap((column) => cellValues(user, column.id)),
    user.id,
    user.provider ?? '',
    ...user.organizations.map((o) => o.role),
  ];
}

export type SortDir = 'asc' | 'desc';

function sortText(user: AdminUser, column: ColumnId): string {
  if (column === 'created') return user.created_at || '';
  if (column === 'user') return (user.name || user.email).toLowerCase();
  return cellValues(user, column).join(' ').toLowerCase();
}

/** The rows sorted by a column, then by email, so equal cells keep one order. */
export function sortUsers(users: AdminUser[], column: ColumnId, dir: SortDir): AdminUser[] {
  const sign = dir === 'asc' ? 1 : -1;
  return [...users].sort(
    (a, b) =>
      sign * sortText(a, column).localeCompare(sortText(b, column)) || a.email.localeCompare(b.email)
  );
}

/** The export: every column of the visible rows. */
export const EXPORT_HEADERS = [
  'Name',
  'Email',
  'IAM id',
  'Status',
  'Deactivated',
  'Superadmin',
  'Organizations',
  'Created',
  'Identity provider',
] as const;

export function exportRow(user: AdminUser): string[] {
  return [
    user.name,
    user.email,
    user.principal_id ?? '',
    statusLabel(user),
    user.deactivated ? 'yes' : 'no',
    user.is_superadmin ? 'yes' : 'no',
    user.organizations.map((o) => `${o.name || o.id} (${o.role})`).join('; '),
    createdDay(user),
    user.provider ?? '',
  ];
}

/** The person's page in Roles & permissions, where their access is seen and changed. */
export function personHref(user: AdminUser): string | null {
  if (!user.principal_id) return null;
  return `/settings/roles?section=people&person=${encodeURIComponent(user.principal_id)}`;
}

export function isSelf(user: AdminUser, selfId: string | null | undefined): boolean {
  return !!selfId && (user.id === selfId || user.principal_id === selfId);
}

/** Delete is sent only once the email is typed back exactly (case aside). */
export function deleteConfirmed(user: AdminUser, typed: string): boolean {
  const email = user.email.trim().toLowerCase();
  return email !== '' && typed.trim().toLowerCase() === email;
}

/** "1 session", "2 sessions". */
export function count(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** What the API said about a refusal: its `detail` when it is text, else the status. */
export function errorText(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === 'string') return first.msg;
  }
  if (status === 403) return 'You may not do this.';
  if (status === 404) return 'User not found.';
  if (status === 0) return 'The API did not answer.';
  return `The API answered ${status}.`;
}

/** What an invitation did, in words, for the admin who sent it. */
export function inviteSummary(outcome: InviteOutcome): string[] {
  const said: string[] = [];
  said.push(outcome.renewed ? `Invitation to ${outcome.user.email} renewed.` : `${outcome.user.email} invited.`);
  if (outcome.user_created) said.push('Their account was made at the identity provider.');
  if (outcome.provisioning_skipped) {
    said.push(
      'No account was made at the identity provider (you may not create one there): they sign in with an account they have.'
    );
  }
  said.push(outcome.sign_in_email_sent ? 'A sign-in link was emailed to them.' : 'No email could be sent: send them the sign-in link yourself.');
  if (outcome.warning) said.push(outcome.warning);
  return said;
}
