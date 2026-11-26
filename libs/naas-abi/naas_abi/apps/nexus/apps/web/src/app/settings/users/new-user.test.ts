// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});

import { NewUser } from './new-user';

type Call = { url: string; method: string; body: unknown };

const PROVIDERS = {
  enabled: true,
  default_provider: 'builtin',
  providers: [
    { name: 'builtin', display_name: 'Built-in', provisioning: 'builtin', managed_in_provider: false },
    { name: 'okta', display_name: 'Okta', provisioning: 'none', managed_in_provider: true },
  ],
};

function api(invite: (call: Call) => { status: number; body: unknown }, providers: unknown = PROVIDERS) {
  const calls: Call[] = [];
  const fetcher = async (url: string, options: RequestInit = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    const call = { url, method, body: options.body ? JSON.parse(String(options.body)) : null };
    calls.push(call);
    const answer =
      method === 'POST' && url === '/api/admin/users/invite'
        ? invite(call)
        : method === 'GET' && url === '/api/invitations/providers'
          ? { status: 200, body: providers }
          : { status: 404, body: {} };
    return new Response(JSON.stringify(answer.body), { status: answer.status });
  };
  return { fetcher, calls };
}

const INVITED = {
  user: {
    id: 'invited:carol@example.com',
    kind: 'invitation',
    email: 'carol@example.com',
    name: 'Carol',
    avatar: null,
    principal_id: null,
    status: 'invited',
    deactivated: false,
    is_superadmin: false,
    created_at: null,
    organizations: [],
    provider: 'okta',
  },
  user_created: true,
  sign_in_email_sent: true,
  provisioning_skipped: false,
  renewed: false,
  warning: null,
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const field = (name: string) => mounted!.host.querySelector(`[data-field="${name}"]`);
const create = () => mounted!.host.querySelector('[data-action="create"]') as HTMLButtonElement;

describe('NewUser', () => {
  it('creates through the provider picked, and says what was done', async () => {
    const { fetcher, calls } = api(() => ({ status: 200, body: INVITED }));
    mounted = await mount(NewUser, { fetcher });
    await mounted.flush();
    expect(mounted.host.querySelector('h2')?.textContent).toBe('Create user');
    expect(create().disabled).toBe(true);

    await mounted.type(field('invite-email'), 'carol@example.com');
    await mounted.type(field('invite-name'), ' Carol ');
    await mounted.select(field('invite-provider'), 'okta');
    expect(mounted.host.textContent).toContain('This provider manages its people');
    expect(create().disabled).toBe(false);
    await mounted.click(create());
    await mounted.flush();

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      email: 'carol@example.com',
      name: 'Carol',
      provider: 'okta',
    });
    const said = field('invite-outcome')!.textContent!;
    expect(said).toContain('carol@example.com invited.');
    expect(said).toContain('Their account was made at the identity provider.');
    expect(said).toContain('A sign-in link was emailed to them.');
    expect((field('invite-email') as HTMLInputElement).value).toBe('');
    expect(mounted.host.querySelector('[data-action="cancel"]')?.textContent).toBe('Back to users');
    expect(mounted.host.querySelector('[data-action="cancel"]')?.getAttribute('href')).toBe('/settings/users');
  });

  it('asks for no provider when there is one, and refuses what is not an address', async () => {
    const { fetcher, calls } = api(() => ({ status: 200, body: INVITED }), {
      ...PROVIDERS,
      providers: [PROVIDERS.providers[0]],
    });
    mounted = await mount(NewUser, { fetcher });
    await mounted.flush();
    expect(field('invite-provider')).toBeNull();
    await mounted.type(field('invite-email'), 'carol');
    expect(create().disabled).toBe(true);
    await mounted.type(field('invite-email'), 'carol@example.com');
    await mounted.click(create());
    await mounted.flush();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ email: 'carol@example.com' });
  });

  it('makes them a platform admin when "Platform admin" is ticked', async () => {
    const { fetcher, calls } = api(() => ({ status: 200, body: INVITED }));
    mounted = await mount(NewUser, { fetcher });
    await mounted.flush();
    await mounted.type(field('invite-email'), 'carol@example.com');
    expect((field('invite-platform-admin') as HTMLInputElement).checked).toBe(false);
    await mounted.click(field('invite-platform-admin'));
    await mounted.click(create());
    await mounted.flush();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      email: 'carol@example.com',
      provider: 'builtin',
      platform_admin: true,
    });
    expect((field('invite-platform-admin') as HTMLInputElement).checked).toBe(false);
  });

  it('says why the API refused', async () => {
    const { fetcher } = api(() => ({ status: 403, body: { detail: 'Not allowed to invite users' } }));
    mounted = await mount(NewUser, { fetcher });
    await mounted.flush();
    await mounted.type(field('invite-email'), 'carol@example.com');
    await mounted.click(create());
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toBe('Not allowed to invite users');
  });
});
