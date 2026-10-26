// @vitest-environment jsdom
import { createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { CachePreview, TierBadges, cacheView } from './cache';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const Host = ({ node }: { node: ReactNode }) => createElement(Fragment, null, node);

const entry = (id: string, attributes: Record<string, string>, size = 10): ResourceEntry => ({
  id,
  name: id,
  kind: 'item',
  actions: ['read', 'download', 'write', 'delete'],
  size,
  modified: attributes.created_at ?? null,
  attributes: { created_at: '2026-10-02T10:00:00Z', ...attributes },
});

describe('cache view', () => {
  it('shows type, tier and age on a row, and the value line', async () => {
    const row = entry('lookup:acme', { data_type: 'json', tier: 'hot', summary: '{"name": "Acme"}' });
    const columns = cacheView.level?.(0, '').columns ?? [];
    mounted = await mount(Host, {
      node: createElement(
        Fragment,
        null,
        cacheView.summary?.(row),
        ...columns.map((c) => createElement('span', { key: c.id, 'data-col': c.id }, c.render(row))),
      ),
    });

    expect(mounted.host.querySelector('[data-col="type"]')?.textContent).toBe('JSON');
    expect(mounted.host.querySelector('[data-col="tier"] .data-badge-warn')?.textContent).toBe('hot');
    expect(mounted.host.querySelector('[data-col="age"] time')?.getAttribute('datetime')).toBe('2026-10-02T10:00:00Z');
    expect(mounted.host.textContent).toContain('{"name": "Acme"}');
  });

  it('names every tier holding an opened entry', async () => {
    mounted = await mount(TierBadges, { entry: entry('k', { tier: 'hot', tiers: 'hot, cold' }) });
    expect([...mounted.host.querySelectorAll('.data-badge')].map((b) => b.textContent)).toEqual(['hot', 'cold']);
  });

  it('never shows a pickle, explains why and offers its raw bytes', async () => {
    const detail: ResourceDetail = {
      entry: entry('pickled', { data_type: 'pickle', tier: 'cold' }, 2048),
      content: { encoding: 'binary', text: null, size: 2048, truncated: false },
    };
    const download = vi.fn(async () => new Blob([new Uint8Array([0x80, 0x04, 0x95])]));
    mounted = await mount(CachePreview, { detail, ctx: { download } });

    expect(mounted.host.textContent).toContain('never loads pickles');
    expect(mounted.host.textContent).toContain('Show hex dump');
    expect(download).not.toHaveBeenCalled();
  });

  it('previews a JSON entry as a tree and edits it as JSON', async () => {
    const detail: ResourceDetail = {
      entry: entry('config', { data_type: 'json', tier: 'cold', tiers: 'cold' }),
      content: { encoding: 'text', text: '{"on": true}', size: 12, truncated: false },
      view: { type: 'json', value: { on: true, limits: [1, 2] } },
    };
    mounted = await mount(CachePreview, { detail, ctx: {} });

    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('limits');
    expect(mounted.host.querySelector('.data-cache-origin')?.textContent).toContain('cold');
    expect(cacheView.editor?.language('config', detail.entry)).toBe('json');
    expect(cacheView.editor?.language('note', entry('note', { data_type: 'text' }))).toBe('plaintext');
  });

  it('describes pickles and binaries without their value on a row', async () => {
    mounted = await mount(Host, {
      node: createElement(Fragment, null, cacheView.summary?.(entry('p', { data_type: 'pickle' }, 2048))),
    });
    expect(mounted.host.textContent).toBe('Pickled Python object · 2.0 KB');
  });
});
