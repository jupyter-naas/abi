import { describe, expect, it, vi } from 'vitest';
import {
  CANDIDATE_LIMIT,
  LEVELS,
  LEVEL_EVERYWHERE_NOTE,
  LEVEL_LABELS,
  addMemberBody,
  capabilityGroupsUrl,
  levelConflict,
  offeredCapabilityGroups,
  readLevel,
  addedNotice,
  candidateLabel,
  candidateQuery,
  candidatesUrl,
  createPeopleApi,
  createUserHref,
  createUserPrefill,
  createdMessage,
  filledProfile,
  memberStatus,
  membersAddedHref,
  organizationCreateBody,
  readCreatedPerson,
  resentMessage,
  statusBadge,
  workspaceCreateBody,
} from './people';

const params = (query: string) => new URLSearchParams(query);

describe('the search text', () => {
  it('asks from two characters on, trimmed', () => {
    expect(candidateQuery('')).toBeNull();
    expect(candidateQuery(' F ')).toBeNull();
    expect(candidateQuery('Fl')).toBe('Fl');
    expect(candidateQuery('  Flo ')).toBe('Flo');
  });

  it('asks the candidates route with q and a limit of at most 20', () => {
    expect(candidatesUrl('ws 1', 'Flo')).toBe(`/api/workspaces/ws%201/members/candidates?q=Flo&limit=${CANDIDATE_LIMIT}`);
    expect(candidatesUrl('ws', 'a@b.c', 50)).toBe('/api/workspaces/ws/members/candidates?q=a%40b.c&limit=20');
  });

  it('names a suggestion by its name, else its email', () => {
    expect(candidateLabel({ name: 'Florent', email: 'florent@naas.ai' })).toBe('Florent');
    expect(candidateLabel({ name: ' ', email: 'florent@naas.ai' })).toBe('florent@naas.ai');
    expect(candidateLabel({ name: null, email: 'florent@naas.ai' })).toBe('florent@naas.ai');
  });
});

describe('the create page link', () => {
  it('prefills an email as the email, anything else as the name', () => {
    expect(createUserHref('ws-1', 'bob@example.com')).toBe(
      '/workspace/ws-1/settings/users/new?email=bob%40example.com'
    );
    expect(createUserHref('ws-1', ' Bob Martin ')).toBe('/workspace/ws-1/settings/users/new?name=Bob+Martin');
    expect(createUserHref('ws-1', '')).toBe('/workspace/ws-1/settings/users/new');
  });

  it('reads the prefill back', () => {
    expect(createUserPrefill(params('email=bob%40example.com'))).toEqual({ email: 'bob@example.com', name: '' });
    expect(createUserPrefill(params('name=Bob'))).toEqual({ email: '', name: 'Bob' });
    expect(createUserPrefill(params(''))).toEqual({ email: '', name: '' });
  });
});

describe('the status', () => {
  it('is invited only when the API says so', () => {
    expect(memberStatus('invited')).toBe('invited');
    expect(memberStatus('active')).toBe('active');
    expect(memberStatus(undefined)).toBe('active');
  });

  it('shows an Invited badge for invited people only', () => {
    expect(statusBadge('invited')?.label).toBe('Invited');
    expect(statusBadge('active')).toBeNull();
    expect(statusBadge(undefined)).toBeNull();
  });

  it('says what Resend did', () => {
    expect(resentMessage('bob@example.com', true)).toBe('Sign-in email sent again to bob@example.com.');
    expect(resentMessage('bob@example.com', false)).toBe('No email could be sent to bob@example.com.');
  });
});

