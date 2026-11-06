// @vitest-environment jsdom
/**
 * "View as <name>" on a person's page: shown when IAM accepts a view in at least one workspace,
 * a picker of them with this page's workspace preselected, Start.
 */
import { existsSync } from 'node:fs';
import path from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { beginView, viewLanding } from '@/lib/view-as';
import { clearViewFlag, readViewFlag } from '@/lib/view-flag';
import { navigation, type ViewableWorkspace } from '@/lib/view-model';
import { useAuthStore } from '@/stores/auth';
import { ViewAsControl } from './view-as-control';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

const ALPHA: ViewableWorkspace = { id: 'ws-alpha', name: 'Alpha', organization: { id: 'acme', name: 'Acme' } };
const BRAVO: ViewableWorkspace = { id: 'ws-bravo', name: 'Bravo', organization: null };

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  clearViewFlag();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const open = (workspaces: ViewableWorkspace[], over: Partial<Parameters<typeof ViewAsControl>[0]> = {}) =>
  mount(ViewAsControl, {
    personId: 'iam_carol',
    name: 'Carol',
    workspaceId: null,
    viewable: () => Promise.resolve(workspaces),
    ...over,
  });
const button = () => mounted!.host.querySelector('button');

describe('the View as button', () => {
  it('is not shown when no workspace may be viewed', async () => {
    mounted = await open([]);
    expect(mounted.host.textContent).toBe('');
  });

  it('is not shown when the list cannot be read', async () => {
    mounted = await open([], { viewable: () => Promise.reject(new Error('down')) });
    expect(mounted.host.textContent).toBe('');
  });

  it('is shown, with the person’s name, when there is one', async () => {
    mounted = await open([ALPHA]);
    expect(button()?.textContent).toContain('View as Carol');
  });

  it('asks for the person’s workspaces by their IAM id', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify([ALPHA]), { status: 200 }));
    vi.stubGlobal('fetch', fetcher);
    mounted = await mount(ViewAsControl, { personId: 'iam carol', name: 'Carol', workspaceId: null });
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
    await mounted.flush();
    expect(String(fetcher.mock.calls[0][0])).toBe(
      'https://api.example.test/api/iam/view-as/workspaces?principal_id=iam%20carol',
    );
    expect(button()?.textContent).toContain('View as Carol');
  });
});

describe('the picker', () => {
  it('lists the workspaces with their organization, the first one chosen', async () => {
    mounted = await open([ALPHA, BRAVO]);
    await mounted.click(button());
    const select = mounted.host.querySelector('select') as HTMLSelectElement;
    expect([...select.options].map((o) => o.textContent)).toEqual(['Alpha · Acme', 'Bravo']);
    expect(select.value).toBe('ws-alpha');
  });

  it('preselects the page’s workspace', async () => {
    mounted = await open([ALPHA, BRAVO], { workspaceId: 'ws-bravo' });
    await mounted.click(button());
    expect((mounted.host.querySelector('select') as HTMLSelectElement).value).toBe('ws-bravo');
  });

  it('keeps the first when the page’s workspace is not offered', async () => {
    mounted = await open([ALPHA, BRAVO], { workspaceId: 'ws-elsewhere' });
    await mounted.click(button());
    expect((mounted.host.querySelector('select') as HTMLSelectElement).value).toBe('ws-alpha');
  });

  it('starts the view in the workspace picked, from this page', async () => {
    const start = vi.fn().mockResolvedValue(undefined);
    mounted = await open([ALPHA, BRAVO], { start, returnTo: () => '/settings/roles?section=people&person=iam_carol' });
    await mounted.click(button());
    await mounted.select(mounted.host.querySelector('select'), 'ws-bravo');
    const startButton = [...mounted.host.querySelectorAll('button')].find((b) => b.textContent === 'Start');
    await mounted.click(startButton!);
    expect(start).toHaveBeenCalledWith('iam_carol', 'ws-bravo', '/settings/roles?section=people&person=iam_carol');
  });

  it('says why IAM refused', async () => {
    const start = vi.fn().mockRejectedValue(new Error('Carol holds something you do not'));
    mounted = await open([ALPHA], { start });
    await mounted.click(button());
    const startButton = [...mounted.host.querySelectorAll('button')].find((b) => b.textContent === 'Start');
    await mounted.click(startButton!);
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toBe('Carol holds something you do not');
  });
});

describe('where a view lands', () => {
  it('is the workspace Home: a page every workspace has, never the bare workspace address', () => {
    expect(viewLanding('ws-alpha')).toBe('/workspace/ws-alpha/home');
    expect(viewLanding('ws a/b')).toBe('/workspace/ws%20a%2Fb/home');
    // `/workspace/<id>` has no page: a view that landed there would open a 404.
    const root = path.join(process.cwd(), 'src/app/workspace/[workspaceId]');
    expect(existsSync(path.join(root, 'home/page.tsx'))).toBe(true);
    expect(existsSync(path.join(root, 'page.tsx'))).toBe(false);
  });
});

describe('starting for real', () => {
  it('posts, raises the flag, then loads the workspace in the browser', async () => {
    useAuthStore.setState({ csrfToken: 'csrf' });
    const go = vi.spyOn(navigation, 'go').mockImplementation(() => undefined);
    const fetcher = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            person: { id: 'iam_carol', name: 'Carol' },
            workspace: { id: 'ws-alpha', name: 'Alpha' },
            ends_at: new Date(Date.now() + 900_000).toISOString(),
            groups_from: null,
          }),
          { status: 200 },
        ),
    );
    vi.stubGlobal('fetch', fetcher);
    await beginView('iam_carol', 'ws-alpha', '/settings/roles?section=people&person=iam_carol');
    useAuthStore.setState({ csrfToken: null });
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe('https://api.example.test/api/iam/view-as');
    expect(JSON.parse(init.body)).toEqual({ principal_id: 'iam_carol', workspace_id: 'ws-alpha' });
    expect(readViewFlag()).toEqual({ workspaceId: 'ws-alpha', returnTo: '/settings/roles?section=people&person=iam_carol' });
    expect(go).toHaveBeenCalledWith('/workspace/ws-alpha/home');
  });

  it('loads nothing and raises no flag when the server refuses', async () => {
    const go = vi.spyOn(navigation, 'go').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'no' }), { status: 403 })));
    await expect(beginView('iam_carol', 'ws-alpha', '/x')).rejects.toThrow('no');
    expect(readViewFlag()).toBeNull();
    expect(go).not.toHaveBeenCalled();
  });
});
