// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot, type Root } from 'react-dom/client';

// The login page is single sign-on only: an email goes to the provider its
// organization's verified domain names, else the engine's default provider, and
// every provider is a button.

const push = vi.fn();
let search = '';
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    React.createElement('a', { href }, children),
}));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.test' }));
const storage = new Map<string, string>();
vi.mock('@/lib/safe-storage', () => ({
  getSafeStorage: () => ({
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => void storage.set(key, value),
    removeItem: (key: string) => void storage.delete(key),
  }),
}));

const { useAuthStore } = await import('@/stores/auth');
const { default: LoginForm } = await import('./login-form');

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

// The API as it answers with `acme` configured as the default provider.
let providerList: { name: string; display_name: string }[] = [{ name: 'acme', display_name: 'Acme' }];
let defaultProvider: string | null = 'acme';
function api(url: string, init?: RequestInit): Response {
  if (url.endsWith('/api/auth/oidc/providers')) {
    return json({ providers: providerList, default_provider: defaultProvider });
  }
  if (url.endsWith('/api/auth/oidc/route')) {
    const { email } = JSON.parse(String(init?.body));
    return json({ provider: email.endsWith('@acme.test') ? 'acme' : null });
  }
  return new Response('not found', { status: 404 });
}

let root: Root;
let host: HTMLDivElement;
const signInWithProvider = vi.fn();

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function mount() {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(React.createElement(LoginForm)));
  await settle();
}

function type(id: string, value: string) {
  const input = host.querySelector<HTMLInputElement>(`#${id}`)!;
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

async function submit() {
  const form = host.querySelector('form')!;
  await act(async () => {
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
  await settle();
}

describe('the login page', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    storage.clear();
    push.mockReset();
    search = '';
    providerList = [{ name: 'acme', display_name: 'Acme' }];
    defaultProvider = 'acme';
    signInWithProvider.mockReset();
    fetchMock.mockReset().mockImplementation(async (url: string, init?: RequestInit) => api(String(url), init));
    vi.stubGlobal('fetch', fetchMock);
    useAuthStore.setState({ isAuthenticated: false, signInWithProvider });
  });
  afterEach(() => {
    act(() => root?.unmount());
    host?.remove();
    vi.unstubAllGlobals();
  });

  it('has no password, code or account-creation field, and calls no retired endpoint', async () => {
    await mount();
    expect(host.querySelector('#password')).toBeNull();
    expect(host.querySelector('#otp')).toBeNull();
    expect(host.textContent).not.toMatch(/password|magic link|create account/i);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      'https://api.test/api/auth/oidc/providers',
    ]);
  });

  it('sends an email of a routed domain to its provider', async () => {
    providerList = [
      { name: 'acme', display_name: 'Acme' },
      { name: 'builtin', display_name: 'ABI' },
    ];
    defaultProvider = 'builtin';
    await mount();
    type('email', 'ada@acme.test');
    await submit();

    expect(signInWithProvider).toHaveBeenCalledWith({
      provider: 'acme',
      email: 'ada@acme.test',
      next: undefined,
    });
  });

  it('sends any other email to the default provider', async () => {
    providerList = [
      { name: 'acme', display_name: 'Acme' },
      { name: 'builtin', display_name: 'ABI' },
    ];
    defaultProvider = 'builtin';
    await mount();
    type('email', 'admin@example.com');
    await submit();

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/oidc/route'))).toBe(true);
    expect(signInWithProvider).toHaveBeenCalledWith({
      provider: 'builtin',
      email: 'admin@example.com',
      next: undefined,
    });
  });

  it('asks to pick a provider when none routes and there is no default', async () => {
    providerList = [
      { name: 'acme', display_name: 'Acme' },
      { name: 'builtin', display_name: 'ABI' },
    ];
    defaultProvider = null;
    await mount();
    type('email', 'admin@example.com');
    await submit();

    expect(signInWithProvider).not.toHaveBeenCalled();
    expect(host.textContent).toContain('Choose how to sign in');
  });

  it('honours the provider an invitation link names, skipping the domain routing', async () => {
    providerList = [
      { name: 'acme', display_name: 'Acme' },
      { name: 'builtin', display_name: 'ABI' },
    ];
    search = 'provider=builtin&email=bob%40acme.test&redirect=%2Fworkspace%2Fw';
    await mount();
    await submit();

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/oidc/route'))).toBe(false);
    expect(signInWithProvider).toHaveBeenCalledWith({
      provider: 'builtin',
      email: 'bob@acme.test',
      next: '/workspace/w',
    });
  });

  it('offers every provider as a button, never as a redirect', async () => {
    await mount();
    const button = [...host.querySelectorAll('button')].find((b) => b.textContent === 'Continue with Acme');
    expect(button).toBeDefined();
    expect(signInWithProvider).not.toHaveBeenCalled();

    act(() => button!.click());
    expect(signInWithProvider).toHaveBeenCalledWith({ provider: 'acme', email: undefined, next: undefined });
  });

  it('says so when no identity provider is configured', async () => {
    providerList = [];
    defaultProvider = null;
    await mount();
    expect(host.textContent).toContain('No identity provider is configured');
    expect(host.querySelector('form')).toBeNull();
  });

  it('refuses an address that is not an email', async () => {
    await mount();
    type('email', 'not-an-email');
    await submit();
    expect(signInWithProvider).not.toHaveBeenCalled();
    expect(host.textContent).toContain('Enter a valid email address');
  });
});
