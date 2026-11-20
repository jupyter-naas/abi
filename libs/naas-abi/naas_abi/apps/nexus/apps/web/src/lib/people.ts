// People: the platform user directory as the workspace and organization settings see it.
// Search an organization's people to add them to a workspace, create (or link) someone by
// email, and resend an invited person their sign-in email. The shapes are the API's
// (`/api/workspaces/{ws}/members/*`, `/api/organizations/{org}/members/*`).

import type { InviteProvider } from '@/lib/invitations';
import { policyIdsToSend, readApiError } from '@/lib/invitations';

export type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

/** Invited: created, not signed in yet. Active: signed in at least once. */
export type MemberStatus = 'active' | 'invited';

export type WorkspaceRole = 'owner' | 'admin' | 'member' | 'viewer';
export type OrganizationRole = 'owner' | 'admin' | 'member';

/** One suggestion of `GET /api/workspaces/{ws}/members/candidates`. */
export type MemberCandidate = {
  user_id: string;
  name: string | null;
  email: string;
  avatar: string | null;
  status: MemberStatus;
  org_role: OrganizationRole | null;
};

/** The profile a created person gets in the organization (only the fields filled in). */
export type PeopleProfile = {
  organization?: string;
  job_title?: string;
  bio?: string;
  service_line?: string;
  country?: string;
  interest?: string;
};

/** What a create (or link) route answers: the same whether the account was made or found. */
export type CreatedPerson = {
  user: { id: string; email: string; name: string | null; status: MemberStatus };
  /** The membership made: a workspace member, or an organization member (null: no org role). */
  member: Record<string, unknown> | null;
  provider: InviteProvider | null;
  emailSent: boolean;
  warning: string | null;
};

/** The search asks the API from this many characters on (the API answers [] below). */
export const CANDIDATE_MIN_CHARS = 2;
/** At most this many suggestions (the API's own cap is 20). */
export const CANDIDATE_LIMIT = 10;
/** How long the search waits for the typing to stop. */
export const CANDIDATE_DELAY_MS = 250;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function looksLikeEmail(text: string): boolean {
  return EMAIL.test(text.trim());
}

/** The text a search asks for, or null while it is too short to ask. */
export function candidateQuery(text: string): string | null {
  const q = text.trim();
  return q.length >= CANDIDATE_MIN_CHARS ? q : null;
}

export function candidatesUrl(workspaceId: string, q: string, limit = CANDIDATE_LIMIT): string {
  const query = new URLSearchParams({ q, limit: String(Math.min(Math.max(limit, 1), 20)) });
  return `/api/workspaces/${encodeURIComponent(workspaceId)}/members/candidates?${query}`;
}

/** How a suggestion is named: its name, else its email. */
export function candidateLabel(candidate: Pick<MemberCandidate, 'name' | 'email'>): string {
  return candidate.name?.trim() || candidate.email;
}

/**
 * The create page of a workspace, prefilled with what was typed: an email goes in the email
 * field, anything else in the name.
 */
export function createUserHref(workspaceId: string, typed: string): string {
  const text = typed.trim();
  const base = `/workspace/${encodeURIComponent(workspaceId)}/settings/users/new`;
  if (!text) return base;
  const query = new URLSearchParams(looksLikeEmail(text) ? { email: text } : { name: text });
  return `${base}?${query}`;
}

/** The prefill the create page reads back from its query (`?email=` or `?name=`). */
export function createUserPrefill(params: { get(name: string): string | null }): { email: string; name: string } {
  return { email: params.get('email')?.trim() ?? '', name: params.get('name')?.trim() ?? '' };
}

/** A member's status as a row says it; anything but "invited" is active. */
export function memberStatus(raw: unknown): MemberStatus {
  return raw === 'invited' ? 'invited' : 'active';
}

/** The badge a member's status shows: invited only, active people show none. */
export function statusBadge(status: MemberStatus | undefined): { label: string; title: string } | null {
  if (status !== 'invited') return null;
  return {
    label: 'Invited',
    title: 'Created and given access, has not signed in yet. Resend emails them a sign-in link again.',
  };
}

// -- the request bodies ------------------------------------------------------------