describe('the request bodies', () => {
  it('adds a suggestion by its user id, with the level, the admin toggle and the groups picked', () => {
    expect(addMemberBody({ userId: 'usr_flo' })).toEqual({ user_id: 'usr_flo', admin: false });
    expect(addMemberBody({ userId: 'usr_flo', level: 'viewer', admin: false, capabilities: [] })).toEqual({
      user_id: 'usr_flo',
      admin: false,
      level: 'viewer',
    });
    expect(addMemberBody({ userId: 'usr_flo', level: 'member', admin: true, capabilities: ['grp_runners'] })).toEqual({
      user_id: 'usr_flo',
      admin: true,
      level: 'member',
      capabilities: ['grp_runners'],
    });
  });

  it('never sends a role, policies or an owner', () => {
    const bodies = [
      addMemberBody({ userId: 'usr_flo', level: 'member', admin: true }),
      workspaceCreateBody({ email: 'bob@example.com', level: 'member', admin: true }),
      organizationCreateBody({ email: 'bob@example.com', orgAdmin: true, workspaces: [{ id: 'ws-1', admin: true }] }),
    ];
    for (const body of bodies) {
      expect(body).not.toHaveProperty('role');
      expect(body).not.toHaveProperty('policy_ids');
      expect(JSON.stringify(body)).not.toContain('owner');
    }
  });

  it('keeps only the profile fields filled in', () => {
    expect(filledProfile({ organization: ' Acme ', job_title: '', country: '  ' })).toEqual({ organization: 'Acme' });
    expect(filledProfile({ job_title: '' })).toBeUndefined();
  });

  it('creates into a workspace with the profile nested, the level kept when none is picked', () => {
    const body = workspaceCreateBody({
      email: ' bob@example.com ',
      name: 'Bob',
      level: 'member',
      admin: false,
      capabilities: ['grp_runners'],
      provider: 'okta',
      profile: { job_title: 'Analyst' },
    });
    expect(body).toEqual({
      email: 'bob@example.com',
      name: 'Bob',
      level: 'member',
      admin: false,
      capabilities: ['grp_runners'],
      provider: 'okta',
      profile: { job_title: 'Analyst' },
    });
    expect(workspaceCreateBody({ email: 'bob@example.com', level: null })).toEqual({
      email: 'bob@example.com',
      admin: false,
    });
  });

  it('creates into an organization in one request with every workspace and its admin flag, the profile flat', () => {
    expect(
      organizationCreateBody({
        email: 'bob@example.com',
        level: 'member',
        orgAdmin: false,
        workspaces: [
          { id: 'ws-1', admin: true },
          { id: 'ws-2', admin: false },
        ],
        capabilities: ['grp_runners'],
        profile: { country: 'FR' },
      })
    ).toEqual({
      email: 'bob@example.com',
      level: 'member',
      org_admin: false,
      workspaces: [
        { id: 'ws-1', admin: true },
        { id: 'ws-2', admin: false },
      ],
      capabilities: ['grp_runners'],
      country: 'FR',
    });
  });

  it('creates someone of the organization alone (its people), with no workspace', () => {
    expect(organizationCreateBody({ email: 'bob@example.com', workspaces: [] })).toEqual({
      email: 'bob@example.com',
      org_admin: false,
      workspaces: [],
    });
  });
});

describe('the level', () => {
  it('is Member or Viewer, and a note says it applies everywhere', () => {
    expect(LEVELS).toEqual(['member', 'viewer']);
    expect(LEVEL_LABELS).toEqual({ member: 'Member', viewer: 'Viewer' });
    expect(LEVEL_EVERYWHERE_NOTE).toMatch(/all of this person.s workspaces/);
  });

  it('cannot be Viewer for a workspace admin, who is a Member', () => {
    expect(levelConflict('viewer', true)).toMatch(/workspace admin is a Member/);
    expect(levelConflict('member', true)).toBeNull();
    expect(levelConflict('viewer', false)).toBeNull();
    expect(levelConflict(null, true)).toBeNull();
  });

  it('reads a level from an answer, anything else is none', () => {
    expect(readLevel('member')).toBe('member');
    expect(readLevel('viewer')).toBe('viewer');
    expect(readLevel('admin')).toBeNull();
    expect(readLevel(undefined)).toBeNull();
  });
});

