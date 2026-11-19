// Create user: the pure part of the form Organization settings › Users › New and Workspace
// settings › Members › New share. Which organization it creates in (fixed or picked), which
// workspaces it attaches, the org roles it offers, and the one request it sends.

import {
  filledProfile,
  looksLikeEmail,
  type OrganizationCreate,
  type OrganizationRole,
  type PeopleProfile,
  type WorkspaceCreate,
  type WorkspaceRole,
} from '@/lib/people';

export type OrgChoice = { id: string; name: string };
export type WorkspaceChoice = { id: string; name: string };

/** The organization: fixed (shown read-only), or picked among `choices`. */
export type OrganizationProp = { fixed: OrgChoice } | { choices: OrgChoice[]; initialId?: string };

/** "None (workspace access only)" in the org role field. */
export const NO_ORG_ROLE = 'none';
export type OrgRoleValue = OrganizationRole | typeof NO_ORG_ROLE;

export const ORG_ROLE_LABELS: Record<OrgRoleValue, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  none: 'None (workspace access only)',
};

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
  /** Ignored when the form offers no org role (the workspace page). */
  orgRole: OrgRoleValue;
  /** The workspaces picked, with the role there (the attached one is added by the form). */
  workspaces: { id: string; role: WorkspaceRole }[];
  /** The role at the attached workspace (the workspace page). */
  attachedRole: WorkspaceRole;
  policyIds: string[];
  provider?: string;
  profile: Partial<Record<keyof PeopleProfile, string>>;
};

export type CreateUserConfig = {
  organization: OrganizationProp;
  /** The organization picked when it is selectable. */
  organizationId: string | null;
  /** The workspace the person is attached to, not removable (the workspace page). */
  attachedWorkspace?: WorkspaceChoice;
  /** The org roles offered; none: the form asks for no org role and grants none. */
  orgRoles: OrganizationRole[];
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

/** The workspaces the person gets: the attached one first, then those picked. */
export function workspaceGrants(
  draft: Pick<CreateUserDraft, 'workspaces' | 'attachedRole'>,
  attached?: WorkspaceChoice
): { id: string; role: WorkspaceRole }[] {
  const picked = draft.workspaces.filter((w) => w.id !== attached?.id);
  return attached ? [{ id: attached.id, role: draft.attachedRole }, ...picked] : picked;
}

/**
 * The org roles the field offers: those allowed, then "None (workspace access only)" once at
 * least one workspace is picked. Empty when the form asks for no org role.
 */
export function orgRoleOptions(orgRoles: OrganizationRole[], workspaceCount: number): OrgRoleValue[] {
  if (orgRoles.length === 0) return [];
  return workspaceCount > 0 ? [...orgRoles, NO_ORG_ROLE] : [...orgRoles];
}

/** The org role the draft really has: "None" falls back to the first role once no workspace is left. */
export function effectiveOrgRole(value: OrgRoleValue, orgRoles: OrganizationRole[], workspaceCount: number): OrgRoleValue {
  const offered = orgRoleOptions(orgRoles, workspaceCount);
  if (offered.includes(value)) return value;
  return offered.includes('member') ? 'member' : (offered[0] ?? NO_ORG_ROLE);
}

export type CreateUserRequest =
  | { route: 'workspace'; workspaceId: string; body: WorkspaceCreate }
  | { route: 'organization'; organizationId: string; body: OrganizationCreate };

/**
 * The one request the form sends, or why it cannot be sent. With no org role offered and a
 * workspace attached, it creates into that workspace (no org role is granted); else into the
 * organization with an org role (or none) and every workspace picked.
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

  if (config.orgRoles.length === 0) {
    if (!config.attachedWorkspace) return { ok: false, error: 'No workspace to add them to.' };
    return {
      ok: true,
      request: {
        route: 'workspace',
        workspaceId: config.attachedWorkspace.id,
        body: { email, name, role: draft.attachedRole, policyIds: draft.policyIds, provider, profile },
      },
    };
  }

  const organization = selectedOrganization(config.organization, config.organizationId);
  if (!organization) return { ok: false, error: 'Pick an organization.' };
  const workspaces = workspaceGrants(draft, config.attachedWorkspace);
  const role = effectiveOrgRole(draft.orgRole, config.orgRoles, workspaces.length);
  if (role === NO_ORG_ROLE && workspaces.length === 0) {
    return { ok: false, error: 'Pick an organization role, or at least one workspace.' };
  }
  return {
    ok: true,
    request: {
      route: 'organization',
      organizationId: organization.id,
      body: {
        email,
        name,
        role: role === NO_ORG_ROLE ? null : role,
        workspaces,
        policyIds: draft.policyIds,
        provider,
        profile,
      },
    },
  };
}
