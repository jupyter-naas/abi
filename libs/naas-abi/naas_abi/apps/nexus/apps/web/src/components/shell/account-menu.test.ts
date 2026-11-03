// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({ user: 'olivia', answers: {} as Record<string, unknown> }));

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: () => undefined }) }));
vi.mock('@/hooks/use-platform-settings-access', () => ({
  usePlatformSettingsAccess: () => ({ status: 'ready', actions: {}, retry: () => undefined }),
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ user: { id: state.user }, logout: () => undefined }),
  authFetch: async (url: string) =>
    url in state.answers
      ? new Response(JSON.stringify(state.answers[url]), { status: 200 })
      : new Response('{}', { status: 403 }),
}));

import { AccountMenuPanel } from './account-menu';

const ACCESS_ACME = `/api/iam/admin/access?scope=${encodeURIComponent('abi:nexus:organization/acme')}`;

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function menuFor(user: string, orgRole: string): Promise<string> {
  state.user = user;
  state.answers = {
    '/api/organizations': [{ id: 'acme' }],
    '/api/organizations/acme': { current_user_role: orgRole },
    [ACCESS_ACME]: { actions: { 'iam:ListPolicies': false } },
  };
  mounted = await mount(AccountMenuPanel, { user: { name: user, email: `${user}@example.com` }, onClose: () => undefined });
  await mounted.flush();
  await mounted.flush();
  return mounted.host.textContent ?? '';
}

describe('the account menu', () => {
  it('shows Organization Settings to an organization admin', async () => {
    expect(await menuFor('olivia', 'admin')).toContain('Organization Settings');
  });
  it('hides it from a workspace owner who is a member of the organization', async () => {
    expect(await menuFor('bob', 'member')).not.toContain('Organization Settings');
  });
});
