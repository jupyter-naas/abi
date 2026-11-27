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
// The picker is a modal, rendered in document.body.
const dialog = () => document.querySelector('[role="dialog"]');
const select = () => document.querySelector('[role="dialog"] select') as HTMLSelectElement;
const dialogButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')].find((b) => b.textContent === label);

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
    const fetcher = vi.fn(
      async () => new Response(JSON.stringify({ workspaces: [ALPHA], reason: null, detail: null }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetcher);
    mounted = await mount(ViewAsControl, { personId: 'iam carol', name: 'Carol', workspaceId: null });
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
    await mounted.flush();
    expect(String(fetcher.mock.calls[0][0])).toBe(
      'https://api.example.test/api/iam/view-as/eligibility?principal_id=iam%20carol',
    );
    expect(button()?.textContent).toContain('View as Carol');
  });
});

describe('a View as with no workspace to view', () => {
  it('is shown disabled, saying why, for a person who has not signed in yet', async () => {
    mounted = await open([], { viewable: () => Promise.resolve({ workspaces: [], reason: 'not_signed_in' }) });
    expect(button()?.disabled).toBe(true);
    expect(button()?.textContent).toContain('View as Carol');
    // A no-entry box (cursor in CSS) with the reason in its tooltip, described for screen readers.
    const box = mounted.host.querySelector('[data-view-as-control][data-unavailable]')!;
    expect(box.classList.contains('access-view-as-unavailable')).toBe(true);
    expect(box.getAttribute('aria-describedby')).toBe('view-as-unavailable');
    expect(mounted.host.querySelector('[role="tooltip"]')?.textContent).toBe(
      'Carol has not signed in to Nexus yet: a view needs their first sign-in.',
    );
  });

  it('says IAM’s words when IAM refuses each workspace', async () => {
    mounted = await open([], {
      viewable: () => Promise.resolve({ workspaces: [], reason: 'refused', detail: 'Carol holds something you do not' }),
    });
    expect(mounted.host.querySelector('[role="tooltip"]')?.textContent).toBe('Carol holds something you do not');
  });

  it('opens nothing', async () => {
    mounted = await open([], { viewable: () => Promise.resolve({ workspaces: [], reason: 'no_workspace' }) });
    await mounted.click(button());
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });
});

describe('the picker, in a modal', () => {
  it('opens on click, not in the page, and closes with Cancel', async () => {
    mounted = await open([ALPHA, BRAVO]);
    expect(dialog()).toBeNull();
    await mounted.click(button());
    expect(dialog()?.textContent).toContain('View as Carol');
    expect(mounted.host.querySelector('select')).toBeNull();
    await mounted.click(dialogButton('Cancel')!);
    expect(dialog()).toBeNull();
  });

  it('lists the workspaces with their organization, the first one chosen', async () => {
    mounted = await open([ALPHA, BRAVO]);
    await mounted.click(button());
    expect([...select().options].map((o) => o.textContent)).toEqual(['Alpha · Acme', 'Bravo']);
    expect(select().value).toBe('ws-alpha');
  });

  it('preselects the page’s workspace', async () => {
    mounted = await open([ALPHA, BRAVO], { workspaceId: 'ws-bravo' });
    await mounted.click(button());
    expect(select().value).toBe('ws-bravo');
  });

  it('keeps the first when the page’s workspace is not offered', async () => {
    mounted = await open([ALPHA, BRAVO], { workspaceId: 'ws-elsewhere' });
    await mounted.click(button());
    expect(select().value).toBe('ws-alpha');
  });

  it('starts the view in the workspace picked, from this page', async () => {
    const start = vi.fn().mockResolvedValue(undefined);
    mounted = await open([ALPHA, BRAVO], { start, returnTo: () => '/settings/roles?section=people&person=iam_carol' });
    await mounted.click(button());
    await mounted.select(select(), 'ws-bravo');
    await mounted.click(dialogButton('Start')!);
    expect(start).toHaveBeenCalledWith('iam_carol', 'ws-bravo', '/settings/roles?section=people&person=iam_carol');
  });

  it('says why IAM refused', async () => {
    const start = vi.fn().mockRejectedValue(new Error('Carol holds something you do not'));
    mounted = await open([ALPHA], { start });
    await mounted.click(button());
    await mounted.click(dialogButton('Start')!);
    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent).toBe('Carol holds something you do not');
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
