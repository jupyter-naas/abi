// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import type { PolicyView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { EMPTY_DIRECTORY } from '../access-directory';
import { PLATFORM_ACCESS_SCOPE } from '../access-scope';
import { WS, adminPublishers, fakeApi, managedPolicy, readerPolicy, wsScope } from '../access-fixtures';
import { PoliciesView, offerWorkspaceOf } from './policies';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
// `authFetch` loads this on its first call: load it here, so the test need not wait for it.
beforeAll(async () => void (await import('@/stores/network-activity')));

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.unstubAllGlobals();
});

const policy = (id: string, name: string, over: Partial<PolicyView> = {}): PolicyView => ({
  ...readerPolicy,
  id,
  name,
  ...over,
});

const platformMember = policy('builtin.platform.member', 'Platform member', { managed: true });
const platformViewer = policy('builtin.platform.viewer', 'Platform viewer', { managed: true });
const nexusApi = policy('builtin.api', 'Nexus API', { managed: true });
const bootstrap = policy('builtin.module_bootstrap', 'Module bootstrap', { managed: true });
const moduleManifest = policy('module.acme.people', 'Module acme/people', { managed: true });
const memberAccess = policy('pol_member', 'Member access', { owner_scope: 'abi:' });
const wsAccess = policy('pol_w', 'Workspace ws-1 access', { owner_scope: WS });

async function open(items: PolicyView[], scope = PLATFORM_ACCESS_SCOPE) {
  const api = fakeApi({
    listPolicies: vi.fn().mockResolvedValue({ items, next_after: null }),
    publishers: vi.fn().mockResolvedValue(adminPublishers),
  });
  mounted = await mount(PoliciesView, { api, can: () => true, scope, directory: EMPTY_DIRECTORY });
  await mounted.flush();
  return api;
}

const listed = () => [...document.querySelectorAll('[data-policy]')].map((r) => r.getAttribute('data-policy'));

describe('Policies and the built-ins', () => {
  it('never lists the automatic platform access nor a service account’s policy', async () => {
    await open([managedPolicy, platformMember, platformViewer, nexusApi, bootstrap, moduleManifest, readerPolicy]);
    expect(listed()).toEqual(['builtin.viewer', 'pol_1']);
    expect(mounted!.host.textContent).not.toContain('Platform member');
  });
});

describe('the generic level policies', () => {
  it('are marked as levels, never deleted, and open read-only with what they grant', async () => {
    await open([memberAccess, readerPolicy]);
    const row = document.querySelector('[data-policy="pol_member"]');
    expect(row?.querySelector('[data-level-policy]')?.getAttribute('data-level-policy')).toBe('member');
    expect(document.querySelector('[aria-label="Delete Member access"]')).toBeNull();
    await mounted!.click(row?.querySelector('button') ?? null);
    const summary = document.querySelector('[data-level-summary="member"]');
    expect(summary?.textContent).toContain('chat');
    expect(summary?.textContent).toContain('Read-only');
    expect([...document.querySelectorAll('button')].some((b) => b.textContent === 'Save changes')).toBe(false);
  });
});

describe('"<W> access" as the workspace offer', () => {
  it('names the workspace of a workspace-owned access policy only', () => {
    expect(offerWorkspaceOf(wsAccess)).toBe('ws-1');
    expect(offerWorkspaceOf({ ...wsAccess, name: 'Analysts' })).toBeNull();
    expect(offerWorkspaceOf(memberAccess)).toBeNull();
  });

  it('opens on its document: the offer is changed from the settings pages, not here', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'no' }), { status: 403 })));
    await open([wsAccess], wsScope);
    expect(document.querySelector('[data-policy="pol_w"] [data-workspace-offer]')?.textContent).toBe('workspace offer');
    await mounted!.click(document.querySelector('[data-policy="pol_w"] button'));
    await vi.waitFor(() => expect(document.querySelector('[role="tab"]')).not.toBeNull());
    const tabs = [...document.querySelectorAll('[role="tab"]')].map((t) => t.textContent);
    expect(tabs).not.toContain('Configuration');
    expect(tabs).toContain('Advanced');
    expect(document.querySelector('[aria-label="Workspace offer"]')).toBeNull();
  });
});