/** `POST /api/workspaces/{ws}/members`: add someone the search found. */
export function addMemberBody(add: {
  userId: string;
  role: WorkspaceRole;
  policyIds?: readonly string[];
}): Record<string, unknown> {
  return { user_id: add.userId, role: add.role, ...policyIdsToSend(add.policyIds) };
}

/** Only the profile fields that were filled in, trimmed; undefined when none was. */
export function filledProfile(profile: Partial<Record<keyof PeopleProfile, string>>): PeopleProfile | undefined {
  const filled: PeopleProfile = {};
  for (const [key, value] of Object.entries(profile) as [keyof PeopleProfile, string | undefined][]) {
    const text = value?.trim();
    if (text) filled[key] = text;
  }
  return Object.keys(filled).length ? filled : undefined;
}

export type WorkspaceCreate = {
  email: string;
  name?: string;
  role: WorkspaceRole;
  policyIds?: readonly string[];
  provider?: string;
  profile?: PeopleProfile;
};

/** `POST /api/workspaces/{ws}/members/invite`: create (or link) someone into the workspace. */
export function workspaceCreateBody(create: WorkspaceCreate): Record<string, unknown> {
  const name = create.name?.trim();
  return {
    email: create.email.trim(),
    ...(name ? { name } : {}),
    role: create.role,
    ...policyIdsToSend(create.policyIds),
    ...(create.provider ? { provider: create.provider } : {}),
    ...(create.profile && Object.keys(create.profile).length ? { profile: create.profile } : {}),
  };
}

export type OrganizationCreate = {
  email: string;
  name?: string;
  /** null: no org role, workspace access only (at least one workspace then). */
  role: OrganizationRole | null;
  workspaces: { id: string; role: WorkspaceRole }[];
  policyIds?: readonly string[];
  provider?: string;
  profile?: PeopleProfile;
};

/**
 * `POST /api/organizations/{org}/members/invite`: one request with every workspace picked.
 * The profile fields go flat, beside the email, as the route reads them.
 */
export function organizationCreateBody(create: OrganizationCreate): Record<string, unknown> {
  if (create.role === null && create.workspaces.length === 0) {
    throw new Error('Pick an organization role, or at least one workspace.');
  }
  const name = create.name?.trim();
  return {
    email: create.email.trim(),
    ...(name ? { name } : {}),
    role: create.role,
    workspaces: create.workspaces.map((w) => ({ id: w.id, role: w.role })),
    ...policyIdsToSend(create.policyIds),
    ...(create.provider ? { provider: create.provider } : {}),
    ...(create.profile ?? {}),
  };
}

/** Reads a create (or link) answer; null when it is not that shape. */
export function readCreatedPerson(data: unknown): CreatedPerson | null {
  const answer = (data ?? {}) as Record<string, unknown>;
  const user = answer.user as Record<string, unknown> | undefined;
  if (!user || typeof user !== 'object' || typeof user.id !== 'string') return null;
  const provider = answer.provider;
  return {
    user: {
      id: user.id,
      email: typeof user.email === 'string' ? user.email : '',
      name: typeof user.name === 'string' ? user.name : null,
      status: memberStatus(user.status),
    },
    member: answer.member && typeof answer.member === 'object' ? (answer.member as Record<string, unknown>) : null,
    provider: provider && typeof provider === 'object' ? (provider as InviteProvider) : null,
    emailSent: answer.sign_in_email_sent === true,
    warning: typeof answer.warning === 'string' && answer.warning ? answer.warning : null,
  };
}

/**
 * What the admin is told once someone is created or linked. It never says which: the answer
 * is the same either way, so an email's account is not revealed.
 */
export function createdMessage(created: CreatedPerson, where: string): string {
  const who = created.user.email || created.user.name || 'They';
  const via = created.provider?.display_name ? ` with ${created.provider.display_name}` : '';
  const mail = created.emailSent
    ? ` They were emailed a link to sign in${via}.`
    : ` No email could be sent: tell them to sign in${via} using this email.`;
  const warning = created.warning ? ` Warning: ${created.warning}.` : '';
  return `${who} was added to ${where}.${mail}${warning}`;
}

/**
 * Members, back from the create page: who was added and whether they were emailed, which
 * the page words itself (`addedNotice`); never a text taken from the URL as is.
 */
export function membersAddedHref(membersPath: string, created: CreatedPerson): string {
  const query = new URLSearchParams({ added: created.user.email, mailed: created.emailSent ? '1' : '0' });
  return `${membersPath}?${query}`;
}

