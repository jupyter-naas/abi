// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: () => undefined }) }));

import { PlatformUsers } from './users';
import type { AdminUser, Deletion } from './users-model';

type Call = { url: string; method: string; body: unknown };
type Answer = { status: number; body: unknown };

const user = (over: Partial<AdminUser>): AdminUser => ({
  id: 'usr_a',
  kind: 'account',
  email: 'a@example.com',
  name: 'A',
  avatar: null,
  principal_id: 'usr_a',
  status: 'signed_in',
  deactivated: false,
  is_superadmin: false,
  created_at: '2026-10-01T00:00:00',
  organizations: [],
  provider: 'builtin',
  ...over,
});

const ADMIN = user({ id: 'usr_admin', principal_id: 'usr_admin', email: 'admin@example.com', name: 'Admin', is_superadmin: true });
const BOB = user({
  id: 'usr_bob',
  principal_id: 'usr_bob',
  email: 'bob@example.com',
  name: 'Bob',
  organizations: [{ id: 'org-1', name: 'Acme', role: 'member' }],
});
const NEW = user({
  id: 'invited:new@example.com',
  kind: 'invitation',
  principal_id: null,
  email: 'new@example.com',
  name: 'new',
  status: 'invited',
});
const USERS = [ADMIN, BOB, NEW];

function api(answers: Record<string, (call: Call) => Answer> = {}, users: AdminUser[] = USERS) {
  const calls: Call[] = [];
  const fetcher = async (url: string, options: RequestInit = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    const call = { url, method, body: options.body ? JSON.parse(String(options.body)) : null };
    calls.push(call);
    const answer =
      answers[`${method} ${url}`]?.(call) ??
      (method === 'GET' && url === '/api/admin/users'
        ? { status: 200, body: users }
        : method === 'GET' && url === '/api/invitations/providers'
          ? {
              status: 200,
              body: {
                enabled: true,
                default_provider: 'builtin',
                providers: [
                  { name: 'builtin', display_name: 'Built-in', provisioning: 'builtin', managed_in_provider: false },
                  { name: 'okta', display_name: 'Okta', provisioning: 'none', managed_in_provider: true },
                ],
              },
            }
          : { status: 404, body: {} });
    return new Response(JSON.stringify(answer.body), { status: answer.status });
  };
  return { fetcher, calls };
}

const ALL = new Set([
  'nexus:ListUsers',
  'nexus:InviteUser',
  'nexus:UpdateUser',
  'nexus:SuspendUser',
  'nexus:ResumeUser',
  'nexus:DeleteUser',
]);
const everything = (action: string) => ALL.has(action);

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

const row = (id: string) => mounted!.host.querySelector(`tr[data-user="${CSS.escape(id)}"]`)!;
const panel = (id: string) => mounted!.host.querySelector(`tr[data-panel="${CSS.escape(id)}"]`);

async function render(props: Partial<Parameters<typeof PlatformUsers>[0]> & { fetcher: Parameters<typeof PlatformUsers>[0]['fetcher'] }) {
  const navigate = vi.fn();
  mounted = await mount(PlatformUsers, { can: everything, selfId: 'usr_admin', navigate, ...props });
  await mounted.flush();
  return navigate;
}

