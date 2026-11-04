// Invitations through the engine's identity providers, and the IdP groups bound
// to roles: the shapes the API answers, and what the UI says about them.

export type InviteProvider = {
  name: string;
  display_name: string;
  provisioning: 'builtin' | 'zitadel' | 'keycloak' | 'none' | string;
  // The provider's people are managed in the provider itself, never from here.
  managed_in_provider: boolean;
};

export type InviteProviders = {
  // False: no identity provider is configured and invitations create the
  // account in Nexus, as they always did.
  enabled: boolean;
  default_provider: string | null;
  providers: InviteProvider[];
};

export type Invitation = {
  id: string;
  email: string;
  provider: string;
  organization_id: string | null;
  org_role: string | null;
  workspace_id: string | null;
  workspace_role: string | null;
  invited_by: string | null;
  status: string;
  created_at: string | null;
};

export type GroupBinding = { provider: string; group: string; role: string };

export type GroupBindings = {
  providers: InviteProvider[];
  bindings: GroupBinding[];
  roles: string[];
};

export type InviteScope = 'organizations' | 'workspaces';

export const NO_PROVIDERS: InviteProviders = {
  enabled: false,
  default_provider: null,
  providers: [],
};

export type InviteAnswer =
  | {
      kind: 'invited';
      invitation: Invitation;
      provider: InviteProvider;
      userCreated: boolean;
      emailSent: boolean;
      renewed: boolean;
      // What the provider could not do for them (its own mail), if anything.
      warning: string | null;
    }
  | { kind: 'member' };

/**
 * What an invite route answered. Someone with no account is invited (an
 * `invitation` and the provider); anyone else is added as a member, in the
 * route's older shapes, which also say `status: "invited"` for workspaces.
 */
export function classifyInviteAnswer(data: unknown): InviteAnswer {
  const answer = (data ?? {}) as Record<string, unknown>;
  const invitation = answer.invitation as Invitation | undefined;
  const provider = answer.provider as InviteProvider | undefined;
  if (invitation && typeof invitation === 'object' && provider && typeof provider === 'object') {
    return {
      kind: 'invited',
      invitation,
      provider,
      userCreated: answer.user_created === true,
      emailSent: answer.sign_in_email_sent === true,
      renewed: answer.renewed === true,
      warning: typeof answer.provisioning_warning === 'string' ? answer.provisioning_warning : null,
    };
  }
  return { kind: 'member' };
}

/** The provider an invitation goes through when none is picked: the default, else the first. */
export function defaultInviteProvider(known: InviteProviders): string | undefined {
  if (!known.enabled || known.providers.length === 0) return undefined;
  const preferred = known.providers.find((p) => p.name === known.default_provider);
  return (preferred ?? known.providers[0]).name;
}

/** The `provider` an invite request names: only when there is a choice to make. */
export function providerToSend(known: InviteProviders, picked: string | undefined): string | undefined {
  if (!known.enabled || known.providers.length < 2) return undefined;
  return known.providers.some((p) => p.name === picked) ? picked : defaultInviteProvider(known);
}

/** What the invite dialog tells the admin about the provider before they send. */
export function providerHint(provider: InviteProvider | undefined): string | null {
  if (!provider) return null;
  if (provider.managed_in_provider) {
    return (
      `People of ${provider.display_name} are managed in the identity provider. ` +
      'The invitation grants access once they sign in with this email; if they have no account ' +
      `there yet, it must be created in ${provider.display_name}.`
    );
  }
  return `${provider.display_name} creates the account if needed; they sign in with an emailed code.`;
}

/** The success message after an invitation for someone with no account. */
export function inviteSuccessMessage(answer: Extract<InviteAnswer, { kind: 'invited' }>): string {
  const { invitation, provider } = answer;
  const verb = answer.renewed ? 'Invitation renewed for' : 'Invitation sent to';
  const lead = `${verb} ${invitation.email}.`;
  const sentence = answer.emailSent
    ? ` They were emailed, and sign in with ${provider.display_name} using this email.`
    : ` No email could be sent: tell them to sign in with ${provider.display_name} using this email.`;
  const warning = answer.warning ? ` Warning: ${answer.warning}.` : '';
  if (provider.managed_in_provider) {
    return (
      `${lead} Access is granted once they sign in with this email.` +
      ` People of ${provider.display_name} are managed in the identity provider: ` +
      `their account must exist there.${answer.emailSent ? ' They were emailed.' : ''}` +
      warning
    );
  }
  return lead + sentence + warning;
}