/** The notice Members shows for `?added=<email>&mailed=1|0`; null without one. */
export function addedNotice(params: { get(name: string): string | null }): string | null {
  const email = params.get('added')?.trim();
  if (!email || !looksLikeEmail(email)) return null;
  const mailed = params.get('mailed') === '1';
  return mailed
    ? `${email} was added to this workspace. They were emailed a link to sign in.`
    : `${email} was added to this workspace. No email could be sent: tell them to sign in using this email.`;
}

/** What Resend tells the admin. */
export function resentMessage(email: string, sent: boolean): string {
  return sent ? `Sign-in email sent again to ${email}.` : `No email could be sent to ${email}.`;
}

// -- the API -----------------------------------------------------------------------

async function defaultFetcher(url: string, options?: RequestInit): Promise<Response> {
  const { authFetch } = await import('@/stores/auth');
  return authFetch(url, options);
}

async function json<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) throw new Error(await readApiError(response, fallback));
  return (await response.json()) as T;
}

const post = (body?: unknown): RequestInit =>
  body === undefined
    ? { method: 'POST' }
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };

export type PeopleApi = {
  candidates: (workspaceId: string, q: string, signal?: AbortSignal) => Promise<MemberCandidate[]>;
  addMember: (
    workspaceId: string,
    add: { userId: string; role: WorkspaceRole; policyIds?: readonly string[] }
  ) => Promise<{ member: Record<string, unknown>; emailSent: boolean }>;
  createInWorkspace: (workspaceId: string, create: WorkspaceCreate) => Promise<CreatedPerson>;
  createInOrganization: (organizationId: string, create: OrganizationCreate) => Promise<CreatedPerson>;
  resendWorkspace: (workspaceId: string, userId: string) => Promise<boolean>;
  resendOrganization: (organizationId: string, userId: string) => Promise<boolean>;
};

function created(data: unknown, fallback: string): CreatedPerson {
  const person = readCreatedPerson(data);
  if (!person) throw new Error(fallback);
  return person;
}

export function createPeopleApi(fetcher: Fetcher = defaultFetcher): PeopleApi {
  const ws = (id: string) => `/api/workspaces/${encodeURIComponent(id)}/members`;
  const org = (id: string) => `/api/organizations/${encodeURIComponent(id)}/members`;
  return {
    async candidates(workspaceId, q, signal) {
      const query = candidateQuery(q);
      if (!query) return [];
      const data = await json<{ items?: MemberCandidate[] }>(
        await fetcher(candidatesUrl(workspaceId, query), signal ? { signal } : undefined),
        'Failed to search people'
      );
      return Array.isArray(data.items) ? data.items.map((c) => ({ ...c, status: memberStatus(c.status) })) : [];
    },
    async addMember(workspaceId, add) {
      const data = await json<{ member: Record<string, unknown>; sign_in_email_sent?: boolean }>(
        await fetcher(ws(workspaceId), post(addMemberBody(add))),
        'Failed to add the member'
      );
      return { member: data.member, emailSent: data.sign_in_email_sent === true };
    },
    async createInWorkspace(workspaceId, create) {
      const data = await json<unknown>(
        await fetcher(`${ws(workspaceId)}/invite`, post(workspaceCreateBody(create))),
        'Failed to create the user'
      );
      return created(data, 'Failed to create the user');
    },
    async createInOrganization(organizationId, create) {
      const data = await json<unknown>(
        await fetcher(`${org(organizationId)}/invite`, post(organizationCreateBody(create))),
        'Failed to create the user'
      );
      return created(data, 'Failed to create the user');
    },
    async resendWorkspace(workspaceId, userId) {
      const data = await json<{ sign_in_email_sent?: boolean }>(
        await fetcher(`${ws(workspaceId)}/${encodeURIComponent(userId)}/resend`, post()),
        'Failed to resend the sign-in email'
      );
      return data.sign_in_email_sent === true;
    },
    async resendOrganization(organizationId, userId) {
      const data = await json<{ sign_in_email_sent?: boolean }>(
        await fetcher(`${org(organizationId)}/${encodeURIComponent(userId)}/resend`, post()),
        'Failed to resend the sign-in email'
      );
      return data.sign_in_email_sent === true;
    },
  };
}
