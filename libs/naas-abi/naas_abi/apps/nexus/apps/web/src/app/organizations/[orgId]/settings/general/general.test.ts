// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
vi.mock('next/navigation', () => ({ useParams: () => ({ orgId: 'acme' }) }));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});

import { clearPageState } from '@/lib/page-state';
import { clearResources } from '@/lib/resource-cache';
import { clearViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
import OrganizationGeneralPage from './general';

const admin: User = { id: 'admin', email: 'admin@example.invalid', name: 'Admin', createdAt: new Date() };

/** The organization as the API holds it; another administrator may change it meanwhile. */
let organization: Record<string, unknown>;
let reads = 0;
let mounted: Mounted | null = null;

beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  useAuthStore.setState({ user: admin, csrfToken: 'csrf-admin', isAuthenticated: true });
  clearPageState();
  clearResources();
  organization = { id: 'acme', name: 'Acme', city: 'Paris', website: 'https://acme.test', current_user_role: 'admin' };
  reads = 0;
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    const path = new URL(input).pathname;
    if (path === '/api/organizations/acme') {
      reads += 1;
      return Response.json(organization);
    }
    if (path === '/api/organizations/acme/domains') return Response.json([]);
    return Response.json({});
  }));
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.unstubAllGlobals();
});

const input = (id: string) => mounted!.host.querySelector<HTMLInputElement>(`#org-${id}`)!;

async function open() {
  mounted = await mount(OrganizationGeneralPage, {});
  for (let i = 0; i < 20 && !mounted.host.querySelector('#org-name'); i += 1) await mounted.flush();
}

describe('Organization › General keeps unsaved edits', () => {
  it('a return finds them; a fresh read updates the fields not edited', async () => {
    await open();
    await mounted!.type(input('legal_name'), 'Acme Holding SAS');
    await mounted!.unmount();

    // Meanwhile another administrator moved the organization; the kept answer is stale.
    organization = { ...organization, city: 'Lyon' };
    clearResources();
    await open();
    expect(reads).toBe(2);
    expect(input('legal_name').value).toBe('Acme Holding SAS');
    expect(input('city').value).toBe('Lyon');
    expect(mounted!.host.textContent).toContain('Unsaved changes.');
    expect(mounted!.host.textContent).not.toContain('Changed elsewhere');
  });

  it('a field changed on both sides keeps the edit and says so', async () => {
    await open();
    await mounted!.type(input('name'), 'Acme Group');
    await mounted!.unmount();

    organization = { ...organization, name: 'Acme Corp' };
    clearResources();
    await open();
    expect(input('name').value).toBe('Acme Group');
    expect(mounted!.host.textContent).toContain('Changed elsewhere since you began editing: Name');

    const discard = [...mounted!.host.querySelectorAll('button')].find((b) => b.textContent === 'Discard changes')!;
    await mounted!.click(discard);
    expect(input('name').value).toBe('Acme Corp');
    expect(mounted!.host.textContent).not.toContain('Unsaved changes.');
  });
});
