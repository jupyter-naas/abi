// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot, type Root } from 'react-dom/client';

// The login page beside an identity provider that is the engine's default: an
// email goes to a provider only through its organization's verified domain, and
// every other account keeps the built-in login. The default is a button.

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
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
function api(url: string, init?: RequestInit): Response {
  if (url.endsWith('/api/auth/config')) return json({ password_auth_enabled: true });
  if (url.endsWith('/api/auth/oidc/providers')) {
    return json({ providers: [{ name: 'acme', display_name: 'Acme' }], default_provider: 'acme' });
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
const login = vi.fn();

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

describe('the login page with a default identity provider', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    storage.clear();
    push.mockReset();
    signInWithProvider.mockReset();
    login.mockReset().mockResolvedValue('w1');
    fetchMock.mockReset().mockImplementation(async (url: string, init?: RequestInit) => api(String(url), init));
    vi.stubGlobal('fetch', fetchMock);
    useAuthStore.setState({ isAuthenticated: false, signInWithProvider, login });
  });
  afterEach(() => {
    act(() => root?.unmount());
    host?.remove();
    vi.unstubAllGlobals();
  });

  it('keeps the built-in login for an email no organization domain routes', async () => {
    await mount();
    type('email', 'admin@example.com');
    type('password', 'Correct-horse-9');
    await submit();

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/oidc/route'))).toBe(true);
    expect(signInWithProvider).not.toHaveBeenCalled();
    expect(login).toHaveBeenCalledWith('admin@example.com', 'Correct-horse-9');
    expect(push).toHaveBeenCalledWith('/workspace/w1/chat');
  });

  it('sends an email of a routed domain to its provider before any password', async () => {
    await mount();
    type('email', 'ada@acme.test');
    type('password', 'whatever');
    await submit();

    expect(signInWithProvider).toHaveBeenCalledWith({
      provider: 'acme',
      email: 'ada@acme.test',
      next: undefined,
    });
    expect(login).not.toHaveBeenCalled();
  });

  it('offers the default provider as a button, never as a redirect', async () => {
    await mount();
    const button = [...host.querySelectorAll('button')].find((b) => b.textContent === 'Continue with Acme');
    expect(button).toBeDefined();
    expect(signInWithProvider).not.toHaveBeenCalled();

    act(() => button!.click());
    expect(signInWithProvider).toHaveBeenCalledWith({ provider: 'acme', email: undefined, next: undefined });
  });
});
