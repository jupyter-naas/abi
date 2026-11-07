// @vitest-environment jsdom
import { act, createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { KeyValuePreview, keyDeleteWarning, keyIcon, keyValueView } from './keyvalue';
import { TtlBadge, keyFamily, keyPrefix, ttlState } from './keyvalue-parts';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.useRealTimers();
});

const Host = ({ node }: { node: ReactNode }) => createElement(Fragment, null, node);

const entry = (id: string, attributes: Record<string, string> = {}, size: number | null = 12): ResourceEntry => ({
  id,
  name: id,
  kind: 'item',
  actions: ['read', 'download', 'write', 'delete'],
  size,
  modified: null,
  attributes,
});

describe('key families', () => {
  it('reads the family from the key prefix', () => {
    expect(keyPrefix('lock:object:finance/graph.ttl')).toBe('lock');
    expect(keyPrefix('signals/github/last_ingest')).toBe('signals');
    expect(keyPrefix('plain-key')).toBeNull();
    expect(keyPrefix('a-very-long-prefix-name-that-is-not-one:x')).toBeNull();
    expect(keyFamily('session:42')).toBe('session');
    expect(keyFamily('jobs:digest')).toBe('job');
    expect(keyFamily('feature:flags')).toBe('other');
    expect(keyFamily('flags')).toBeNull();
    expect(keyIcon(entry('lock:a')).displayName ?? keyIcon(entry('lock:a')).name).toMatch(/Lock/);
  });

  it('warns about what deleting a lock or a session does', () => {
    expect(keyDeleteWarning(entry('lock:job'))).toContain('releases it');
    expect(keyDeleteWarning(entry('session:1'))).toContain('signs that session out');
    expect(keyDeleteWarning(entry('flags'))).toContain('not found');
  });

  it('edits JSON values as JSON', () => {
    expect(keyValueView.editor?.language('flags', entry('flags', { encoding: 'json' }))).toBe('json');
    expect(keyValueView.editor?.language('note', entry('note', { encoding: 'text' }))).toBe('plaintext');
  });
});

describe('expiry', () => {
  const now = Date.parse('2026-10-02T12:00:00Z');
  const at = (seconds: number) => new Date(now + seconds * 1000).toISOString();

  it('reads as no expiry, minutes, the last minute, then expired', () => {
    expect(ttlState(undefined, now)).toEqual({ tone: 'neutral', label: 'no expiry', seconds: null });
    expect(ttlState(at(240), now)).toMatchObject({ tone: 'info', label: 'expires in 4 min' });
    expect(ttlState(at(42), now)).toMatchObject({ tone: 'warn', label: 'expires in 42 s' });
    expect(ttlState(at(-1), now)).toMatchObject({ tone: 'danger', label: 'expired' });
  });

  it('counts down live', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    mounted = await mount(TtlBadge, { expiresAt: at(65) });
    expect(mounted.host.textContent).toBe('expires in 1 min');

    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });
    expect(mounted.host.textContent).toBe('expires in 55 s');
    expect(mounted.host.querySelector('.data-badge-warn')).not.toBeNull();

    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    expect(mounted.host.textContent).toBe('expired');
  });
});

describe('key-value rows and preview', () => {
  it('shows the value kind, size, expiry and a monospace value line', async () => {
    const row = entry('lock:job', { encoding: 'binary' }, 6);
    const columns = keyValueView.level?.(0, '').columns ?? [];
    mounted = await mount(Host, {
      node: createElement(
        Fragment,
        null,
        keyValueView.badges?.(row),
        keyValueView.summary?.(row),
        ...columns.map((c) => createElement('span', { key: c.id, 'data-col': c.id }, c.render(row))),
      ),
    });
    const text = mounted.host.textContent ?? '';
    expect(text).toContain('lock');
    expect(text).toContain('Binary value · 6 B');
    expect(mounted.host.querySelector('[data-col="encoding"]')?.textContent).toBe('Binary');
    expect(mounted.host.querySelector('[data-col="expiry"]')?.textContent).toBe('no expiry');
  });

  it('previews JSON as a tree, with the expiry and what the key family means', async () => {
    const detail: ResourceDetail = {
      entry: entry('session:42', { encoding: 'json', expires_at: new Date(Date.now() + 300_000).toISOString() }),
      content: { encoding: 'text', text: '{"user": "ada", "scopes": ["read"]}', size: 35, truncated: false },
    };
    mounted = await mount(KeyValuePreview, { detail, ctx: {} });

    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('scopes');
    expect(mounted.host.textContent).toContain('expires in 5 min');
    expect(mounted.host.textContent).toContain('ends that session');
  });
});
