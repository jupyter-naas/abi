// @vitest-environment jsdom
/**
 * The pages of the person's own say "Private to <name>" in a view and ask the server for nothing:
 * chat history, My Drive, coding environments, the workspace's secrets, the account's API keys.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { useAuthStore } from '@/stores/auth';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { PrivateGate, PrivateToPerson } from './private-to-person';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
// The pages' own content is not under test: a marker stands in, and says when it was rendered.
vi.mock('@/components/settings/secrets-panel', () => ({ SecretsPanel: () => createElement('p', { 'data-secrets': '' }, 'secrets') }));
vi.mock('@/app/account/api-keys/api-keys', () => ({ default: () => createElement('p', { 'data-keys': '' }, 'keys') }));

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-alpha' }),
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/workspace/ws-alpha/code/workspaces',
}));

import CodeWorkspacesPage from '@/app/workspace/[workspaceId]/code/workspaces/page';
import SecretsPage from '@/app/workspace/[workspaceId]/settings/secrets/page';
import ApiKeysPage from '@/app/account/api-keys/page';

const VIEW = {
  person: { id: 'iam_carol', name: 'Carol' },
  workspace: { id: 'ws-alpha', name: 'Alpha' },
  ends_at: new Date(Date.now() + 900_000).toISOString(),
  groups_from: null,
};

let mounted: Mounted | null = null;
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetcher = vi.fn(async () => new Response('[]', { status: 200 }));
  vi.stubGlobal('fetch', fetcher);
  useAuthStore.setState({ view: null, csrfToken: 'csrf', isAuthenticated: true });
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  useAuthStore.setState({ view: null, csrfToken: null, isAuthenticated: false });
  vi.unstubAllGlobals();
});

const inView = () => useAuthStore.setState({ view: VIEW });
const text = () => mounted!.host.textContent ?? '';

describe('the placeholder', () => {
  it('names the person', async () => {
    inView();
    mounted = await mount(PrivateToPerson, { what: 'My Drive' });
    expect(text()).toContain('Private to Carol');
    expect(text()).toContain('My Drive');
  });

  it('renders nothing outside a view', async () => {
    mounted = await mount(PrivateToPerson, {});
    expect(text()).toBe('');
  });

  it('the gate shows its page outside a view and the placeholder, not the page, in one', async () => {
    mounted = await mount(PrivateGate, { children: createElement('p', { 'data-page': '' }, 'page') });
    expect(mounted.host.querySelector('[data-page]')).not.toBeNull();
    await mounted.unmount();
    inView();
    mounted = await mount(PrivateGate, { children: createElement('p', { 'data-page': '' }, 'page') });
    expect(mounted.host.querySelector('[data-page]')).toBeNull();
    expect(text()).toContain('Private to Carol');
  });
});

describe('the private pages', () => {
  it('the workspace’s secrets', async () => {
    mounted = await mount(SecretsPage, {});
    expect(mounted.host.querySelector('[data-secrets]')).not.toBeNull();
    await mounted.unmount();
    inView();
    mounted = await mount(SecretsPage, {});
    expect(mounted.host.querySelector('[data-secrets]')).toBeNull();
    expect(text()).toContain('Private to Carol');
  });

  it('the account’s API keys', async () => {
    mounted = await mount(ApiKeysPage, {});
    expect(mounted.host.querySelector('[data-keys]')).not.toBeNull();
    await mounted.unmount();
    inView();
    mounted = await mount(ApiKeysPage, {});
    expect(mounted.host.querySelector('[data-keys]')).toBeNull();
    expect(text()).toContain('Private to Carol');
  });
});

describe('the coding environments', () => {
  it('are private to the person in a view, and none is asked for', async () => {
    inView();
    mounted = await mount(CodeWorkspacesPage, {});
    await mounted.flush();
    expect(text()).toContain('Private to Carol');
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe('what asks the server for the person’s own', () => {
  it('My Drive is not listed', async () => {
    inView();
    useFilesStore.setState({ activeSource: 'my-drive', files: [{ name: 'viewers.txt' } as never] });
    await useFilesStore.getState().fetchFiles('');
    expect(fetcher).not.toHaveBeenCalled();
    expect(useFilesStore.getState().files).toEqual([]);
  });

  it('the workspace’s own drive still is', async () => {
    inView();
    useFilesStore.setState({ activeSource: 'workspace' });
    await useFilesStore.getState().fetchFiles('ws-alpha', { workspaceId: 'ws-alpha' });
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('/api/files/'))).toBe(true);
  });

  it('the conversations are not listed', async () => {
    inView();
    await useWorkspaceStore.getState().syncWorkspaceConversations('ws-alpha');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('the conversations are listed outside a view', async () => {
    await useWorkspaceStore.getState().syncWorkspaceConversations('ws-alpha');
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('/api/chat/conversations'))).toBe(true);
  });
});
