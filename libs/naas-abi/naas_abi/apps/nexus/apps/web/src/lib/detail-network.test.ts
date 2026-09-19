import { describe, expect, it } from 'vitest';
import { instanceDomainGraph, instanceDomainRelationsKey, instanceEgoGraph, termEgoGraph } from './detail-network';
import type { DictionaryTerm } from './ontology-dictionary-tree';

describe('instanceEgoGraph', () => {
  it('keeps the current node and both directions from the connections payload', () => {
    const graph = instanceEgoGraph(
      { uri: 'urn:person', label: 'Ada', class_label: 'Person' },
      [
        { role: 'domain', predicate_uri: 'urn:reports', predicate_label: 'reports to', other_uri: 'urn:boss', other_label: 'Boss' },
        { role: 'range', predicate_uri: 'urn:member', predicate_label: 'has member', other_uri: 'urn:team', other_label: 'Team' },
      ],
    );
    expect(graph.rootId).toBe('urn:person');
    expect(graph.nodes.find(node => node.id === 'urn:person')?.properties.is_primary).toBe(true);
    expect(graph.edges.map(edge => [edge.source, edge.label, edge.target])).toEqual([
      ['urn:person', 'reports to', 'urn:boss'],
      ['urn:team', 'has member', 'urn:person'],
    ]);
  });

  it('ignores self-links and missing neighbours', () => {
    const graph = instanceEgoGraph(
      { uri: 'urn:a', label: 'A' },
      [
        { role: 'domain', predicate_uri: 'urn:self', predicate_label: 'same as', other_uri: 'urn:a', other_label: 'A' },
        { role: 'domain', predicate_uri: 'urn:empty', predicate_label: 'empty', other_uri: '', other_label: '' },
      ],
    );
    expect(graph.nodes).toHaveLength(1);
    expect(graph.edges).toHaveLength(0);
  });

  it('instanceDomainGraph keeps outgoing links and ignores incoming range rows', () => {
    const graph = instanceDomainGraph(
      { uri: 'urn:person', label: 'Ada', class_label: 'Person' },
      [
        { role: 'domain', predicate_uri: 'urn:reports', predicate_label: 'reports to', other_uri: 'urn:boss', other_label: 'Boss' },
        { role: 'range', predicate_uri: 'urn:member', predicate_label: 'has member', other_uri: 'urn:team', other_label: 'Team' },
      ],
    );
    expect(graph.nodes.map(node => node.id)).toEqual(['urn:person', 'urn:boss']);
    expect(graph.edges.map(edge => [edge.source, edge.label, edge.target])).toEqual([
      ['urn:person', 'reports to', 'urn:boss'],
    ]);
  });

  it('instanceDomainRelationsKey is stable for the same payload in a new array', () => {
    const rows = [
      { role: 'domain' as const, predicate_uri: 'urn:a', predicate_label: 'a', other_uri: 'urn:x', other_label: 'X' },
      { role: 'range' as const, predicate_uri: 'urn:b', predicate_label: 'b', other_uri: 'urn:y', other_label: 'Y' },
    ];
    expect(instanceDomainRelationsKey([...rows])).toBe(instanceDomainRelationsKey([...rows]));
  });
});

describe('termEgoGraph', () => {
  it('is the selected term plus its immediate connections', () => {
    const parent: DictionaryTerm = { id: 'urn:parent', name: 'Parent', type: 'entity' };
    const child: DictionaryTerm = { id: 'urn:child', name: 'Child', type: 'entity', parents: [{ id: parent.id, name: parent.name }] };
    const graph = termEgoGraph(child, [parent, child]);
    expect(graph.rootId).toBe('entity:urn:child');
    expect(graph.nodes).toHaveLength(2);
    expect(graph.edges.map(edge => [edge.source, edge.label, edge.target])).toEqual([
      ['entity:urn:child', 'subclass of', 'entity:urn:parent'],
    ]);
  });
});
