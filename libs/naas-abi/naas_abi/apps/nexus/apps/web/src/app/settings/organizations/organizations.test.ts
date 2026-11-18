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
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: () => undefined }) }));

import { PlatformOrganizations } from './organizations';
import { NewOrganization } from './new-organization';

type Call = { url: string; method: string; body: unknown };

function api(
  answers: Record<string, (call: Call) => { status: number; body: unknown }>,
  organizations: Record<string, unknown>[]
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
  {
    id: 'org-b',
    name: 'Beta Corp',
    slug: 'beta',
    legal_name: 'Beta Corporation SA',
    city: 'Lyon',
    country: 'France',
    website: 'https://beta.example/',
    created_at: '2026-03-01T10:00:00',
  },
  { id: 'org-a', name: 'Acme', slug: 'acme', created_at: '2026-01-15T09:00:00' },
];

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const row = (id: string) => mounted!.host.querySelector(`tr[data-org="${id}"]`)!;
const panel = (id: string) => mounted!.host.querySelector(`tr[data-panel="${id}"]`)!;
const rowIds = () => [...mounted!.host.querySelectorAll('tr[data-org]')].map((r) => r.getAttribute('data-org'));

describe('PlatformOrganizations', () => {
  it('is a table of every organization, its count next to the title', async () => {
    const { fetcher } = api({}, ORGS);
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    expect(mounted.host.querySelector('h2')?.textContent).toBe('Organizations');
    expect(mounted.host.textContent).toContain('2 organizations');
    expect(rowIds()).toEqual(['org-a', 'org-b']);
    const beta = row('org-b');
    expect(beta.textContent).toContain('Beta Corp');
    expect(beta.textContent).toContain('beta');
    expect(beta.querySelector('[data-field="legal_name"]')?.textContent).toBe('Beta Corporation SA');
    expect(beta.querySelector('[data-field="location"]')?.textContent).toBe('Lyon, France');
    expect(beta.querySelector('[data-field="website"] a')?.textContent).toBe('beta.example');
    expect(beta.querySelector('[data-action="settings"]')?.getAttribute('href')).toBe('/organizations/org-b/settings');
  });

  it('creates on a page of its own, from the button at the top right', async () => {
    const { fetcher } = api({}, ORGS);
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    expect(mounted.host.querySelector('[data-action="new"]')?.getAttribute('href')).toBe('/settings/organizations/new');
    expect(mounted.host.querySelector('[data-field="name"]')).toBeNull();
  });

  it('opens the organization when its row is clicked', async () => {
    const { fetcher } = api({}, ORGS);
    const navigate = vi.fn();
    mounted = await mount(PlatformOrganizations, { fetcher, navigate });
    await mounted.flush();
    await mounted.click(row('org-b').querySelector('td'));
    expect(navigate).toHaveBeenCalledWith('/organizations/org-b/settings');
    navigate.mockClear();
    await mounted.click(row('org-b').querySelector('[data-action="rename"]'));
    expect(navigate).not.toHaveBeenCalled();
  });

  it('searches and sorts', async () => {
    const { fetcher } = api({}, ORGS);
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.click(mounted.host.querySelector('[data-sort="created"]'));
    expect(rowIds()).toEqual(['org-a', 'org-b']);
    await mounted.click(mounted.host.querySelector('[data-sort="created"]'));
    expect(rowIds()).toEqual(['org-b', 'org-a']);
    await mounted.type(mounted.host.querySelector('input[type="search"]'), 'lyon');
    expect(rowIds()).toEqual(['org-b']);
    expect(mounted.host.textContent).toContain('1 of 2 organizations');
  });

  it('renames with PATCH and reloads', async () => {
    const { fetcher, calls } = api(
      { 'PATCH /api/organizations/org-b': () => ({ status: 200, body: { id: 'org-b' } }) },
      ORGS
    );
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.click(row('org-b').querySelector('[data-action="rename"]'));
    await mounted.type(panel('org-b').querySelector('[data-field="rename"]'), 'Beta Corporation');
    await mounted.click(panel('org-b').querySelector('[data-action="save"]'));
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
    const confirm = () => panel('org-b').querySelector('[data-action="confirm-delete"]') as HTMLButtonElement;
    expect(confirm().disabled).toBe(true);
    await mounted.type(panel('org-b').querySelector('[data-field="confirm"]'), 'beta');
    expect(confirm().disabled).toBe(true);
    await mounted.type(panel('org-b').querySelector('[data-field="confirm"]'), 'Beta Corp');
    expect(confirm().disabled).toBe(false);
    await mounted.click(confirm());
    await mounted.flush();
    expect(calls.filter((c) => c.method === 'DELETE').map((c) => c.url)).toEqual(['/api/organizations/org-b']);
  });

  it('shows the workspaces a 409 names under the row', async () => {
    const detail = 'Organization org-a still has workspaces: Alpha (ws-1), Bravo (ws-2). Delete them first';
    const { fetcher } = api({ 'DELETE /api/organizations/org-a': () => ({ status: 409, body: { detail } }) }, ORGS);
    mounted = await mount(PlatformOrganizations, { fetcher });
    await mounted.flush();
    await mounted.click(row('org-a').querySelector('[data-action="delete"]'));
    await mounted.type(panel('org-a').querySelector('[data-field="confirm"]'), 'Acme');
    await mounted.click(panel('org-a').querySelector('[data-action="confirm-delete"]'));
    await mounted.flush();
    expect(panel('org-a').querySelector('[role="alert"]')?.textContent).toBe(detail);
    expect(mounted.host.querySelector('tr[data-panel="org-b"]')).toBeNull();
  });
});

