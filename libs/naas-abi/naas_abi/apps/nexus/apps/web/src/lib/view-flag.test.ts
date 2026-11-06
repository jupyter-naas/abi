// @vitest-environment jsdom
/**
 * The browser keeps nothing during a view ("View as"): the flag that says a view runs, the script
 * that swaps the browser's storage before any store exists, and the two storages the persisted
 * stores write through.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { createDeferredStorage, discardDeferredStorage, flushDeferredStorage } from './deferred-storage';
import { getSafeStorage, resetSafeStorageForTests } from './safe-storage';
import {
  VIEW_FLAG_COOKIE,
  clearViewFlag,
  parseViewFlag,
  readViewFlag,
  setViewFlag,
  viewFlagActive,
  viewFlagFromCookies,
} from './view-flag';
import { VIEW_STORAGE_GUARD } from './view-storage-guard';
import { middleware } from '../middleware';

const ENDS = () => new Date(Date.now() + 15 * 60_000).toISOString();

beforeEach(() => {
  clearViewFlag();
  resetSafeStorageForTests();
});
afterEach(() => {
  clearViewFlag();
  discardDeferredStorage();
  vi.useRealTimers();
});

describe('the view flag', () => {
  it('is raised until the view ends, and holds the workspace and the page to return to', () => {
    expect(viewFlagActive()).toBe(false);
    setViewFlag({ workspaceId: 'ws-1', returnTo: '/settings/roles?section=people&person=usr_c' }, ENDS());
    expect(viewFlagActive()).toBe(true);
    expect(readViewFlag()).toEqual({ workspaceId: 'ws-1', returnTo: '/settings/roles?section=people&person=usr_c' });
    clearViewFlag();
    expect(viewFlagActive()).toBe(false);
  });

  it('expires with the view', () => {
    const written: string[] = [];
    const jar = vi.spyOn(document, 'cookie', 'set').mockImplementation((value) => void written.push(value));
    setViewFlag({ workspaceId: 'ws-1', returnTo: null }, new Date(1_000_000 + 90_000), 1_000_000);
    jar.mockRestore();
    expect(written).toHaveLength(1);
    expect(written[0]).toContain(`${VIEW_FLAG_COOKIE}=`);
    expect(written[0]).toContain('max-age=90');
    expect(written[0]).toContain('path=/');
  });

  it('never returns to another origin', () => {
    expect(parseViewFlag(JSON.stringify({ workspaceId: 'w', returnTo: '//evil.example/x' }))?.returnTo).toBeNull();
    expect(parseViewFlag(JSON.stringify({ workspaceId: 'w', returnTo: 'https://evil.example' }))?.returnTo).toBeNull();
    expect(parseViewFlag(JSON.stringify({ workspaceId: 'w', returnTo: '/ok' }))?.returnTo).toBe('/ok');
  });

  it('counts as a view even when its value is unreadable', () => {
    expect(viewFlagFromCookies(`a=1; ${VIEW_FLAG_COOKIE}=%7Bnot-json; b=2`)).toEqual({ workspaceId: '', returnTo: null });
    expect(viewFlagFromCookies('a=1; b=2')).toBeNull();
  });
});

describe('the storage guard script', () => {
  function run(cookie: string) {
    const win: Record<string, unknown> = {};
    const attrs: Record<string, string> = {};
    const doc = { cookie, documentElement: { setAttribute: (k: string, v: string) => (attrs[k] = v) } };
    new Function('window', 'document', VIEW_STORAGE_GUARD)(win, doc);
    return { win, attrs };
  }

  it('does nothing without a view', () => {
    const { win, attrs } = run('a=1');
    expect(win.localStorage).toBeUndefined();
    expect(attrs).toEqual({});
  });

  it('puts an empty in-memory storage in place of the browser’s during a view', () => {
    const { win, attrs } = run(`${VIEW_FLAG_COOKIE}=%7B%7D`);
    const local = win.localStorage as Storage;
    const session = win.sessionStorage as Storage;
    expect(attrs['data-view-as']).toBe('');
    expect(local.getItem('nexus-workspace-storage')).toBeNull();
    local.setItem('k', 'v');
    expect(local.getItem('k')).toBe('v');
    expect(session.getItem('k')).toBeNull();
    local.removeItem('k');
    expect(local.length).toBe(0);
  });

  it('keeps the browser’s own storage aside, for a sign-out to clear', () => {
    const real = { removeItem: vi.fn() };
    const win: Record<string, unknown> = { localStorage: real };
    const doc = { cookie: `${VIEW_FLAG_COOKIE}=%7B%7D`, documentElement: { setAttribute: () => undefined } };
    new Function('window', 'document', VIEW_STORAGE_GUARD)(win, doc);
    expect(win.localStorage).not.toBe(real);
    expect(win.__nexusRealLocalStorage).toBe(real);
  });
});

describe('the persisted stores during a view', () => {
  const backend = () => {
    const data = new Map<string, string>([['nexus-agents', JSON.stringify({ state: { viewers: 'own' } })]]);
    return {
      data,
      api: {
        getItem: vi.fn((k: string) => data.get(k) ?? null),
        setItem: vi.fn((k: string, v: string) => void data.set(k, v)),
        removeItem: vi.fn((k: string) => void data.delete(k)),
      },
    };
  };

  it('the deferred storage reads nothing the browser kept and writes nothing', () => {
    vi.useFakeTimers();
    const { data, api } = backend();
    setViewFlag({ workspaceId: 'w', returnTo: null }, ENDS());
    const storage = createDeferredStorage<{ n: number }>(() => api, 10);
    expect(storage.getItem('nexus-agents')).toBeNull();
    storage.setItem('nexus-workspace-storage', { state: { n: 1 } });
    vi.advanceTimersByTime(50);
    flushDeferredStorage();
    expect(api.setItem).not.toHaveBeenCalled();
    expect(data.has('nexus-workspace-storage')).toBe(false);
  });

  it('the deferred storage works as before outside a view', () => {
    const { api } = backend();
    const storage = createDeferredStorage<{ viewers: string }>(() => api, 10);
    expect(storage.getItem('nexus-agents')).toEqual({ state: { viewers: 'own' } });
  });

  it('the auth store’s storage is memory, whatever the browser allows', () => {
    setViewFlag({ workspaceId: 'w', returnTo: null }, ENDS());
    localStorage.setItem('nexus-auth', 'viewer');
    const storage = getSafeStorage();
    expect(storage.backend).toBe('memory');
    expect(storage.getItem('nexus-auth')).toBeNull();
    storage.setItem('nexus-auth', 'person');
    expect(localStorage.getItem('nexus-auth')).toBe('viewer');
    localStorage.removeItem('nexus-auth');
  });
});

describe('the middleware during a view', () => {
  const requestFor = (pathname: string, cookies: Record<string, string> = {}) => {
    const req = new NextRequest(`https://nexus.example.com${pathname}`);
    for (const [k, v] of Object.entries(cookies)) req.cookies.set(k, v);
    return req;
  };
  const flag = encodeURIComponent(JSON.stringify({ workspaceId: 'ws-view', returnTo: null }));

  it('does not set the last-workspace cookie in a view', () => {
    const response = middleware(requestFor('/workspace/ws-view/chat', { 'nexus-auth-flag': 'true', [VIEW_FLAG_COOKIE]: flag }));
    expect(response.cookies.get('nexus-last-workspace')).toBeUndefined();
  });

  it('sets it as before without a view', () => {
    const response = middleware(requestFor('/workspace/ws-1/chat', { 'nexus-auth-flag': 'true' }));
    expect(response.cookies.get('nexus-last-workspace')?.value).toBe('ws-1');
  });

  it('lands in the viewed workspace, not the viewer’s last one', () => {
    const response = middleware(
      requestFor('/', { 'nexus-auth-flag': 'true', 'nexus-last-workspace': 'viewers-own', [VIEW_FLAG_COOKIE]: flag }),
    );
    expect(response.headers.get('location')).toContain('/workspace/ws-view/chat');
  });
});
