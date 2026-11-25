// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { mount, type Mounted } from '@/lib/testing/mount';
import { clearPageState, readPageState, type PageKey } from '@/lib/page-state';
import { clearViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
import { usePageDraft, usePageState } from './use-page-state';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });
const signIn = (id: string) => useAuthStore.setState({ user: person(id), csrfToken: `csrf-${id}`, isAuthenticated: true });
const KEY: PageKey = { scope: 'workspace:ws-1', page: 'agents' };

let mounted: Mounted | null = null;

beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  signIn('one');
  clearPageState();
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

function Filters({ pageKey }: { pageKey: PageKey | null }) {
  const [filters, setFilters] = usePageState(pageKey, { search: '', model: 'all' });
  return createElement('input', {
    'data-search': '',
    value: filters.search,
    onChange: (event: { target: { value: string } }) =>
      setFilters((current) => ({ ...current, search: event.target.value })),
  });
}

const searchBox = () => mounted!.host.querySelector<HTMLInputElement>('[data-search]');

describe('usePageState', () => {
  it('a page left and opened again finds its filters', async () => {
    mounted = await mount(Filters, { pageKey: KEY });
    await mounted.type(searchBox(), 'abi');
    await mounted.unmount();

    mounted = await mount(Filters, { pageKey: KEY });
    expect(searchBox()!.value).toBe('abi');
  });

  it('the session read of a page load does not reset what the open page shows', async () => {
    // A user restored from storage: the API has not answered the session read yet.
    useAuthStore.setState({ user: person('one'), csrfToken: null, provider: null, isAuthenticated: true });
    mounted = await mount(Filters, { pageKey: KEY });
    await mounted.type(searchBox(), 'abi');
    // The read confirms the session and adds its provider: the same person.
    await act(async () => {
      useAuthStore.setState({ csrfToken: 'csrf-one', provider: 'idp' });
    });
    await mounted.flush();
    expect(searchBox()!.value).toBe('abi');
    await mounted.unmount();

    mounted = await mount(Filters, { pageKey: KEY });
    expect(searchBox()!.value).toBe('abi');
  });

  it('another scope starts afresh', async () => {
    mounted = await mount(Filters, { pageKey: KEY });
    await mounted.type(searchBox(), 'abi');
    await mounted.unmount();

    mounted = await mount(Filters, { pageKey: { ...KEY, scope: 'workspace:ws-2' } });
    expect(searchBox()!.value).toBe('');
  });

  it('back to the initial value keeps nothing', async () => {
    mounted = await mount(Filters, { pageKey: KEY });
    await mounted.type(searchBox(), 'abi');
    expect(readPageState(KEY)).toEqual({ search: 'abi', model: 'all' });
    await mounted.type(searchBox(), '');
    expect(readPageState(KEY)).toBeUndefined();
  });

  it('without a key it is plain component state', async () => {
    mounted = await mount(Filters, { pageKey: null });
    await mounted.type(searchBox(), 'abi');
    expect(searchBox()!.value).toBe('abi');
    await mounted.unmount();
    mounted = await mount(Filters, { pageKey: null });
    expect(searchBox()!.value).toBe('');
  });

  it('another account on the open page does not see the first one\'s state', async () => {
    mounted = await mount(Filters, { pageKey: KEY });
    await mounted.type(searchBox(), 'abi');
    await act(async () => signIn('two'));
    expect(searchBox()!.value).toBe('');
    await mounted.unmount();
    await act(async () => signIn('one'));
    mounted = await mount(Filters, { pageKey: KEY });
    expect(searchBox()!.value).toBe('');
  });
});

type Profile = { name: string; city: string };

function Form({ server }: { server: Profile | null }) {
  const draft = usePageDraft({ scope: 'account', page: 'profile' }, server);
  if (!draft.values) return createElement('p', null, 'Loading');
  return createElement(
    'form',
    null,
    createElement('input', {
      'data-name': '',
      value: draft.values.name,
      onChange: (event: { target: { value: string } }) => draft.set({ name: event.target.value }),
    }),
    createElement('span', { 'data-city': '' }, draft.values.city),
    createElement('span', { 'data-dirty': '' }, draft.dirty.join(',')),
    createElement('span', { 'data-conflicts': '' }, draft.conflicts.join(',')),
    createElement('button', { type: 'button', 'data-discard': '', onClick: draft.discard }, 'Discard'),
  );
}

/** A root the test renders again with other props (a background refresh). */
async function render(server: Profile | null): Promise<{ host: HTMLElement; root: Root }> {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(createElement(Form, { server })));
  return { host, root };
}

const text = (host: HTMLElement, selector: string) => host.querySelector(selector)?.textContent ?? '';

describe('usePageDraft', () => {
  const server: Profile = { name: 'Ada', city: 'Paris' };

  it('unsaved edits survive leaving and returning; the fields not edited follow the server', async () => {
    mounted = await mount(Form, { server });
    await mounted.type(mounted.host.querySelector('[data-name]'), 'Ada L.');
    await mounted.unmount();

    // Back later, the server changed another field meanwhile.
    mounted = await mount(Form, { server: { name: 'Ada', city: 'Lyon' } });
    expect(mounted.host.querySelector<HTMLInputElement>('[data-name]')!.value).toBe('Ada L.');
    expect(text(mounted.host, '[data-city]')).toBe('Lyon');
    expect(text(mounted.host, '[data-dirty]')).toBe('name');
    expect(text(mounted.host, '[data-conflicts]')).toBe('');
  });

  it('a background refresh does not overwrite the field being edited, and shows the conflict', async () => {
    const { host, root } = await render(server);
    const input = host.querySelector<HTMLInputElement>('[data-name]')!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    await act(async () => {
      setValue.call(input, 'Ada L.');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });

    await act(async () => root.render(createElement(Form, { server: { name: 'Ada Lovelace', city: 'Paris' } })));
    expect(host.querySelector<HTMLInputElement>('[data-name]')!.value).toBe('Ada L.');
    expect(text(host, '[data-conflicts]')).toBe('name');

    // Discard: the server's value, no conflict, nothing kept.
    await act(async () => host.querySelector<HTMLButtonElement>('[data-discard]')!.click());
    expect(host.querySelector<HTMLInputElement>('[data-name]')!.value).toBe('Ada Lovelace');
    expect(text(host, '[data-conflicts]')).toBe('');
    expect(readPageState({ scope: 'account', page: 'profile' })).toBeUndefined();
    await act(async () => root.unmount());
  });

  it('waits for the server snapshot', async () => {
    mounted = await mount(Form, { server: null });
    expect(mounted.host.textContent).toBe('Loading');
  });
});
