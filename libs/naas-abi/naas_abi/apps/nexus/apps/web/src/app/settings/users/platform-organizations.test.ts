// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { PlatformOrganizations } from './platform-organizations';

const ACCESS = {
  user_id: 'usr_alice',
  principal_id: 'prn_alice',
  level: 'member',
  platform_admin: false,
  organizations: [
    { id: 'zeta', name: 'Zeta', org_admin: false },
    { id: 'acme', name: 'Acme', org_admin: true },
  ],
  workspaces: [{ id: 'ws-sales', name: 'Sales', organization_id: 'acme', admin: true }],
  capabilities: [],
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

describe('Platform › Users › a person › Organizations', () => {
  it('lists their organizations by their IAM id in one request, each opening their page there', async () => {
    const { fetcher, urls } = fetcherFor({
      '/api/admin/users/prn_alice/access': { status: 200, body: ACCESS },
    });
    mounted = await mount(PlatformOrganizations, { personId: 'prn_alice', fetcher });
    await mounted.flush();
    await mounted.flush();
    expect(urls).toEqual(['/api/admin/users/prn_alice/access']);
    const rows = [...mounted.host.querySelectorAll('[data-organization]')];
    expect(rows.map((r) => r.getAttribute('data-organization'))).toEqual(['acme', 'zeta']);
    expect(rows[0].textContent).toContain('Administers it');
    expect(rows[1].textContent).toContain('Member');
    expect(rows[0].querySelector('a')?.getAttribute('href')).toBe('/organizations/acme/settings/users/usr_alice');
  });

  it('says when there is no account, and why the API refused', async () => {
    const none = fetcherFor({});
    mounted = await mount(PlatformOrganizations, { personId: 'prn_dana', fetcher: none.fetcher });
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toBe('They have no account yet.');
    await mounted.unmount();

    const refused = fetcherFor({
      '/api/admin/users/usr_alice/access': { status: 403, body: { detail: 'Not allowed' } },
    });
    mounted = await mount(PlatformOrganizations, { personId: 'usr_alice', fetcher: refused.fetcher });
    await mounted.flush();
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toContain('Not allowed');
  });
});
