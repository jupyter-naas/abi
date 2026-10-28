/**
 * The people of a scope, for People & roles and the group member picker: a workspace's
 * members (with those whose role comes from the organization), an organization's members.
 * The platform has no member list: its holders are the attachments themselves.
 */
import { authFetch } from '@/stores/auth';
import type { AccessScope } from './access-scope';
import { BUILT_IN_ROLES, type BuiltInRole } from './roles/role-change';

export type ScopeMember = {
  userId: string;
  name: string;
  email: string;
  role: BuiltInRole | null;
  /** The role is the organization's (an org owner or admin): read-only here. */
  inherited: boolean;
};

export type AccessDirectory = {
  members: (scope: AccessScope) => Promise<ScopeMember[]>;
};

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

function asRole(value: unknown): BuiltInRole | null {
  return typeof value === 'string' && (BUILT_IN_ROLES as string[]).includes(value) ? (value as BuiltInRole) : null;
}

export function toMembers(rows: unknown): ScopeMember[] {
  if (!Array.isArray(rows)) return [];
  return rows.flatMap((row: Record<string, unknown>) => {
    const userId = typeof row?.user_id === 'string' ? row.user_id : null;
    if (!userId) return [];
    return [
      {
        userId,
        name: typeof row.name === 'string' && row.name ? row.name : '',
        email: typeof row.email === 'string' ? row.email : '',
        role: asRole(row.role),
        inherited: row.source === 'organization',
      },
    ];
  });
}

/** The directory read from the Nexus member routes. */
export function createAccessDirectory(fetcher: Fetcher = authFetch): AccessDirectory {
  return {
    members: async (scope) => {
      let url: string | null = null;
      if (scope.level === 'workspace' && scope.workspaceId) {
        url = `/api/workspaces/${encodeURIComponent(scope.workspaceId)}/members`;
      } else if (scope.level === 'organization' && scope.organizationId) {
        url = `/api/organizations/${encodeURIComponent(scope.organizationId)}/members`;
      }
      if (!url) return [];
      const response = await fetcher(url);
      if (!response.ok) throw new Error(`Could not load the members (HTTP ${response.status}).`);
      return toMembers(await response.json());
    },
  };
}

/** A directory with nobody in it: the platform's, and tests that need none. */
export const EMPTY_DIRECTORY: AccessDirectory = { members: () => Promise.resolve([]) };