describe('the capability groups offered', () => {
  const group = (over: Record<string, unknown>) => ({
    id: 'grp_x',
    name: 'X',
    description: null,
    owner_scope: 'abi:nexus:organization/acme',
    scope: 'organization',
    ...over,
  });

  it("are the groups that add one thing to a level, never the model's own", () => {
    const items = [
      group({ id: 'grp_runners', name: 'Workflow runners' }),
      group({ id: 'grp_pilot', name: 'Pilot seat' }),
      group({ id: 'grp_models', name: 'Models · all', owner_scope: 'abi:', scope: 'platform' }),
      group({ id: 'grp_admins', name: 'Acme admins' }),
      group({ id: 'grp_people', name: 'Acme people' }),
      group({ id: 'grp_members', name: 'Members', owner_scope: 'abi:', scope: 'platform' }),
      group({ id: 'grp_platform', name: 'Platform admins', owner_scope: 'abi', scope: 'platform' }),
      group({ id: 'grp_ws', name: 'Alpha workspace', owner_scope: 'abi:nexus:organization/acme/nexus:workspace/ws-1' }),
    ];
    expect(offeredCapabilityGroups(items).map((g) => g.id)).toEqual(['grp_runners', 'grp_models', 'grp_pilot']);
  });

  it('are asked of the organization, or of the workspace', () => {
    expect(capabilityGroupsUrl({ organizationId: 'org 1' })).toBe('/api/organizations/org%201/capability-groups');
    expect(capabilityGroupsUrl({ workspaceId: 'ws-1' })).toBe('/api/workspaces/ws-1/capability-groups');
  });
});

const ADDED = {
  status: 'added',
  user: { id: 'usr_bob', email: 'bob@example.com', name: 'Bob', status: 'invited' },
  member: { id: 'm1', user_id: 'usr_bob', role: 'member', status: 'invited' },
  provider: { name: 'builtin', display_name: 'Built-in', provisioning: 'builtin', managed_in_provider: false },
  sign_in_email_sent: true,
  warning: null,
};

describe('a create (or link) answer', () => {
  it('is read with its user, member, provider and mail', () => {
    const created = readCreatedPerson(ADDED);
    expect(created).toMatchObject({
      user: { id: 'usr_bob', email: 'bob@example.com', status: 'invited' },
      member: { id: 'm1' },
      emailSent: true,
      warning: null,
    });
    expect(readCreatedPerson({ id: 'm', user_id: 'u' })).toBeNull();
    expect(readCreatedPerson({ ...ADDED, member: null })?.member).toBeNull();
  });

  it('never says whether the account was created or found', () => {
    const message = createdMessage(readCreatedPerson(ADDED)!, 'Research');
    expect(message).toBe('bob@example.com was added to Research. They were emailed a link to sign in with Built-in.');
    expect(message).not.toMatch(/creat|exist|linked|already/i);
    // The same words for a linked account (the API answers the same shape).
    const linked = createdMessage(readCreatedPerson({ ...ADDED, user: { ...ADDED.user, status: 'active' } })!, 'Research');
    expect(linked).toBe(message);
  });

  it('says when no mail went, and what the provider warned', () => {
    const message = createdMessage(
      readCreatedPerson({ ...ADDED, sign_in_email_sent: false, warning: 'Keycloak could not send the verification email' })!,
      'Research'
    );
    expect(message).toContain('No email could be sent');
    expect(message).toContain('Warning: Keycloak could not send the verification email.');
  });

  it('goes back to Members with who was added, worded there', () => {
    const href = membersAddedHref('/workspace/ws-1/settings/users', readCreatedPerson(ADDED)!);
    expect(href).toBe('/workspace/ws-1/settings/users?added=bob%40example.com&mailed=1');
    expect(addedNotice(new URL(href, 'https://x.test').searchParams)).toBe(
      'bob@example.com was added to this workspace. They were emailed a link to sign in.'
    );
    expect(addedNotice(params('added=bob%40example.com&mailed=0'))).toContain('No email could be sent');
    // Never a text from the URL as is.
    expect(addedNotice(params('added=Your+account+is+locked'))).toBeNull();
    expect(addedNotice(params(''))).toBeNull();
  });
});

