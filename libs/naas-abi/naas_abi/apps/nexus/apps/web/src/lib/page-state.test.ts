// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  PAGE_STATE_MAX_ENTRY_BYTES,
  clearPageState,
  createPageStateRegistry,
  pageKeyId,
  readPageState,
  rebaseDraft,
  usePageStateRegistry,
  writePageState,
} from './page-state';
import { clearViewFlag, setViewFlag } from './view-flag';
import { useAuthStore, type User } from '@/stores/auth';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });
const signIn = (id: string) => useAuthStore.setState({ user: person(id), csrfToken: `csrf-${id}`, isAuthenticated: true });
const filters = { scope: 'workspace:ws-1', page: 'agents' };

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({})));
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  signIn('one');
  clearPageState();
});

afterEach(() => {
  clearViewFlag();
  vi.unstubAllGlobals();
});

describe('the page-state registry', () => {
  it('keeps a value per scope, page and detail', () => {
    const registry = createPageStateRegistry();
    registry.getState().bind('one');
    registry.getState().write(pageKeyId(filters), { search: 'abi' });
    registry.getState().write(pageKeyId({ ...filters, detail: 'abi' }), { tab: 'prompt' });
    registry.getState().write(pageKeyId({ ...filters, scope: 'workspace:ws-2' }), { search: 'other' });
    expect(registry.getState().read(pageKeyId(filters))).toEqual({ search: 'abi' });
    expect(registry.getState().read(pageKeyId({ ...filters, detail: 'abi' }))).toEqual({ tab: 'prompt' });
    expect(registry.getState().read(pageKeyId({ ...filters, scope: 'workspace:ws-2' }))).toEqual({ search: 'other' });
  });

  it('keeps nothing without an owner, and forgets everything when the owner changes', () => {
    const registry = createPageStateRegistry();
    expect(registry.getState().write(pageKeyId(filters), { search: 'abi' })).toBe(false);
    expect(registry.getState().read(pageKeyId(filters))).toBeUndefined();

    registry.getState().bind('one');
    registry.getState().write(pageKeyId(filters), { search: 'abi' });
    registry.getState().bind('two');
    expect(registry.getState().read(pageKeyId(filters))).toBeUndefined();
    // Back to the first owner: what it had is gone for good.
    registry.getState().bind('one');
    expect(registry.getState().read(pageKeyId(filters))).toBeUndefined();
  });

  it('is bounded: an entry too large is not kept, the least recently used go first', () => {
    const registry = createPageStateRegistry({ maxEntries: 3, maxTotalBytes: 1_000 });
    registry.getState().bind('one');
    const key = (n: number) => pageKeyId({ scope: 's', page: 'p', detail: String(n) });
    registry.getState().write(key(1), 'a');
    registry.getState().write(key(2), 'b');
    registry.getState().write(key(3), 'c');
    registry.getState().read(key(1)); // used again: 2 is now the oldest
    registry.getState().write(key(4), 'd');
    expect(registry.getState().read(key(2))).toBeUndefined();
    expect(registry.getState().read(key(1))).toBe('a');
    expect(registry.getState().entries.size).toBe(3);

    // Over the total: older entries make room.
    registry.getState().write(key(5), 'x'.repeat(400));
    expect(registry.getState().bytes).toBeLessThanOrEqual(1_000);
    expect(registry.getState().read(key(5))).toBe('x'.repeat(400));

    // Over the per-entry bound: not kept, and an older value under that key is dropped.
    const big = createPageStateRegistry();
    big.getState().bind('one');
    big.getState().write(key(1), 'small');
    expect(big.getState().write(key(1), 'x'.repeat(PAGE_STATE_MAX_ENTRY_BYTES))).toBe(false);
    expect(big.getState().read(key(1))).toBeUndefined();
  });

  it('does not keep what is not plain data', () => {
    const registry = createPageStateRegistry();
    registry.getState().bind('one');
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    expect(registry.getState().write(pageKeyId(filters), cyclic)).toBe(false);
    expect(registry.getState().write(pageKeyId(filters), undefined)).toBe(false);
  });
});

describe('the registry follows the session', () => {
  it('another account never reads what the first one left, nor after coming back', () => {
    writePageState(filters, { search: 'abi' });
    expect(readPageState(filters)).toEqual({ search: 'abi' });

    signIn('two');
    expect(readPageState(filters)).toBeUndefined();
    writePageState(filters, { search: 'two' });

    signIn('one');
    expect(readPageState(filters)).toBeUndefined();
  });

  it('sign-out forgets everything', () => {
    writePageState(filters, { search: 'abi' });
    useAuthStore.getState().logout();
    expect(usePageStateRegistry.getState().owner).toBeNull();
    expect(usePageStateRegistry.getState().entries.size).toBe(0);
  });

  it('keeps nothing during View as', () => {
    writePageState(filters, { search: 'abi' });
    setViewFlag({ workspaceId: 'ws-1', returnTo: null }, Date.now() + 60_000);
    expect(readPageState(filters)).toBeUndefined();
    expect(writePageState(filters, { search: 'viewed' })).toBe(false);
    expect(usePageStateRegistry.getState().entries.size).toBe(0);

    clearViewFlag();
    expect(readPageState(filters)).toBeUndefined();
  });
});

describe('rebaseDraft: a server snapshot under a draft', () => {
  const server = { name: 'Acme', website: 'acme.test', city: 'Paris' };

  it('without a draft, the values are the server', () => {
    expect(rebaseDraft(null, server)).toEqual({ draft: null, values: server, dirty: [], conflicts: [] });
  });

  it('a refresh updates the fields not edited and keeps the edited ones', () => {
    const draft = { base: server, values: { ...server, name: 'Acme Corp' }, conflicts: [] };
    const fresh = { ...server, city: 'Lyon' };
    const result = rebaseDraft(draft, fresh);
    expect(result.values).toEqual({ name: 'Acme Corp', website: 'acme.test', city: 'Lyon' });
    expect(result.dirty).toEqual(['name']);
    expect(result.conflicts).toEqual([]);
    expect(result.draft?.base).toEqual(fresh);
  });

  it('a field edited here and changed elsewhere is a conflict, kept until it is resolved', () => {
    const draft = { base: server, values: { ...server, name: 'Acme Corp' }, conflicts: [] };
    const fresh = { ...server, name: 'Acme SAS' };
    const first = rebaseDraft(draft, fresh);
    expect(first.values.name).toBe('Acme Corp');
    expect(first.conflicts).toEqual(['name']);

    // The same snapshot again (a second refresh): still visible.
    const again = rebaseDraft(first.draft, fresh);
    expect(again.conflicts).toEqual(['name']);

    // Typed back to what the server has: no longer edited, no conflict, no draft.
    const settled = rebaseDraft({ ...again.draft!, values: { ...again.draft!.values, name: 'Acme SAS' } }, fresh);
    expect(settled).toEqual({ draft: null, values: fresh, dirty: [], conflicts: [] });
  });

  it('the server reaching the edited value is no conflict', () => {
    const draft = { base: server, values: { ...server, name: 'Acme Corp' }, conflicts: [] };
    expect(rebaseDraft(draft, { ...server, name: 'Acme Corp' }).draft).toBeNull();
  });
});
