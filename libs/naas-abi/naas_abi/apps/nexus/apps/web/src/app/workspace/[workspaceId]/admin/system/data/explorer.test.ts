// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../system-render';
import type { DataApi, Result } from './data-api';
import type { AuditEntry, ResourceDetail, ResourceEntry, ResourceServiceInfo } from './data-types';
import { DataExplorer } from './explorer';

const replace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  usePathname: () => '/workspace/w1/admin/system',
  useSearchParams: () => new URLSearchParams('tab=data'),
}));

const caps = (overrides: Partial<ResourceServiceInfo['capabilities']> = {}) => ({
  browse: true,
  lookup: false,
  create: true,
  reveal: false,
  write_format: '',
  search: false,
  ...overrides,
});

const SERVICES: ResourceServiceInfo[] = [
  { name: 'object_storage', available: true, reason: '', capabilities: caps() },
  { name: 'secret', available: true, reason: '', capabilities: caps({ reveal: true }) },
  { name: 'vector_store', available: false, reason: 'not configured', capabilities: caps({ browse: false }) },
];

/** In-memory service data: ids are paths; secrets are masked until revealed. */
function fakeApi() {
  const data: Record<string, Record<string, string>> = {
    object_storage: { 'docs/a.json': '{"title": "Hello", "n": 1}', 'docs/b.txt': 'bye', 'top.txt': 'top' },
    secret: { OPENAI_API_KEY: 'sk-123', PUBLIC_HOST: 'example.org' },
  };
  const masked = (s: string) => s === 'secret';
  const entry = (service: string, id: string): ResourceEntry => {
    const item = id in data[service];
    return {
      id,
      name: id.split('/').pop() ?? id,
      kind: item ? 'item' : 'container',
      actions: item ? (masked(service) ? ['read', 'reveal', 'write', 'delete'] : ['read', 'download', 'write', 'delete']) : [],
      size: item && !masked(service) ? data[service][id].length : null,
      modified: item ? '2026-10-02T10:00:00Z' : null,
      attributes: {},
    };
  };
  const detail = (service: string, id: string, reveal: boolean): ResourceDetail => ({
    entry: entry(service, id),
    content:
      masked(service) && !reveal
        ? { encoding: 'masked', text: null, size: null, truncated: false }
        : { encoding: 'text', text: data[service][id], size: data[service][id].length, truncated: false },
  });
  const ok = <T,>(value: T): Promise<Result<T>> => Promise.resolve({ ok: true, data: value });
  const audit: AuditEntry[] = [];
  const api: DataApi = {
    services: vi.fn(() => ok({ services: SERVICES })),
    list: vi.fn((service: string, parent: string) => {
      const prefix = parent ? `${parent}/` : '';
      const ids = [
        ...new Set(
          Object.keys(data[service])
            .filter((id) => id.startsWith(prefix))
            .map((id) => prefix + id.slice(prefix.length).split('/')[0]),
        ),
      ].sort();
      return ok({ parent, entries: ids.map((id) => entry(service, id)), next_cursor: null, listable: true });
    }),
    read: vi.fn((service: string, id: string) =>
      id in data[service] ? ok(detail(service, id, false)) : Promise.resolve({ ok: false as const, status: 404, reason: 'not found' }),
    ),
    reveal: vi.fn((service: string, id: string) => {
      audit.unshift({ at: '2026-10-02T10:01:00Z', actor_id: 'u1', actor: 'Ada', service, operation: 'reveal', resource_id: id, phase: 'succeeded', error: '' });
      return ok(detail(service, id, true));
    }),
    download: vi.fn((service: string, id: string) => ok(new Blob([data[service][id]]))),
    write: vi.fn((service: string, id: string, body: Blob | string, confirm?: string) => {
      if (id in data[service] && confirm !== id) {
        return Promise.resolve({ ok: false as const, status: 409, reason: 'confirm', confirm: id, operation: 'replace' });
      }
      data[service][id] = String(body);
      return ok(entry(service, id));
    }),
    remove: vi.fn((service: string, id: string, confirm: string) => {
      if (confirm !== id) return Promise.resolve({ ok: false as const, status: 409, reason: 'confirm', confirm: id });
      delete data[service][id];
      return ok(null);
    }),
    history: vi.fn((service: string, id: string) => ok({ entries: audit.filter((a) => a.service === service && a.resource_id === id) })),
    recent: vi.fn(() => ok({ entries: audit })),
  };
  return { api, data };
}