describe('PlatformUsers', () => {
  it('lists every account and invitation with its IAM id, status, superadmin and organizations', async () => {
    const { fetcher } = api();
    await render({ fetcher });
    const rows = [...mounted!.host.querySelectorAll('tr[data-user]')].map((r) => r.getAttribute('data-user'));
    expect(rows).toEqual(['usr_admin', 'usr_bob', 'invited:new@example.com']);
    expect(row('usr_bob').textContent).toContain('usr_bob');
    expect(row('usr_bob').querySelector('[data-field="status"]')?.textContent).toBe('Signed in');
    expect(row('usr_bob').querySelector('[data-field="organizations"]')?.textContent).toBe('Acme');
    expect(row('usr_admin').querySelector('[data-field="superadmin"]')?.textContent).toContain('Superadmin');
    expect(row('invited:new@example.com').querySelector('[data-field="status"]')?.textContent).toBe('Invited, not yet');
    expect(row('invited:new@example.com').textContent).toContain('None yet');
  });

  it('opens the person page of a row with an IAM id, never the row of someone IAM has none for', async () => {
    const { fetcher } = api();
    const navigate = await render({ fetcher });
    await mounted!.click(row('usr_bob').querySelector('td'));
    expect(navigate).toHaveBeenCalledWith('/settings/roles?section=people&person=usr_bob');
    navigate.mockClear();
    await mounted!.click(row('invited:new@example.com').querySelector('td'));
    expect(navigate).not.toHaveBeenCalled();
  });

  it('searches every column', async () => {
    const { fetcher } = api();
    await render({ fetcher });
    await mounted!.type(mounted!.host.querySelector('input[type="search"]'), 'acme');
    expect([...mounted!.host.querySelectorAll('tr[data-user]')].map((r) => r.getAttribute('data-user'))).toEqual(['usr_bob']);
    expect(mounted!.host.textContent).toContain('1 of 3 users');
  });

  it('offers nothing on oneself, and only the actions the access gives', async () => {
    const { fetcher } = api();
    await render({ fetcher, can: (a) => a === 'nexus:ListUsers' || a === 'nexus:SuspendUser' });
    expect(row('usr_admin').querySelectorAll('button')).toHaveLength(0);
    expect(row('usr_admin').textContent).toContain('You');
    const actions = [...row('usr_bob').querySelectorAll('[data-action]')].map((b) => b.getAttribute('data-action'));
    expect(actions).toEqual(['deactivate']);
    expect(mounted!.host.querySelector('[data-action="invite"]')).toBeNull();
  });

  it('never offers superadmin to someone invited who has no account', async () => {
    const { fetcher } = api();
    await render({ fetcher });
    expect(row('usr_bob').querySelector('[data-action="superadmin"]')).not.toBeNull();
    expect(row('invited:new@example.com').querySelector('[data-action="superadmin"]')).toBeNull();
  });

  it('deactivates and reactivates, the row as the API answers it, a warning said', async () => {
    const { fetcher, calls } = api({
      'POST /api/admin/users/usr_bob/deactivate': () => ({
        status: 200,
        body: { ...BOB, deactivated: true, warning: 'Okta manages its people: deactivate them there too' },
      }),
    });
    await render({ fetcher });
    await mounted!.click(row('usr_bob').querySelector('[data-action="deactivate"]'));
    await mounted!.flush();
    expect(calls.some((c) => c.method === 'POST' && c.url === '/api/admin/users/usr_bob/deactivate')).toBe(true);
    expect(row('usr_bob').querySelector('[data-field="deactivated"]')?.textContent).toBe('Deactivated');
    expect(row('usr_bob').querySelector('[data-action="reactivate"]')).not.toBeNull();
    expect(panel('usr_bob')?.querySelector('[role="status"]')?.textContent).toContain('Okta manages');
  });

  it('url-encodes an invitation id', async () => {
    const { fetcher, calls } = api({
      'POST /api/admin/users/invited%3Anew%40example.com/deactivate': () => ({ status: 200, body: { ...NEW, deactivated: true } }),
    });
    await render({ fetcher });
    await mounted!.click(row('invited:new@example.com').querySelector('[data-action="deactivate"]'));
    await mounted!.flush();
    expect(calls.map((c) => c.url)).toContain('/api/admin/users/invited%3Anew%40example.com/deactivate');
  });

  it('shows the API words of a refusal at the row', async () => {
    const detail = 'The platform needs at least one superadmin';
    const { fetcher } = api({ 'PATCH /api/admin/users/usr_bob': () => ({ status: 400, body: { detail } }) });
    await render({ fetcher });
    await mounted!.click(row('usr_bob').querySelector('[data-action="superadmin"]'));
    await mounted!.flush();
    expect(panel('usr_bob')?.querySelector('[role="alert"]')?.textContent).toBe(detail);
  });

  it('renames with PATCH', async () => {
    const { fetcher, calls } = api({
      'PATCH /api/admin/users/usr_bob': (call) => ({ status: 200, body: { ...BOB, ...(call.body as object) } }),
    });
    await render({ fetcher });
    await mounted!.click(row('usr_bob').querySelector('[data-action="rename"]'));
    await mounted!.type(panel('usr_bob')!.querySelector('[data-field="rename"]'), 'Robert');
    await mounted!.click(panel('usr_bob')!.querySelector('[data-action="save"]'));
    await mounted!.flush();
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ name: 'Robert' });
    expect(row('usr_bob').textContent).toContain('Robert');
  });

  it('says what a delete takes and leaves, and deletes once the email is typed back', async () => {
    const deletion: Deletion = {
      user: BOB,
      blocked: null,
      warning: 'Built-in keeps their account: delete it at the provider too',
      goes: {
        provider_account: { provider: 'builtin', display_name: 'Built-in', managed_in_provider: false },
        iam_user: 'usr_bob',
        attachments: 3,
        memberships: [{ scope: 'abi:nexus:organization/org-1', label: 'Acme', role: 'member' }],
        groups: 1,
        sessions: 2,
        api_keys: 1,
        invitations: 0,
      },
      stays: { workspaces: [{ id: 'ws-1', name: 'Research' }] },
    };
    const { fetcher, calls } = api({
      'GET /api/admin/users/usr_bob/deletion': () => ({ status: 200, body: deletion }),
      'DELETE /api/admin/users/usr_bob?confirm=bob%40example.com': () => ({
        status: 200,
        body: { deleted: true, warning: 'builtin could not be reached' },
      }),
    });
    await render({ fetcher });
    await mounted!.click(row('usr_bob').querySelector('[data-action="delete"]'));
    await mounted!.flush();
    const goes = panel('usr_bob')!.querySelector('[data-list="goes"]')!.textContent!;
    expect(goes).toContain('Their account at the identity provider, Built-in.');
    expect(goes).toContain('usr_bob');
    expect(goes).toContain('3 policy attachments');
    expect(goes).toContain('1 group');
    expect(goes).toContain('member of Acme');
    expect(goes).toContain('2 signed-in sessions and 1 API key');
    expect(panel('usr_bob')!.querySelector('[data-list="stays"]')!.textContent).toContain('Research');
    expect(panel('usr_bob')!.querySelector('[data-field="deletion-warning"]')!.textContent).toContain(
      'keeps their account'
    );
    const confirm = () => panel('usr_bob')!.querySelector('[data-action="confirm-delete"]') as HTMLButtonElement;
    expect(confirm().disabled).toBe(true);
    await mounted!.type(panel('usr_bob')!.querySelector('[data-field="confirm"]'), 'bob@example.com');
    expect(confirm().disabled).toBe(false);
    await mounted!.click(confirm());
    await mounted!.flush();
    expect(calls.filter((c) => c.method === 'DELETE').map((c) => c.url)).toEqual([
      '/api/admin/users/usr_bob?confirm=bob%40example.com',
    ]);
    expect(calls.filter((c) => c.method === 'GET' && c.url === '/api/admin/users')).toHaveLength(2);
    // The row is gone: what the provider could not do is said above the table.
    expect(document.querySelector('[data-field="page-notice"]')?.textContent).toBe(
      'bob@example.com: builtin could not be reached'
    );
  });

  it('refuses a blocked delete with its reason and no confirmation', async () => {
    const blocked = 'Bob alone owns Acme: hand it over first';
    const { fetcher } = api({
      'GET /api/admin/users/usr_bob/deletion': () => ({
        status: 200,
        body: {
          user: BOB,
          blocked,
          goes: { provider_account: null, iam_user: null, attachments: 0, memberships: [], groups: 0, sessions: 0, api_keys: 0, invitations: 0 },
          stays: { workspaces: [] },
        },
      }),
    });
    await render({ fetcher });
    await mounted!.click(row('usr_bob').querySelector('[data-action="delete"]'));
    await mounted!.flush();
    expect(panel('usr_bob')!.querySelector('[data-field="blocked"]')?.textContent).toBe(blocked);
    expect(panel('usr_bob')!.querySelector('[data-field="confirm"]')).toBeNull();
  });

  it('invites through the provider picked, and says what was done', async () => {
    const { fetcher, calls } = api({
      'POST /api/admin/users/invite': () => ({
        status: 200,
        body: {
          user: user({ id: 'invited:carol@example.com', email: 'carol@example.com', status: 'invited' }),
          user_created: true,
          sign_in_email_sent: true,
          provisioning_skipped: false,
          renewed: false,
          warning: null,
        },
      }),
    });
    await render({ fetcher });
    await mounted!.click(mounted!.host.querySelector('[data-action="invite"]'));
    await mounted!.flush();
    await mounted!.type(mounted!.host.querySelector('[data-field="invite-email"]'), 'carol@example.com');
    await mounted!.select(mounted!.host.querySelector('[data-field="invite-provider"]'), 'okta');
    await mounted!.click(mounted!.host.querySelector('[data-action="send-invite"]'));
    await mounted!.flush();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ email: 'carol@example.com', provider: 'okta' });
    const said = mounted!.host.querySelector('[data-field="invite-outcome"]')!.textContent!;
    expect(said).toContain('carol@example.com invited.');
    expect(said).toContain('Their account was made at the identity provider.');
    expect(said).toContain('A sign-in link was emailed to them.');
  });

  it('says why the list could not be read', async () => {
    const { fetcher } = api({ 'GET /api/admin/users': () => ({ status: 403, body: { detail: 'Not allowed to list users' } }) });
    await render({ fetcher });
    expect(mounted!.host.querySelector('[role="alert"]')?.textContent).toBe('Not allowed to list users');
  });
});
