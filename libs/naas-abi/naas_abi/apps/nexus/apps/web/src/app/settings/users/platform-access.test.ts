// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { PlatformAccess } from './platform-access';

const ALICE = {
  id: 'usr_alice',
  kind: 'account',
  email: 'alice@example.com',
  name: 'Alice',
  principal_id: 'prn_alice',
  is_superadmin: false,
};

const ACCESS = {
  user_id: 'usr_alice',
  principal_id: 'prn_alice',
  level: 'member',
  platform_admin: false,
  organizations: [{ id: 'acme', name: 'Acme', org_admin: true }],
  workspaces: [
    { id: 'ws-sales', name: 'Sales', organization_id: 'acme', admin: true },
    { id: 'ws-audit', name: 'Audit', organization_id: 'acme', admin: false },
  ],
  capabilities: [{ id: 'grp_runners', name: 'Workflow runners', owner_scope: 'abi:nexus:organization/acme' }],
};

function fetcherFor(answers: Record<string, { status: number; body: unknown }>) {
  const urls: string[] = [];
  const fetcher = async (url: string) => {
    urls.push(url);
    const answer = answers[url] ?? { status: 404, body: { detail: 'Not found' } };
    return new Response(JSON.stringify(answer.body), { status: answer.status });
  };
  return { fetcher, urls };
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const value = (field: string) => mounted!.host.querySelector(`[data-field="${field}"] dd`)?.textContent;

describe('PlatformAccess', () => {
  it('reads their access by account from their IAM id, as "Platform access (automatic)"', async () => {
    const { fetcher, urls } = fetcherFor({
      '/api/admin/users': { status: 200, body: [ALICE] },
      '/api/admin/users/usr_alice/access': { status: 200, body: ACCESS },
    });
    mounted = await mount(PlatformAccess, { personId: 'prn_alice', fetcher });
    await mounted.flush();
    await mounted.flush();
    expect(urls).toEqual(['/api/admin/users', '/api/admin/users/usr_alice/access']);
    expect(mounted.host.querySelector('h3')?.textContent).toBe('Platform access (automatic)');
    expect(value('platform-admin')).toBe('No');
    expect(value('level')).toBe('Member');
    expect(value('organizations')).toBe('Acme (admin)');
    expect(value('workspaces')).toBe('Sales (admin), Audit');
    expect(value('capabilities')).toBe('Workflow runners');
  });

  it('says when there is no account, and why the API refused', async () => {
    const none = fetcherFor({ '/api/admin/users': { status: 200, body: [] } });
    mounted = await mount(PlatformAccess, { personId: 'prn_bob', fetcher: none.fetcher });
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toBe('They have no account yet.');
    await mounted.unmount();

    const refused = fetcherFor({
      '/api/admin/users': { status: 200, body: [ALICE] },
      '/api/admin/users/usr_alice/access': { status: 403, body: { detail: 'Not allowed' } },
    });
    mounted = await mount(PlatformAccess, { personId: 'usr_alice', fetcher: refused.fetcher });
    await mounted.flush();
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toContain('Not allowed');
  });
});