let mounted: Mounted | null = null;
beforeEach(() => replace.mockClear());
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const q = (selector: string) => document.querySelector(selector);
const text = () => document.body.textContent ?? '';
const button = (label: string, root: ParentNode = document) =>
  ([...root.querySelectorAll('button')].find((b) => b.textContent?.trim() === label) as HTMLButtonElement | undefined) ?? null;
const rows = () => [...document.querySelectorAll('[data-entry]')].map((r) => r.getAttribute('data-entry'));

async function open(api: DataApi) {
  mounted = await mount(DataExplorer, { api });
  await mounted.flush();
  await mounted.flush();
}

async function key(k: string, init: KeyboardEventInit = {}) {
  window.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, ...init }));
  await mounted!.flush();
}

describe('DataExplorer', () => {
  it('groups services, says why one is off and opens the first available', async () => {
    const { api } = fakeApi();
    await open(api);

    expect(q('[data-data-service="object_storage"]')?.getAttribute('aria-current')).toBe('page');
    expect(q('[data-data-service="vector_store"]')?.getAttribute('aria-disabled')).toBe('true');
    expect(text()).toContain('Storage');
    expect(rows()).toEqual(['docs', 'top.txt']);
  });

  it('browses into containers, names the path and goes back up', async () => {
    const { api } = fakeApi();
    await open(api);

    await mounted!.click(q('[data-entry="docs"]'));
    await mounted!.flush();
    expect(rows()).toEqual(['docs/a.json', 'docs/b.txt']);
    expect([...document.querySelectorAll('.data-crumb')].map((c) => c.textContent)).toEqual(['Object storage', 'docs']);

    await key('Backspace');
    expect(rows()).toEqual(['docs', 'top.txt']);
  });

  it('previews JSON as a tree and lists the entry details', async () => {
    const { api } = fakeApi();
    await open(api);
    await mounted!.click(q('[data-entry="docs"]'));
    await mounted!.flush();
    await mounted!.click(q('[data-entry="docs/a.json"]'));
    await mounted!.flush();

    expect(q('.json-tree')?.textContent).toContain('title');
    expect(q('.json-tree')?.textContent).toContain('"Hello"');

    await mounted!.click(button('Details'));
    expect(q('.data-fields')?.textContent).toContain('docs/a.json');
  });

  it('keeps secrets hidden until revealed, then hides them again', async () => {
    const { api } = fakeApi();
    await open(api);
    await mounted!.click(q('[data-data-service="secret"]'));
    await mounted!.flush();
    await mounted!.click(q('[data-entry="OPENAI_API_KEY"]'));
    await mounted!.flush();

    expect(text()).toContain('Value hidden');
    expect(text()).not.toContain('sk-123');

    await mounted!.click(button('Reveal', q('.data-preview') ?? document));
    await mounted!.flush();
    expect(text()).toContain('sk-123');
    expect(q('.data-reveal-bar')?.textContent).toContain('audit log');

    await mounted!.click(button('Hide now'));
    await mounted!.flush();
    expect(text()).not.toContain('sk-123');
  });

  it('deletes only once the id is typed back', async () => {
    const { api, data } = fakeApi();
    await open(api);
    await mounted!.click(q('[data-entry="top.txt"]'));
    await mounted!.flush();
    await mounted!.click(button('Delete'));

    const confirm = () => button('Delete file', q('[role="dialog"]') ?? document);
    expect(confirm()?.disabled).toBe(true);
    await mounted!.type(q('[aria-label="Type the id to confirm"]'), 'top.tx');
    expect(confirm()?.disabled).toBe(true);
    await mounted!.type(q('[aria-label="Type the id to confirm"]'), 'top.txt');
    await mounted!.click(confirm());
    await mounted!.flush();

    expect(api.remove).toHaveBeenCalledWith('object_storage', 'top.txt', 'top.txt');
    expect('top.txt' in data.object_storage).toBe(false);
    expect(rows()).not.toContain('top.txt');
    expect(q('.data-toasts')?.textContent).toContain('Deleted top.txt');
  });

  it('creates a secret, and asks for the id before replacing an existing one', async () => {
    const { api, data } = fakeApi();
    await open(api);
    await mounted!.click(q('[data-data-service="secret"]'));
    await mounted!.flush();

    await mounted!.click(button('New secret'));
    await mounted!.type(q('[aria-label="Name"]'), 'NEW_KEY');
    await mounted!.type(q('[aria-label="Value"]'), 'v1');
    await mounted!.click(button('Create'));
    await mounted!.flush();
    expect(data.secret.NEW_KEY).toBe('v1');

    await mounted!.click(button('New secret'));
    await mounted!.type(q('[aria-label="Name"]'), 'NEW_KEY');
    await mounted!.type(q('[aria-label="Value"]'), 'v2');
    await mounted!.click(button('Create'));
    await mounted!.flush();
    expect(data.secret.NEW_KEY).toBe('v1');
    expect(text()).toContain('already exists');

    await mounted!.type(q('[aria-label="Type the id to confirm"]'), 'NEW_KEY');
    await mounted!.click(button('Replace'));
    await mounted!.flush();
    expect(api.write).toHaveBeenLastCalledWith('secret', 'NEW_KEY', 'v2', 'NEW_KEY');
    expect(data.secret.NEW_KEY).toBe('v2');
  });

  it('filters loaded entries and moves with the keyboard', async () => {
    const { api } = fakeApi();
    await open(api);

    await mounted!.type(q('[aria-label="Search"]'), 'top');
    expect(rows()).toEqual(['top.txt']);
    await mounted!.type(q('[aria-label="Search"]'), '');

    await key('j');
    expect(q('[aria-selected="true"]')?.getAttribute('data-entry')).toBe('docs');
    await key('j');
    expect(q('[aria-selected="true"]')?.getAttribute('data-entry')).toBe('top.txt');
    await key('Enter');
    expect(q('[aria-label="Selected entry"]')?.textContent).toContain('top.txt');
    await key('Escape');
    expect(q('[aria-label="Selected entry"]')).toBeNull();
  });

  it('shows the history of an entry and the recent changes', async () => {
    const { api } = fakeApi();
    await open(api);
    await mounted!.click(q('[data-data-service="secret"]'));
    await mounted!.flush();
    await mounted!.click(q('[data-entry="PUBLIC_HOST"]'));
    await mounted!.flush();
    await mounted!.click(button('Reveal', q('.data-preview') ?? document));
    await mounted!.flush();

    await mounted!.click(button('History'));
    await mounted!.flush();
    expect(q('.data-history')?.textContent).toContain('Ada revealed it');

    await mounted!.click(button('Recent changes'));
    await mounted!.flush();
    expect(q('[role="dialog"]')?.textContent).toContain('PUBLIC_HOST');
  });
});

