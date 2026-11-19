import { describe, expect, it, vi } from 'vitest';
import {
  CANDIDATE_LIMIT,
  addMemberBody,
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
      '/workspace/ws-1/settings/members/new?email=bob%40example.com'
    );
    expect(createUserHref('ws-1', ' Bob Martin ')).toBe('/workspace/ws-1/settings/members/new?name=Bob+Martin');
    expect(createUserHref('ws-1', '')).toBe('/workspace/ws-1/settings/members/new');
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
  it('adds a suggestion by its user id, with the role and the policies picked', () => {
    expect(addMemberBody({ userId: 'usr_flo', role: 'viewer' })).toEqual({ user_id: 'usr_flo', role: 'viewer' });
    expect(addMemberBody({ userId: 'usr_flo', role: 'admin', policyIds: ['pol_graph'] })).toEqual({
      user_id: 'usr_flo',
      role: 'admin',
      policy_ids: ['pol_graph'],
    });
  });

  it('keeps only the profile fields filled in', () => {
    expect(filledProfile({ organization: ' Acme ', job_title: '', country: '  ' })).toEqual({ organization: 'Acme' });
    expect(filledProfile({ job_title: '' })).toBeUndefined();
  });

  it('creates into a workspace with the profile nested, and no org role', () => {
    const body = workspaceCreateBody({
      email: ' bob@example.com ',
      name: 'Bob',
      role: 'member',
      policyIds: ['pol_1'],
      provider: 'okta',
      profile: { job_title: 'Analyst' },
    });
    expect(body).toEqual({
      email: 'bob@example.com',
      name: 'Bob',
      role: 'member',
      policy_ids: ['pol_1'],
      provider: 'okta',
      profile: { job_title: 'Analyst' },
    });
    expect(workspaceCreateBody({ email: 'bob@example.com', role: 'viewer' })).toEqual({
      email: 'bob@example.com',
      role: 'viewer',
    });
  });

  it('creates into an organization in one request with every workspace, the profile flat', () => {
    expect(
      organizationCreateBody({
        email: 'bob@example.com',
        role: 'member',
        workspaces: [
          { id: 'ws-1', role: 'member' },
          { id: 'ws-2', role: 'viewer' },
        ],
        profile: { country: 'FR' },
      })
    ).toEqual({
      email: 'bob@example.com',
      role: 'member',
      workspaces: [
        { id: 'ws-1', role: 'member' },
        { id: 'ws-2', role: 'viewer' },
      ],
      country: 'FR',
    });
  });

  it('sends no org role (null) only with a workspace', () => {
    expect(
      organizationCreateBody({ email: 'bob@example.com', role: null, workspaces: [{ id: 'ws-1', role: 'member' }] })
    ).toMatchObject({ role: null, workspaces: [{ id: 'ws-1', role: 'member' }] });
    expect(() => organizationCreateBody({ email: 'bob@example.com', role: null, workspaces: [] })).toThrow(
      'at least one workspace'
    );
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
    const href = membersAddedHref('/workspace/ws-1/settings/members', readCreatedPerson(ADDED)!);
    expect(href).toBe('/workspace/ws-1/settings/members?added=bob%40example.com&mailed=1');
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
    expect(await api.addMember('ws-1', { userId: 'usr_flo', role: 'member' })).toEqual({
      member: { id: 'm' },
      emailSent: true,
    });
    await api.createInWorkspace('ws-1', { email: 'bob@example.com', role: 'member' });
    await api.createInOrganization('org-1', {
      email: 'bob@example.com',
      role: null,
      workspaces: [{ id: 'ws-1', role: 'member' }],
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
    expect(calls[0].body).toEqual({ user_id: 'usr_flo', role: 'member' });
    expect(calls[2].body).toEqual({ email: 'bob@example.com', role: null, workspaces: [{ id: 'ws-1', role: 'member' }] });
  });

  it('says what the API refused', async () => {
    const fetcher = vi.fn(async () => answer(409, { detail: 'Already a member of this workspace' }));
    await expect(createPeopleApi(fetcher).addMember('ws-1', { userId: 'usr_flo', role: 'member' })).rejects.toThrow(
      'Already a member of this workspace'
    );
  });
});
