// @vitest-environment jsdom
import { createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { vectorStoreView } from './vector-store';
import { parseSample, textExcerpt, validateVectorDocument } from './vector-store-model';

const collection = (attributes: Record<string, string>): ResourceEntry => ({
  id: 'chunks',
  name: 'chunks',
  kind: 'container',
  actions: ['delete'],
  size: null,
  modified: null,
  attributes: { documents: '1200', dimension: '1536', distance: 'cosine', ...attributes },
});

const vector = (attributes: Record<string, string> = {}): ResourceEntry => ({
  id: 'chunks/doc-1',
  name: 'doc-1',
  kind: 'item',
  actions: ['read', 'download', 'write', 'delete'],
  size: null,
  modified: null,
  attributes,
});

function Node({ node }: { node: ReactNode }) {
  return createElement(Fragment, null, node);
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('vector store model', () => {
  it('parses sample vectors', () => {
    expect(parseSample('0.1,-0.2,0.3')).toEqual([0.1, -0.2, 0.3]);
    expect(parseSample('0.1,x')).toEqual([]);
    expect(parseSample(undefined)).toEqual([]);
  });

  it('finds the text a vector embeds, payload first', () => {
    expect(textExcerpt({ text: 'from payload' }, { title: 'from metadata' })).toEqual({ field: 'title', text: 'from metadata' });
    expect(textExcerpt({ content: ' body ' }, {})).toEqual({ field: 'content', text: 'body' });
    expect(textExcerpt({ n: 1 }, null)).toBeNull();
  });

  it('validates vector documents before saving', () => {
    expect(validateVectorDocument('{"vector": [0.1, 2], "metadata": {}, "payload": {"text": "x"}}')).toBeNull();
    expect(validateVectorDocument('{"payload": {"text": "keep the stored vector"}}')).toBeNull();
    expect(validateVectorDocument('{"vector": []}')).toMatch(/non-empty/);
    expect(validateVectorDocument('{"vector": [1, "a"]}')).toMatch(/item 1/);
    expect(validateVectorDocument('{"vectors": [1]}')).toMatch(/Unknown fields: vectors/);
    expect(validateVectorDocument('{"payload": [1]}')).toMatch(/JSON object/);
    expect(validateVectorDocument('{"vector": [1], "distance_metric": "manhattan"}')).toMatch(/distance_metric/);
    expect(validateVectorDocument('[')).toMatch(/Not valid JSON/);
  });
});

describe('vector store view', () => {
  it('shows collections as cards with a sparkline and their shape', async () => {
    const level = vectorStoreView.level!(0, '');
    const entry = collection({ sample: '0.1,-0.2,0.3,0.4' });
    mounted = await mount(Node, {
      node: createElement(
        Fragment,
        null,
        level.card!(entry),
        ...level.columns!.map((c) => createElement('span', { key: c.id }, c.render(entry))),
      ),
    });

    expect(level.layout).toBe('cards');
    expect(mounted.host.querySelectorAll('.vector-bars rect')).toHaveLength(4);
    expect(mounted.host.textContent).toContain('1,200');
    expect(mounted.host.textContent).toContain('1536');
    expect(mounted.host.textContent).toContain('cosine');
    expect(vectorStoreView.deleteWarning!(entry)).toContain('1,200 vectors');
  });

  it('says a collection is empty only when it is', async () => {
    const card = vectorStoreView.level!(0, '').card!;
    mounted = await mount(Node, { node: card(collection({ documents: '0' })) });
    expect(mounted.host.textContent).toContain('No vectors yet');
    await mounted.unmount();

    // Vectors but no sample reported: no false "empty" claim.
    mounted = await mount(Node, { node: card(collection({})) });
    expect(mounted.host.textContent).toBe('');
  });

  it('previews a vector with the text it embeds, then its shape and payload', async () => {
    const detail: ResourceDetail = {
      entry: vector({ fields: 'source, text' }),
      content: { encoding: 'text', text: '{}', size: 2, truncated: false },
      view: {
        type: 'vector',
        dimension: 1536,
        components: [0.1, -0.2, 0.3],
        norm: 0.374,
        metadata: { source: 'handbook.pdf' },
        payload: { text: 'Paris is the capital of France.' },
      },
    };
    mounted = await mount(Node, { node: vectorStoreView.preview!(detail, {}) });

    expect(mounted.host.querySelector('.data-vector-excerpt')?.textContent).toContain('Paris is the capital of France.');
    expect(mounted.host.querySelector('.data-vector-excerpt')?.textContent).toContain('text');
    expect(mounted.host.textContent).toContain('1536');
    expect(mounted.host.textContent).toContain('handbook.pdf');
    expect(vectorStoreView.facts!(detail).map((f) => f.label)).toEqual(['Dimension', 'Norm', 'Fields']);
    expect(vectorStoreView.preview!({ ...detail, view: null }, {})).toBeNull();
  });

  it('edits vectors as validated JSON from a template', () => {
    const editor = vectorStoreView.editor!;
    expect(editor.language('chunks/doc-1')).toBe('json');
    expect(editor.validate!('{"vector": [0.5], "payload": {"text": "x"}}')).toBeNull();
    expect(JSON.parse(editor.template!('chunks'))).toEqual({ vector: [], metadata: {}, payload: { text: '' } });
    expect(vectorStoreView.nounFor!(vector(), 1).one).toBe('vector');
  });
});
