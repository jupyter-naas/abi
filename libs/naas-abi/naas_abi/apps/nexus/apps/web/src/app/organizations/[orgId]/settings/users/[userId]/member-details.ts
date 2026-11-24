import { type Level } from '@/lib/people';

/** One member, as `GET /api/organizations/{org}/members/{user}` returns it. */
export interface MemberAccount {
  user_id: string;
  email: string | null;
  name: string | null;
  avatar: string | null;
  organization: string | null;
  job_title: string | null;
  bio: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Editable org fields. No name: the full name is always the account's (users.name). */
export type MemberProfileField =
  | 'organization'
  | 'job_title'
  | 'service_line'
  | 'country'
  | 'interest'
  | 'bio';

/** What this organization set. Bio shows the account value when empty. */
export type MemberOrganizationProfile = Record<MemberProfileField, string | null> & {
  avatar: string | null;
};

export interface MemberWorkspace {
  id: string;
  name: string;
  slug: string;
  role: string;
  /** "workspace": they joined it; "organization": they reach it as an org admin. */
  source: 'workspace' | 'organization';
  /** They administer it ("<W> admins"). */
  admin?: boolean;
}

/** A capability group they are in. */
export interface MemberCapability {
  id: string;
  name: string;
  owner_scope: string;
}

export interface MemberDetails {
  member: {
    id: string;
    organization_id: string;
    user_id: string;
    /** Their IAM principal: an account linked from the old login has another id in IAM. */
    principal_id?: string | null;
    /** "admin" for an org admin, else their level at the organization; null: through a workspace only. */
    role: 'admin' | 'member' | 'viewer' | null;
    /** An admin of the organization. */
    org_admin?: boolean;
    /** Their level, in all their workspaces. */
    level?: Level | null;
    /** Where they are linked to the organization from (an older answer has none: an org role). */
    source?: 'organization' | 'workspace';
    /** Invited: created, has not signed in yet. */
    status?: 'active' | 'invited';
    email: string | null;
    name: string | null;
    created_at: string | null;
  };
  account: MemberAccount;
  organization_profile: MemberOrganizationProfile;
  workspaces: MemberWorkspace[];
  capabilities?: MemberCapability[];
}

export const PROFILE_FIELDS: MemberProfileField[] = [
  'organization',
  'job_title',
  'service_line',
  'country',
  'interest',
  'bio',
];

/**
 * The org profile fields to save: only those the admin changed, trimmed. A field
 * left empty that was never set stays unset, so it keeps showing the account value.
 */
export function changedProfileFields(
  saved: MemberOrganizationProfile,
  draft: Record<MemberProfileField, string>
): Partial<Record<MemberProfileField, string>> {
  const changes: Partial<Record<MemberProfileField, string>> = {};
  for (const field of PROFILE_FIELDS) {
    const next = draft[field].trim();
    if (next !== (saved[field] ?? '').trim()) changes[field] = next;
  }
  return changes;
}

/**
 * Save a member's changes as two steps said apart: the profile, then their access. A refused
 * access change never hides a saved profile; after an access change the members list is
 * refreshed (``refreshed``). Returns null when everything was saved, else what was not, with
 * the reason (the API's, e.g. the last org admin's 409).
 */
export async function saveMemberChanges({
  profile,
  access,
  refreshed,
}: {
  profile: (() => Promise<unknown>) | null;
  access: (() => Promise<unknown>) | null;
  refreshed: () => Promise<unknown>;
}): Promise<string | null> {
  const reason = (err: unknown, fallback: string) => (err instanceof Error && err.message ? err.message : fallback);
  if (profile) {
    try {
      await profile();
    } catch (err) {
      return `The profile was not saved: ${reason(err, 'Failed to save')}`;
    }
  }
  if (access) {
    try {
      await access();
    } catch (err) {
      const what = profile ? 'The profile was saved, but their access was not changed' : 'Their access was not changed';
      return `${what}: ${reason(err, 'Failed to change it')}`;
    }
    await refreshed();
  }
  return null;
}

