// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({
  role: 'member' as string | null,
  access: null as null | { actions: Record<string, boolean> },
  replaced: [] as string[],
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/organizations/acme/settings/general',
  useParams: () => ({ orgId: 'acme' }),
  useRouter: () => ({ replace: (to: string) => state.replaced.push(to), push: () => undefined, prefetch: () => undefined }),
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('@/hooks/use-is-mobile', () => ({ useIsMobile: () => false }));
vi.mock('@/hooks/use-dev-route-warmup', () => ({ useDevRouteWarmup: () => undefined }));
vi.mock('@/lib/iam-admin/use-access', () => ({
  useIamAccess: () => ({ access: state.access, loading: false, error: null, can: () => false }),
}));
vi.mock('@/stores/workspace', () => {
  const store = { currentWorkspaceId: 'ws-1' };
  return { useWorkspaceStore: (select: (s: typeof store) => unknown) => select(store) };
});
vi.mock('@/stores/auth', () => ({
  authFetch: async (url: string) =>
    url === '/api/organizations/acme'
      ? new Response(JSON.stringify({ name: 'Acme', current_user_role: state.role }), { status: 200 })
      : new Response(JSON.stringify([{ id: 'acme' }, { id: 'beta' }]), { status: 200 }),
}));

import { createElement } from 'react';
import OrganizationSettingsLayout from './layout';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  state.replaced = [];
});

async function render(): Promise<string> {
  mounted = await mount(OrganizationSettingsLayout, { children: createElement('p', null, 'GENERAL PAGE') });
  for (let i = 0; i < 4; i += 1) await mounted.flush();
  return mounted.host.textContent ?? '';
}

describe('organization settings by URL (UJ-O1)', () => {
  it('show General and the admin sections to an organization admin (Olivia)', async () => {
    state.role = 'admin';
    state.access = { actions: { 'iam:ListPolicies': true } };
    const text = await render();
    expect(text).toContain('GENERAL PAGE');
    expect(text).toContain('Users');
  });

  it('refuse an organization member with no iam: right there (Eve, Bob)', async () => {
    state.role = 'member';
    state.access = { actions: { 'iam:ListPolicies': false } };
    const text = await render();
    expect(text).not.toContain('GENERAL PAGE');
    expect(text).not.toContain('Workspaces');
    expect(text).toContain('You have no access to these settings');
  });

  it('send a member holding iam: rights there to Roles & permissions', async () => {
    state.role = 'member';
    state.access = { actions: { 'iam:ListPolicies': true } };
    await render();
    expect(state.replaced).toEqual(['/organizations/acme/settings/roles']);
  });
});