describe('the people API', () => {
  const answer = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

  it('asks nothing below two characters', async () => {
    const fetcher = vi.fn();
    expect(await createPeopleApi(fetcher).candidates('ws-1', 'F')).toEqual([]);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('lists the candidates the API suggests', async () => {
    const fetcher = vi.fn(async () =>
      answer(200, {
        items: [{ user_id: 'usr_flo', name: 'Florent', email: 'florent@naas.ai', avatar: null, status: 'active', org_role: 'member' }],
      })
    );
    const items = await createPeopleApi(fetcher).candidates('ws-1', 'Flo');
    expect(fetcher).toHaveBeenCalledWith('/api/workspaces/ws-1/members/candidates?q=Flo&limit=10', undefined);
    expect(items.map((c) => c.email)).toEqual(['florent@naas.ai']);
  });

  it('adds, creates and resends on the contract routes', async () => {
    const calls: { url: string; method: string; body: unknown }[] = [];
    const fetcher = vi.fn(async (url: string, options: RequestInit = {}) => {
      calls.push({ url, method: options.method ?? 'GET', body: options.body ? JSON.parse(String(options.body)) : null });
      if (url.endsWith('/resend')) return answer(200, { sign_in_email_sent: true });
      if (url === '/api/workspaces/ws-1/members') return answer(201, { member: { id: 'm' }, sign_in_email_sent: true });
      return answer(200, ADDED);
    });
    const api = createPeopleApi(fetcher);
    expect(await api.addMember('ws-1', { userId: 'usr_flo', level: 'member', admin: false })).toEqual({
      member: { id: 'm' },
      emailSent: true,
    });
    await api.createInWorkspace('ws-1', { email: 'bob@example.com', level: 'member', admin: true });
    await api.createInOrganization('org-1', {
      email: 'bob@example.com',
      workspaces: [{ id: 'ws-1', admin: false }],
    });
    expect(await api.resendWorkspace('ws-1', 'usr_bob')).toBe(true);
    expect(await api.resendOrganization('org-1', 'usr_bob')).toBe(true);
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'POST /api/workspaces/ws-1/members',
      'POST /api/workspaces/ws-1/members/invite',
      'POST /api/organizations/org-1/members/invite',
      'POST /api/workspaces/ws-1/members/usr_bob/resend',
      'POST /api/organizations/org-1/members/usr_bob/resend',
    ]);
    expect(calls[0].body).toEqual({ user_id: 'usr_flo', level: 'member', admin: false });
    expect(calls[2].body).toEqual({ email: 'bob@example.com', org_admin: false, workspaces: [{ id: 'ws-1', admin: false }] });
  });

  it('changes a level or the admin toggle from a workspace, and the access of an organization member', async () => {
    const calls: { url: string; method: string; body: unknown }[] = [];
    const fetcher = vi.fn(async (url: string, options: RequestInit = {}) => {
      calls.push({ url, method: options.method ?? 'GET', body: options.body ? JSON.parse(String(options.body)) : null });
      if (url.startsWith('/api/workspaces/')) return answer(200, { status: 'updated', level: 'viewer', admin: false });
      return answer(200, { user_id: 'usr_bob' });
    });
    const api = createPeopleApi(fetcher);
    expect(await api.updateWorkspaceMember('ws-1', 'usr_bob', { level: 'viewer' })).toEqual({ level: 'viewer', admin: false });
    await api.updateOrganizationAccess('org-1', 'usr_bob', { orgAdmin: true, level: 'member', capabilities: ['grp_runners'] });
    await api.setOrganizationWorkspaces('org-1', 'usr_bob', [{ id: 'ws-1', admin: true }]);
    expect(calls).toEqual([
      { url: '/api/workspaces/ws-1/members/usr_bob', method: 'PATCH', body: { level: 'viewer' } },
      {
        url: '/api/organizations/org-1/members/usr_bob',
        method: 'PATCH',
        body: { org_admin: true, level: 'member', capabilities: ['grp_runners'] },
      },
      {
        url: '/api/organizations/org-1/members/usr_bob/workspaces',
        method: 'PUT',
        body: { workspaces: [{ id: 'ws-1', admin: true }] },
      },
    ]);
  });

  it("lists the capability groups, leaving out the model's own", async () => {
    const fetcher = vi.fn(async () =>
      answer(200, {
        items: [
          { id: 'grp_runners', name: 'Workflow runners', description: null, owner_scope: 'abi:nexus:organization/org-1', scope: 'organization' },
          { id: 'grp_admins', name: 'Acme admins', description: null, owner_scope: 'abi:nexus:organization/org-1', scope: 'organization' },
        ],
      })
    );
    expect((await createPeopleApi(fetcher).capabilityGroups({ workspaceId: 'ws-1' })).map((g) => g.id)).toEqual(['grp_runners']);
    expect(fetcher).toHaveBeenCalledWith('/api/workspaces/ws-1/capability-groups', undefined);
  });

  it('says what the API refused', async () => {
    const fetcher = vi.fn(async () => answer(409, { detail: 'Already a member of this workspace' }));
    await expect(createPeopleApi(fetcher).addMember('ws-1', { userId: 'usr_flo' })).rejects.toThrow(
      'Already a member of this workspace'
    );
  });
});