describe('NewOrganization', () => {
  const field = (name: string) => mounted!.host.querySelector(`[data-field="${name}"]`);

  it('creates with its general information and opens its settings', async () => {
    const { fetcher, calls } = api(
      { 'POST /api/organizations': () => ({ status: 200, body: { id: 'org-c', name: 'Gamma', slug: 'gamma-group' } }) },
      []
    );
    const navigate = vi.fn();
    mounted = await mount(NewOrganization, { fetcher, navigate });
    const create = () => mounted!.host.querySelector('[data-action="create"]') as HTMLButtonElement;
    expect(create().disabled).toBe(true);

    await mounted.type(field('name'), 'Gamma Group');
    expect((field('slug') as HTMLInputElement).value).toBe('gamma-group');
    await mounted.type(field('legal_name'), ' Gamma Group SAS ');
    await mounted.type(field('website'), 'gamma.example');
    await mounted.type(field('city'), 'Paris');
    expect(create().disabled).toBe(false);
    await mounted.click(create());
    await mounted.flush();

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      name: 'Gamma Group',
      slug: 'gamma-group',
      legal_name: 'Gamma Group SAS',
      website: 'https://gamma.example',
      city: 'Paris',
    });
    expect(navigate).toHaveBeenCalledWith('/organizations/org-c/settings');
  });

  it('keeps a slug typed by hand, refuses an invalid one, and says a taken one', async () => {
    const { fetcher } = api(
      { 'POST /api/organizations': () => ({ status: 400, body: { detail: 'Slug already exists' } }) },
      []
    );
    const navigate = vi.fn();
    mounted = await mount(NewOrganization, { fetcher, navigate });
    const create = () => mounted!.host.querySelector('[data-action="create"]') as HTMLButtonElement;

    await mounted.type(field('name'), 'Acme');
    await mounted.type(field('slug'), 'Acme!');
    expect(create().disabled).toBe(true);
    await mounted.type(field('slug'), 'acme');
    await mounted.type(field('name'), 'Acme Group');
    expect((field('slug') as HTMLInputElement).value).toBe('acme');

    await mounted.click(create());
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toBe('Slug already exists');
    expect(navigate).not.toHaveBeenCalled();
  });
});
