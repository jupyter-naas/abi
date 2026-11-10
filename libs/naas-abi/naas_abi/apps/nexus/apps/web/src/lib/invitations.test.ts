import { describe, expect, it } from 'vitest';
import {
  classifyInviteAnswer,
  defaultInviteProvider,
  inviteSuccessMessage,
  invitablePolicies,
  invitationRoles,
  policyIdsToSend,
  providerHint,
  providerToSend,
  workspaceInviteBody,
  type Invitation,
  type InviteProvider,
  type InviteProviders,
} from './invitations';

const builtin: InviteProvider = {
  name: 'builtin',
  display_name: 'Built-in',
  provisioning: 'builtin',
  managed_in_provider: false,
};
const okta: InviteProvider = {
  name: 'okta',
  display_name: 'Okta',
  provisioning: 'none',
  managed_in_provider: true,
};
const invitation: Invitation = {
  id: 'i1',
  email: 'bob@example.com',
  provider: 'builtin',
  organization_id: 'o1',
  org_role: 'member',
  workspace_id: 'w1',
  workspace_role: 'viewer',
  invited_by: 'u1',
  status: 'pending',
  created_at: '2026-10-19T10:00:00',
};

describe('classifyInviteAnswer', () => {
  it('knows an invitation by its invitation and provider', () => {
    const answer = classifyInviteAnswer({
      status: 'invited',
      invitation,
      provider: builtin,
      user_created: true,
      sign_in_email_sent: true,
      renewed: false,
    });
    expect(answer).toMatchObject({ kind: 'invited', userCreated: true, emailSent: true, renewed: false });
  });

  it('takes the older shapes, including a workspace status "invited", for a member', () => {
    expect(classifyInviteAnswer({ status: 'invited', member_id: 'm1' })).toEqual({ kind: 'member' });
    expect(classifyInviteAnswer({ id: 'm', user_id: 'u', role: 'member' })).toEqual({ kind: 'member' });
    expect(classifyInviteAnswer(null)).toEqual({ kind: 'member' });
  });
});

describe('inviteSuccessMessage', () => {
  const invited = (provider: InviteProvider, emailSent: boolean, renewed = false, warning: string | null = null) =>
    classifyInviteAnswer({
      invitation,
      provider,
      sign_in_email_sent: emailSent,
      user_created: false,
      renewed,
      provisioning_warning: warning,
    }) as Extract<ReturnType<typeof classifyInviteAnswer>, { kind: 'invited' }>;

  it('says who signs in where, and that they were emailed', () => {
    const message = inviteSuccessMessage(invited(builtin, true));
    expect(message).toContain('Invitation sent to bob@example.com');
    expect(message).toContain('sign in with Built-in');
    expect(message).toContain('emailed');
  });

  it('does not claim an email that was not sent', () => {
    const message = inviteSuccessMessage(invited(builtin, false));
    expect(message).toContain('No email could be sent');
    expect(message).not.toContain('They were emailed');
  });

  it('explains a provider that manages its own people', () => {
    const message = inviteSuccessMessage(invited(okta, false));
    expect(message).toContain('managed in the identity provider');
    expect(message).toContain('must exist there');
    expect(message).not.toContain('emailed');
  });

  it('shows what the provider could not do for the invitee', () => {
    const message = inviteSuccessMessage(invited(builtin, true, false, 'Keycloak could not send the verification email'));
    expect(message).toContain('Warning: Keycloak could not send the verification email.');
    expect(inviteSuccessMessage(invited(builtin, true))).not.toContain('Warning');
  });

  it('says renewed for an invitation made again', () => {
    expect(inviteSuccessMessage(invited(builtin, true, true))).toContain('Invitation renewed for');
  });
});

describe('providers', () => {
  const two: InviteProviders = { enabled: true, default_provider: 'okta', providers: [builtin, okta] };

  it('defaults to the default provider, else the first', () => {
    expect(defaultInviteProvider(two)).toBe('okta');
    expect(defaultInviteProvider({ ...two, default_provider: null })).toBe('builtin');
    expect(defaultInviteProvider({ enabled: false, default_provider: null, providers: [] })).toBeUndefined();
  });

  it('names a provider only when there is a choice', () => {
    expect(providerToSend(two, 'builtin')).toBe('builtin');
    expect(providerToSend(two, 'gone')).toBe('okta');
    expect(providerToSend({ ...two, providers: [builtin] }, 'builtin')).toBeUndefined();
    expect(providerToSend({ ...two, enabled: false }, 'builtin')).toBeUndefined();
  });

  it('hints what the chosen provider means', () => {
    expect(providerHint(okta)).toContain('managed in the identity provider');
    expect(providerHint(builtin)).toContain('creates the account');
    expect(providerHint(undefined)).toBeNull();
  });
});

describe('invitationRoles', () => {
  it('lists both roles', () => {
    expect(invitationRoles(invitation)).toBe('Organization member · Workspace viewer');
    expect(invitationRoles({ ...invitation, org_role: null, workspace_role: null })).toBe('—');
  });
});

describe('the policies an invitation carries', () => {
  it('offers customer policies only, never a managed built-in one', () => {
    const items = [
      { id: 'builtin.member', name: 'Member', managed: true },
      { id: 'builtin.platform.member', name: 'Platform member', managed: true },
      { id: 'pol_features', name: 'Features of member', managed: false },
      { id: 'pol_graph', name: 'Graph readers', managed: false },
    ];
    expect(invitablePolicies(items).map((p) => p.id)).toEqual(['pol_features', 'pol_graph']);
  });

  it('names policy_ids only when some are picked', () => {
    expect(policyIdsToSend([])).toEqual({});
    expect(policyIdsToSend(undefined)).toEqual({});
    expect(policyIdsToSend(['pol_1', 'pol_2'])).toEqual({ policy_ids: ['pol_1', 'pol_2'] });
  });

  it('sends the picked policies with a workspace invitation', () => {
    expect(workspaceInviteBody({ email: 'bob@example.com', role: 'member', policyIds: ['pol_1'] })).toEqual({
      email: 'bob@example.com',
      role: 'member',
      provider: undefined,
      policy_ids: ['pol_1'],
    });
    expect(workspaceInviteBody({ email: 'bob@example.com', role: 'viewer', provider: 'okta' })).toEqual({
      email: 'bob@example.com',
      role: 'viewer',
      provider: 'okta',
    });
  });
});
