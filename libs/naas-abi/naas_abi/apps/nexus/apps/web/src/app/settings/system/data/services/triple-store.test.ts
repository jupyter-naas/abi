// @vitest-environment jsdom
import { createElement, Fragment } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { GraphPreview, graphParts, magnitude, tripleStoreView } from './triple-store';

const FOAF = 'http://xmlns.com/foaf/0.1/';
const PEOPLE = 'http://example.org/people/';

const graph = (id: string, attributes: Record<string, string> = {}): ResourceEntry => ({
  id,
  name: id.split('/').pop() ?? id,
  kind: 'item',
  actions: ['read', 'download', 'write', 'delete'],
  size: null,
  modified: null,
  attributes,
});

const detail: ResourceDetail = {
  entry: graph(`${PEOPLE}graph`, { triples: '9' }),
  content: { encoding: 'text', text: '@prefix foaf: <http://xmlns.com/foaf/0.1/> .', size: 40, truncated: false },
  view: {
    type: 'triples',
    triples: [
      [`<${PEOPLE}p0>`, '<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>', `<${FOAF}Person>`],
      [`<${PEOPLE}p0>`, `<${FOAF}name>`, '"Ada"@en'],
    ],
    prefixes: { foaf: FOAF, people: PEOPLE },
    total: 9,
    predicates: [
      ['http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 4],
      [`${FOAF}name`, 4],
    ],
    classes: [[`${FOAF}Person`, 4]],
    predicate_count: 3,
    class_count: 1,
  },
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('knowledge graph view', () => {
  it('splits graph IRIs into what tells them apart and the rest', () => {
    expect(graphParts('http://ontology.naas.ai/graph/palantir/2026-09-21/b037b363')).toEqual({
      base: 'ontology.naas.ai/graph/palantir/2026-09-21/',
      tail: 'b037b363',
    });
    expect(graphParts('urn:graph')).toEqual({ base: '', tail: 'urn:graph' });
    expect(graphParts('http://x.org/ns#')).toEqual({ base: 'x.org/', tail: 'ns' });
  });

  it('scales triple counts logarithmically', () => {
    expect(magnitude(0)).toBe(0);
    expect(magnitude(1)).toBeGreaterThan(0);
    expect(magnitude(10_000_000)).toBe(100);
    expect(magnitude(1_000)).toBeLessThan(magnitude(100_000));
  });

  it('previews stats, ranked classes and predicates, and the triples', async () => {
    mounted = await mount(GraphPreview, { detail });
    const text = mounted.host.textContent ?? '';

    expect(mounted.host.querySelector('.data-triple-store-stats')?.textContent).toContain('9');
    const ranked = [...mounted.host.querySelectorAll('.data-triple-store-ranked-label')].map((n) => n.textContent);
    expect(ranked).toEqual(['foaf:Person', 'rdf:type', 'foaf:name']);
    expect(text).toContain('top 2 of 3');
    expect(mounted.host.querySelectorAll('.rdf-table tbody tr')).toHaveLength(2);
    expect(text).toContain('people:p0');
  });

  it('falls back to the generic preview without a triples view', () => {
    expect(tripleStoreView.preview?.({ ...detail, view: null }, {})).toBeNull();
  });

  it('lists graphs with a meter, the IRI base and a schema badge', async () => {
    const column = tripleStoreView.level?.(0, '').columns?.[0];
    const schema = graph('http://ontology.naas.ai/graph/schema', { role: 'schema', triples: '0' });
    const Cell = () =>
      createElement(
        Fragment,
        null,
        column?.render(graph(`${PEOPLE}graph`, { triples: '1200' })),
        tripleStoreView.badges?.(schema),
        tripleStoreView.summary?.(schema),
      );
    mounted = await mount(Cell, {});
    const text = mounted.host.textContent ?? '';

    expect(text).toContain('1,200');
    expect(text).toContain('Schema · read-only');
    expect(text).toContain('Empty');
    expect(text).toContain('ontology.naas.ai/graph/');
  });

  it('only accepts absolute IRIs as graph names, and states what deleting does', () => {
    const validate = tripleStoreView.editor?.validateName;
    expect(validate?.('http://ontology.naas.ai/graph/new')).toBeNull();
    expect(validate?.('my graph')).toMatch(/absolute IRI/);
    expect(validate?.('http://x.org/<bad>')).not.toBeNull();
    expect(tripleStoreView.deleteWarning?.(graph(`${PEOPLE}g`, { triples: '1500' }))).toContain('1,500');
    expect(tripleStoreView.editor?.template?.('')).toContain('@prefix rdfs:');
  });
});
