import { describe, expect, it } from 'vitest';
import type { GraphEdge, GraphNode } from '../stores/knowledge-graph';
import {
  explorerInstanceGraph,
  filterInstanceNetwork,
  graphConnectors,
  graphNetworkRoute,
  graphNodeShape,
  instanceLabelVAdjust,
  instanceLayoutEdges,
  instanceNodeCtxRenderer,
  instanceNodeLayoutBox,
  isSchemaPredicate,
  wrapInstanceLabel,
} from './graph-network-view';

describe('graph network presentation', () => {
  it('defaults Graph to circles and right-angle connectors', () => {
    expect(graphNodeShape('')).toBe('circle');
    expect(graphNodeShape('view=network&graph=urn:g')).toBe('circle');
    expect(graphNodeShape('nodes=square')).toBe('square');
    expect(graphConnectors('')).toBe('orthogonal');
    expect(graphConnectors('connectors=curved')).toBe('curved');
  });

  it('keeps explorer filters while changing nodes, spacing and connectors', () => {
    const query = 'graph=urn%3Ag&class=urn%3APerson&view=network&list=hierarchy';
    const next = graphNetworkRoute(query, { nodes: 'square', spacing: 'spacious', connectors: 'curved' });
    expect(next.get('nodes')).toBe('square');
    expect(next.get('spacing')).toBe('spacious');
    expect(next.get('connectors')).toBe('curved');
    expect(next.get('view')).toBe('network');
    expect(next.get('graph')).toBe('urn:g');
    expect(next.get('class')).toBe('urn:Person');
    expect(graphNetworkRoute(query, { nodes: 'circle' }).get('nodes')).toBe('circle');
  });

  it('computes a negative label-on-top vadjust that grows with size and lines', () => {
    const one = instanceLabelVAdjust(18, 1);
    const two = instanceLabelVAdjust(18, 2);
    const larger = instanceLabelVAdjust(22, 1);
    expect(one).toBeLessThan(0);
    expect(two).toBeLessThan(one);
    expect(larger).toBeLessThan(one);
  });

  it('wraps instance labels so they can sit above a circle', () => {
    expect(wrapInstanceLabel('Ada')).toEqual(['Ada']);
    expect(wrapInstanceLabel('Ada Lovelace Example Workspace')).toHaveLength(2);
    expect(instanceNodeLayoutBox('Ada').height).toBeGreaterThan(instanceNodeLayoutBox('Ada').width / 3);
  });

  it('filters an ego graph by search, focus and hidden object properties', () => {
    const nodes: GraphNode[] = [
      { id: 'ada', label: 'Ada', type: 'Person', properties: { uri: 'urn:ada', is_primary: true } },
      { id: 'boss', label: 'Boss', type: 'Person', properties: { uri: 'urn:boss' } },
      { id: 'acme', label: 'Acme', type: 'Organization', properties: { uri: 'urn:acme' } },
    ];
    const edges: GraphEdge[] = [
      { id: 'reports', source: 'ada', target: 'boss', type: 'reports', label: 'reports to' },
      { id: 'member', source: 'acme', target: 'ada', type: 'member', label: 'has member' },
    ];
    const search = filterInstanceNetwork(nodes, edges, { search: 'acme' });
    expect(search.nodes.map(node => node.id)).toEqual(['acme']);
    expect(search.edges).toHaveLength(0);

    const byIri = filterInstanceNetwork(
      [{ id: 'entity:urn:person', label: 'Person', type: 'entity', properties: { iri: 'urn:person' } }],
      [],
      { search: 'urn:person' },
    );
    expect(byIri.nodes.map(node => node.id)).toEqual(['entity:urn:person']);

    const focused = filterInstanceNetwork(nodes, edges, { focusedId: 'ada' });
    expect(focused.nodes.map(node => node.id).sort()).toEqual(['acme', 'ada', 'boss']);
    expect(focused.edges).toHaveLength(2);

    const isolated = filterInstanceNetwork(nodes, edges, { objectProperties: false });
    expect(isolated.nodes).toHaveLength(3);
    expect(isolated.edges).toHaveLength(0);
  });

  it('draws the instance label above the circle, not inside it', () => {
    const fills: Array<{ text: string; y: number }> = [];
    const ctx = {
      beginPath() {},
      arc() {},
      fill() {},
      stroke() {},
      strokeText() {},
      fillText(text: string, _x: number, y: number) { fills.push({ text, y }); },
      font: '',
      textAlign: '',
      textBaseline: '',
      lineJoin: '',
      lineWidth: 0,
      fillStyle: '',
      strokeStyle: '',
    } as unknown as CanvasRenderingContext2D;
    const drawn = instanceNodeCtxRenderer({ circular: true, textColor: '#111', strokeColor: '#fff' })({
      ctx, x: 0, y: 0, style: { size: 18, color: '#3b82f6', borderColor: '#2563eb', borderWidth: 2 }, label: 'Ada\nLovelace',
    });
    drawn.drawNode();
    drawn.drawExternalLabel();
    expect(fills.map(item => item.text)).toEqual(['Ada', 'Lovelace']);
    expect(Math.max(...fills.map(item => item.y))).toBeLessThan(-18);
  });

  it('keeps instance relations and drops OWL/RDFS schema from the Graph canvas', () => {
    expect(isSchemaPredicate('http://www.w3.org/2000/01/rdf-schema#range', 'range')).toBe(true);
    expect(isSchemaPredicate('http://www.w3.org/2002/07/owl#equivalentProperty')).toBe(true);
    expect(isSchemaPredicate('http://schema.org/locatedIn', 'located in')).toBe(false);
    expect(isSchemaPredicate('http://www.w3.org/2002/07/owl#sameAs')).toBe(false);

    const graph = explorerInstanceGraph({
      items: [
        { uri: 'urn:ad', graph_uri: 'urn:g', label: 'Abu Dhabi', class_label: 'City', class_uri: 'urn:City' },
      ],
      neighbors: [
        { uri: 'urn:emirate', graph_uri: 'urn:g', label: 'Emirate of Abu Dhabi', class_label: 'Emirate', class_uri: 'urn:Emirate' },
        { uri: 'urn:Settlement', graph_uri: 'urn:g', label: 'Settlement', class_label: 'Class', class_uri: 'http://www.w3.org/2002/07/owl#Class' },
        { uri: 'urn:contained', graph_uri: 'urn:g', label: 'containedInPlace', class_label: 'Object Property', class_uri: 'http://www.w3.org/2002/07/owl#ObjectProperty' },
      ],
      relations: [
        { graph_uri: 'urn:g', source: 'urn:ad', target: 'urn:emirate', predicate: 'urn:locatedIn', label: 'located in' },
        { graph_uri: 'urn:g', source: 'urn:locatedIn', target: 'urn:Settlement', predicate: 'http://www.w3.org/2000/01/rdf-schema#range', label: 'range' },
        { graph_uri: 'urn:g', source: 'urn:locatedIn', target: 'urn:contained', predicate: 'http://www.w3.org/2002/07/owl#equivalentProperty', label: 'equivalentProperty' },
      ],
    });
    expect(graph.nodes.map(node => node.label).sort()).toEqual(['Abu Dhabi', 'Emirate of Abu Dhabi']);
    expect(graph.edges.map(edge => edge.label)).toEqual(['located in']);
  });

  it('points TD/LR layout edges from neighbors to the primary instance', () => {
    const nodes: GraphNode[] = [
      { id: 'ada', label: 'Ada', type: 'Person', properties: { is_primary: true } },
      { id: 'boss', label: 'Boss', type: 'Person', properties: {} },
    ];
    const edges = instanceLayoutEdges(nodes);
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe('boss');
    expect(edges[0].target).toBe('ada');
    expect(edges[0].properties?.relation_kind).toBe('is_a');
    expect(edges[0].properties?.layout_only).toBe(true);
  });
});
