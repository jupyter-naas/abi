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
  /** "workspace": explicit membership or ownership; "organization": inherited from the org role. */
  source: 'workspace' | 'organization';
}

export interface MemberDetails {
  member: {
    id: string;
    organization_id: string;
    user_id: string;
    role: 'owner' | 'admin' | 'member';
    email: string | null;
    name: string | null;
    created_at: string | null;
  };
  account: MemberAccount;
  organization_profile: MemberOrganizationProfile;
  workspaces: MemberWorkspace[];
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
 * Save a member's changes as two steps said apart: the profile, then the role. A refused role
 * never hides a saved profile; after a role change the members list is refreshed (``refreshed``).
 * Returns null when everything was saved, else what was not, with the reason.
 */
export async function saveMemberChanges({
  profile,
  role,
  refreshed,
}: {
  profile: (() => Promise<unknown>) | null;
  role: (() => Promise<unknown>) | null;
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
  if (role) {
    try {
      await role();
    } catch (err) {
      const what = profile ? 'The profile was saved, but the role was not changed' : 'The role was not changed';
      return `${what}: ${reason(err, 'Failed to change the role')}`;
    }
    await refreshed();
  }
  return null;
}
