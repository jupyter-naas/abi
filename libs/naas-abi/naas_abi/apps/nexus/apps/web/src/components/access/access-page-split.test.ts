// @vitest-environment jsdom
/**
 * A page of Access loads its own view alone (#1609): opening Groups never evaluates the
 * policy builder, the simulator or any other page's code.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AccessView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { fakeApi, fakeDirectory } from './access-fixtures';
import type { AccessHrefs } from './access-page';
import { PLATFORM_ACCESS_SCOPE } from './access-scope';
import type { AccessSection } from './access-sections';

const loaded = vi.hoisted(() => new Set<string>());

vi.mock('./policies/policies', async (original) => (loaded.add('policies'), original()));
vi.mock('./groups/groups', async (original) => (loaded.add('groups'), original()));
vi.mock('./service-accounts/service-accounts', async (original) => (loaded.add('service-accounts'), original()));
vi.mock('./approvals/approvals', async (original) => (loaded.add('approvals'), original()));
vi.mock('./simulator/simulator', async (original) => (loaded.add('simulator'), original()));
vi.mock('./audit/audit', async (original) => (loaded.add('audit'), original()));

const everything: AccessView = {
  actions: Object.fromEntries(
    ['iam:ListGroups', 'iam:ListPolicies', 'iam:ListPrincipals', 'iam:ListManifests', 'iam:Explain', 'nexus:ReadSystem'].map(
      (a) => [a, true],
    ),
  ),
};

const hrefs: AccessHrefs = { page: (section, id) => `/access/${section}${id ? `/${id}` : ''}`, person: null };

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function open(section: AccessSection) {
  const { AccessPage } = await import('./access-page');
  const api = fakeApi({
    access: vi.fn().mockResolvedValue(everything),
    listGroups: vi.fn().mockResolvedValue({ items: [] }),
    listPolicies: vi.fn().mockResolvedValue({ items: [], next_after: null }),
    listAttachments: vi.fn().mockResolvedValue({ items: [] }),
    listPrincipals: vi.fn().mockResolvedValue({ items: [] }),
  });
  mounted = await mount(AccessPage, {
    section,
    scopes: [PLATFORM_ACCESS_SCOPE],
    api,
    directory: fakeDirectory([]),
    hrefs,
    navigate: vi.fn(),
  });
  await vi.waitFor(async () => {
    await mounted!.flush();
    expect(document.querySelector('[data-access-loading]')).toBeNull();
  });
}

describe('Access pages load on demand', () => {
  it('evaluates no view before a page opens', async () => {
    await import('./access-page');
    expect([...loaded]).toEqual([]);
  });

  it('opens Groups with the Groups view alone, then Simulator with its own', async () => {
    await open('groups');
    expect([...loaded]).toEqual(['groups']);
    await mounted?.unmount();
    mounted = null;

    await open('simulator');
    expect([...loaded].sort()).toEqual(['groups', 'simulator']);
  });
});