/** The roles an invitation carries, for a list: "Org admin · Workspace member". */
export function invitationRoles(invitation: Invitation): string {
  const roles: string[] = [];
  if (invitation.org_role) roles.push(`Organization ${invitation.org_role}`);
  if (invitation.workspace_role) roles.push(`Workspace ${invitation.workspace_role}`);
  return roles.join(' · ') || '—';
}

// -- the policies an invitation carries ---------------------------------------------

/**
 * The policies an invite offers: the customer ones the inviter may attach at its scope, never
 * a managed `builtin.*` one (the role is picked on its own, and comes with what it needs).
 */
export function invitablePolicies<T extends { id: string; managed?: boolean }>(items: T[]): T[] {
  return items.filter((policy) => !policy.managed && !policy.id.startsWith('builtin.'));
}

/** The `policy_ids` an invite request names: only when some are picked. */
export function policyIdsToSend(ids: readonly string[] | undefined): { policy_ids?: string[] } {
  return ids && ids.length ? { policy_ids: [...ids] } : {};
}

/** `POST /api/workspaces/{ws}/members/invite`'s body; the policies attach at that workspace. */
export function workspaceInviteBody(invite: {
  email: string;
  role: string;
  provider?: string;
  policyIds?: readonly string[];
}): Record<string, unknown> {
  return {
    email: invite.email,
    role: invite.role,
    provider: invite.provider,
    ...policyIdsToSend(invite.policyIds),
  };
}

// -- API ----------------------------------------------------------------------------

async function api(url: string, options: RequestInit = {}): Promise<Response> {
  const { authFetch } = await import('@/stores/auth');
  return authFetch(url, options);
}

export async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || String(d)).join(', ');
    }
  } catch {
    // ignore parse errors
  }
  return fallback;
}

async function json<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) throw new Error(await readApiError(response, fallback));
  return (await response.json()) as T;
}

/** The providers an invitation can go through; "none" when they cannot be read. */
export async function fetchInviteProviders(): Promise<InviteProviders> {
  try {
    const response = await api('/api/invitations/providers');
    if (!response.ok) return NO_PROVIDERS;
    const data = (await response.json()) as Partial<InviteProviders>;
    return {
      enabled: data.enabled === true,
      default_provider: data.default_provider ?? null,
      providers: Array.isArray(data.providers) ? data.providers : [],
    };
  } catch {
    return NO_PROVIDERS;
  }
}

export async function fetchInvitations(scope: InviteScope, id: string): Promise<Invitation[]> {
  const data = await json<{ invitations: Invitation[] }>(
    await api(`/api/invitations/${scope}/${encodeURIComponent(id)}`),
    'Failed to load invitations'
  );
  return data.invitations ?? [];
}

export async function resendInvitation(id: string): Promise<{ sign_in_email_sent: boolean }> {
  return json(
    await api(`/api/invitations/${encodeURIComponent(id)}/resend`, { method: 'POST' }),
    'Failed to resend the invitation'
  );
}

export async function revokeInvitation(id: string): Promise<void> {
  await json(
    await api(`/api/invitations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    'Failed to revoke the invitation'
  );
}

export async function fetchGroupBindings(scope: InviteScope, id: string): Promise<GroupBindings> {
  return json(
    await api(`/api/idp-groups/${scope}/${encodeURIComponent(id)}`),
    'Failed to load identity provider groups'
  );
}

export async function bindGroup(
  scope: InviteScope,
  id: string,
  binding: GroupBinding
): Promise<GroupBindings> {
  return json(
    await api(`/api/idp-groups/${scope}/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(binding),
    }),
    'Failed to bind the group'
  );
}

export async function unbindGroup(
  scope: InviteScope,
  id: string,
  binding: GroupBinding
): Promise<GroupBindings> {
  const query = new URLSearchParams({
    provider: binding.provider,
    group: binding.group,
    role: binding.role,
  });
  return json(
    await api(`/api/idp-groups/${scope}/${encodeURIComponent(id)}?${query}`, { method: 'DELETE' }),
    'Failed to unbind the group'
  );
}