describe('expiring entries', () => {
  async function withKeyValue() {
    const { api, data } = fakeApi();
    data.keyvalue = {};
    const kv: ResourceServiceInfo = { name: 'keyvalue', available: true, reason: '', capabilities: caps({ expiry: true }) };
    api.services = vi.fn(() => Promise.resolve({ ok: true as const, data: { services: [...SERVICES, kv] } }));
    await open(api);
    await mounted!.click(q('[data-data-service="keyvalue"]'));
    await mounted!.flush();
    return { api, data };
  }

  async function choose(selector: string, value: string) {
    const { act } = await import('react');
    const select = q(selector) as HTMLSelectElement;
    await act(async () => {
      select.value = value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  it('creates a key that expires after the time chosen', async () => {
    const { api, data } = await withKeyValue();
    // New keys open the code editor; the value does not matter here.

    await mounted!.click(button('New key'));
    await mounted!.type(q('[aria-label="Name"]'), 'session:1');
    await mounted!.type(q('[aria-label="Expires after"]'), '2');
    await choose('[aria-label="Expiry unit"]', 'hours');
    await mounted!.click(button('Create'));
    await mounted!.flush();

    expect(api.write).toHaveBeenLastCalledWith('keyvalue', 'session:1', '', undefined, { ttlSeconds: 7200 });
    expect('session:1' in data.keyvalue).toBe(true);
  });

  it('creates keys without an expiry by default, and never asks on other services', async () => {
    const { api } = await withKeyValue();

    await mounted!.click(button('New key'));
    await mounted!.type(q('[aria-label="Name"]'), 'plain');
    await mounted!.click(button('Create'));
    await mounted!.flush();
    expect(api.write).toHaveBeenLastCalledWith('keyvalue', 'plain', '', undefined, {});

    await mounted!.click(q('[data-data-service="secret"]'));
    await mounted!.flush();
    await mounted!.click(button('New secret'));
    expect(q('[aria-label="Expires after"]')).toBeNull();
  });
});
