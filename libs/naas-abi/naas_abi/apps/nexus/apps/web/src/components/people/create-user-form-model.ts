// Create user: the pure part of the form Organization settings › Users › New and Workspace
// settings › Members › New share. Which organization it creates in (fixed or picked), the
// person's level, whether they administer the organization, which workspaces they join (each
// with "admin"), the capability groups they are put in, and the one request it sends (#1589).

import {
  filledProfile,
  levelConflict,
  looksLikeEmail,
  type Level,
  type OrganizationCreate,
  type PeopleProfile,
  type WorkspaceAccess,
  type WorkspaceCreate,
} from '@/lib/people';

export type OrgChoice = { id: string; name: string };
export type WorkspaceChoice = { id: string; name: string };

/** The organization: fixed (shown read-only), or picked among `choices`. */
export type OrganizationProp = { fixed: OrgChoice } | { choices: OrgChoice[]; initialId?: string };

export const PROFILE_FIELDS: { field: keyof PeopleProfile; label: string }[] = [
  { field: 'organization', label: 'Organization' },
  { field: 'job_title', label: 'Job title' },
  { field: 'service_line', label: 'Service line' },
  { field: 'country', label: 'Country' },
  { field: 'interest', label: 'Interest' },
];

export type CreateUserDraft = {
  email: string;
  name: string;
  /** Their level, in all their workspaces. */
  level: Level;
  /** An admin of the organization (the organization page). */
  orgAdmin: boolean;
  /** The workspaces picked, each with "admin" (the attached one is added by the form). */
  workspaces: WorkspaceAccess[];
  /** Whether they administer the attached workspace (the workspace page). */
  attachedAdmin: boolean;
  /** The capability groups they are put in. */
  capabilities: string[];
  provider?: string;
  profile: Partial<Record<keyof PeopleProfile, string>>;
};

export type CreateUserConfig = {
  organization: OrganizationProp;
  /** The organization picked when it is selectable. */
  organizationId: string | null;
  /** The workspace the person joins, not removable (the workspace page). */
  attachedWorkspace?: WorkspaceChoice;
  /** The organization page: the org admin toggle and the organization's workspaces to pick. */
  organizationRoute: boolean;
};

/** The organization the form creates in: the fixed one, else the one picked. */
export function selectedOrganization(organization: OrganizationProp, pickedId: string | null): OrgChoice | null {
  if ('fixed' in organization) return organization.fixed;
  return organization.choices.find((o) => o.id === pickedId) ?? null;
}

/** The organization picked first: the initial one when it is a choice, else the first. */
export function initialOrganizationId(organization: OrganizationProp): string | null {
  if ('fixed' in organization) return organization.fixed.id;
  const initial = organization.choices.find((o) => o.id === organization.initialId);
  return (initial ?? organization.choices[0])?.id ?? null;
}

/** Whether the organization is shown read-only (fixed) or picked from a list. */
export function organizationReadOnly(organization: OrganizationProp): boolean {
  return 'fixed' in organization;
}

/** The workspaces the person joins: the attached one first, then those picked. */
export function workspaceGrants(
  draft: Pick<CreateUserDraft, 'workspaces' | 'attachedAdmin'>,
  attached?: WorkspaceChoice
): WorkspaceAccess[] {
  const picked = draft.workspaces.filter((w) => w.id !== attached?.id);
  return attached ? [{ id: attached.id, admin: draft.attachedAdmin }, ...picked] : picked;
}

export type CreateUserRequest =
  | { route: 'workspace'; workspaceId: string; body: WorkspaceCreate }
  | { route: 'organization'; organizationId: string; body: OrganizationCreate };

/**
 * The one request the form sends, or why it cannot be sent. From a workspace it joins that
 * workspace; from the organization it names the org admin toggle and every workspace picked
 * (none and no org admin: they are one of the organization's people).
 */
export function createUserRequest(
  draft: CreateUserDraft,
  config: CreateUserConfig
): { ok: true; request: CreateUserRequest } | { ok: false; error: string } {
  const email = draft.email.trim();
  if (!looksLikeEmail(email)) return { ok: false, error: 'Enter a valid email address.' };
  const name = draft.name.trim() || undefined;
  const profile = filledProfile(draft.profile);
  const provider = draft.provider || undefined;
  const capabilities = [...draft.capabilities];

  if (!config.organizationRoute) {
    if (!config.attachedWorkspace) return { ok: false, error: 'No workspace to add them to.' };
    const conflict = levelConflict(draft.level, draft.attachedAdmin);
    if (conflict) return { ok: false, error: conflict };
    return {
      ok: true,
      request: {
        route: 'workspace',
        workspaceId: config.attachedWorkspace.id,
        body: { email, name, level: draft.level, admin: draft.attachedAdmin, capabilities, provider, profile },
      },
    };
  }

  const organization = selectedOrganization(config.organization, config.organizationId);
  if (!organization) return { ok: false, error: 'Pick an organization.' };
  const workspaces = workspaceGrants(draft, config.attachedWorkspace);
  const conflict = levelConflict(
    draft.level,
    workspaces.some((w) => w.admin)
  );
  if (conflict) return { ok: false, error: conflict };
  return {
    ok: true,
    request: {
      route: 'organization',
      organizationId: organization.id,
      body: {
        email,
        name,
        level: draft.level,
        orgAdmin: draft.orgAdmin,
        workspaces,
        capabilities,
        provider,
        profile,
      },
    },
  };
}
