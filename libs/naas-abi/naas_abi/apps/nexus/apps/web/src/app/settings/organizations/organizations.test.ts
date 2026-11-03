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
vi.mock('../system/system', () => ({ SystemFrame: () => null, SystemRefresh: () => null }));

import { PlatformOrganizations } from './organizations';

type Call = { url: string; method: string; body: unknown };

function api(
  answers: Record<string, (call: Call) => { status: number; body: unknown }>,
  organizations: { id: string; name: string; slug: string }[]
) {
  const calls: Call[] = [];
  const fetcher = async (url: string, options: RequestInit = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    const call = { url, method, body: options.body ? JSON.parse(String(options.body)) : null };
    calls.push(call);
    const answer =
      answers[`${method} ${url}`]?.(call) ??
      (method === 'GET' && url === '/api/organizations' ? { status: 200, body: organizations } : { status: 404, body: {} });
    return new Response(JSON.stringify(answer.body), { status: answer.status });
  };
  return { fetcher, calls };
}

const ORGS = [
  { id: 'org-a', name: 'Acme', slug: 'acme' },
  { id: 'org-b', name: 'Beta Corp', slug: 'beta' },
];

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const row = (id: string) => mounted!.host.querySelector(`[data-org="${id}"]`)!;

describe('PlatformOrganizations', () => {
  it('lists every organization with a link to its settings', async () => {
    const { fetcher } = api({}, ORGS);
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    const rows = [...mounted.host.querySelectorAll('[data-org]')];
    expect(rows.map((r) => r.getAttribute('data-org'))).toEqual(['org-a', 'org-b']);
    expect(rows[1].textContent).toContain('Beta Corp');
    expect(rows[1].textContent).toContain('beta');
    expect(rows[1].querySelector('a')?.getAttribute('href')).toBe('/organizations/org-b/settings');
  });

  it('renames with PATCH and reloads', async () => {
    const { fetcher, calls } = api(
      { 'PATCH /api/organizations/org-b': () => ({ status: 200, body: { id: 'org-b' } }) },
      ORGS
    );
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.click(row('org-b').querySelector('[data-action="rename"]'));
    await mounted.type(row('org-b').querySelector('[data-field="rename"]'), 'Beta Corporation');
    await mounted.click(row('org-b').querySelector('[data-action="save"]'));
    await mounted.flush();
    expect(calls.find((c) => c.method === 'PATCH')).toEqual({
      url: '/api/organizations/org-b',
      method: 'PATCH',
      body: { name: 'Beta Corporation' },
    });
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(2);
  });

  it('deletes only once the name is typed back', async () => {
    const { fetcher, calls } = api(
      { 'DELETE /api/organizations/org-b': () => ({ status: 200, body: { status: 'deleted', id: 'org-b' } }) },
      ORGS
    );
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.click(row('org-b').querySelector('[data-action="delete"]'));
    const confirm = () => row('org-b').querySelector('[data-action="confirm-delete"]') as HTMLButtonElement;
    expect(confirm().disabled).toBe(true);
    await mounted.type(row('org-b').querySelector('[data-field="confirm"]'), 'beta');
    expect(confirm().disabled).toBe(true);
    await mounted.type(row('org-b').querySelector('[data-field="confirm"]'), 'Beta Corp');
    expect(confirm().disabled).toBe(false);
    await mounted.click(confirm());
    await mounted.flush();
    expect(calls.filter((c) => c.method === 'DELETE').map((c) => c.url)).toEqual(['/api/organizations/org-b']);
  });

  it('shows the workspaces a 409 names at the row', async () => {
    const detail = 'Organization org-a still has workspaces: Alpha (ws-1), Bravo (ws-2). Delete them first';
    const { fetcher } = api({ 'DELETE /api/organizations/org-a': () => ({ status: 409, body: { detail } }) }, ORGS);
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.click(row('org-a').querySelector('[data-action="delete"]'));
    await mounted.type(row('org-a').querySelector('[data-field="confirm"]'), 'Acme');
    await mounted.click(row('org-a').querySelector('[data-action="confirm-delete"]'));
    await mounted.flush();
    expect(row('org-a').querySelector('[role="alert"]')?.textContent).toBe(detail);
    expect(row('org-b').querySelector('[role="alert"]')).toBeNull();
  });

  it('creates with POST, the slug suggested from the name; a taken slug is said', async () => {
    let taken = false;
    const { fetcher, calls } = api(
      {
        'POST /api/organizations': () =>
          taken ? { status: 400, body: { detail: 'Slug already exists' } } : { status: 200, body: { id: 'org-c' } },
      },
      ORGS
    );
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.type(mounted.host.querySelector('[data-field="name"]'), 'Beta Corp');
    expect((mounted.host.querySelector('[data-field="slug"]') as HTMLInputElement).value).toBe('beta-corp');
    await mounted.click(mounted.host.querySelector('[data-action="create"]'));
    await mounted.flush();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ name: 'Beta Corp', slug: 'beta-corp' });
    taken = true;
    await mounted.type(mounted.host.querySelector('[data-field="name"]'), 'Acme');
    await mounted.click(mounted.host.querySelector('[data-action="create"]'));
    await mounted.flush();
    expect(mounted.host.querySelector('.platform-orgs-create [role="alert"]')?.textContent).toBe(
      'Slug already exists'
    );
  });
});
