import { describe, expect, it } from 'vitest';
import { architecture } from './architecture-model';
import { describeDependency, graphPositions, segmentDistance, graphRoute, GRAPH_NODE_WIDTH, GRAPH_NODE_HEIGHT, DIAGRAM_LAYERS } from './graph-model';
describe('dependency graph', () => {
  it('measures proximity in screen pixels, including endpoints and zero length links', () => {
    expect(segmentDistance(50, 6, 0, 0, 100, 0)).toBe(6);
    expect(segmentDistance(110, 0, 0, 0, 100, 0)).toBe(10);
    expect(segmentDistance(3, 4, 0, 0, 0, 0)).toBe(5);
  });
  it('places every component at a finite deterministic position', () => {
    const nodes = graphPositions();
    expect(nodes).toEqual(graphPositions());
    expect(new Set(nodes.map(n => n.id))).toEqual(new Set(architecture.components.map(n => n.id)));
    expect(nodes.every(n => Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true);
  });
  it('labels the direction and extracted relationship counts', () => {
    const edge = architecture.edges[0]; const label = describeDependency(edge);
    expect(label.title).toBe(`${architecture.components.find(c => c.id === edge.source)!.label} → ${architecture.components.find(c => c.id === edge.target)!.label}`);
    for (const [relation, count] of Object.entries(edge.relations)) expect(label.detail).toContain(`${relation.replaceAll('_', ' ')}: ${count}`);
  });
});

describe('architectural map spacing', () => {
  it('keeps every card separate and in its architectural column', () => {
    const nodes = graphPositions();
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      const component = architecture.components.find(c => c.id === a.id)!;
      expect(DIAGRAM_LAYERS[a.column].id).toBe(component.layer);
      for (const b of nodes.slice(i + 1)) {
        expect(Math.abs(a.x - b.x) >= GRAPH_NODE_WIDTH + 16 || Math.abs(a.y - b.y) >= GRAPH_NODE_HEIGHT + 16).toBe(true);
      }
    }
  });
  it('routes all dependencies around other cards', () => {
    const nodes = graphPositions();
    const positions = new Map(nodes.map(n => [n.id, n]));
    for (const edge of architecture.edges) {
      const route = graphRoute(positions.get(edge.source)!, positions.get(edge.target)!);
      for (let i = 1; i < route.length; i++) {
        const a = route[i - 1], b = route[i];
        expect(a.x === b.x || a.y === b.y).toBe(true);
        for (const node of nodes.filter(n => n.id !== edge.source && n.id !== edge.target)) {
          const left = node.x - GRAPH_NODE_WIDTH / 2, right = node.x + GRAPH_NODE_WIDTH / 2;
          const top = node.y - GRAPH_NODE_HEIGHT / 2, bottom = node.y + GRAPH_NODE_HEIGHT / 2;
          const crosses = a.y === b.y
            ? a.y > top && a.y < bottom && Math.max(a.x,b.x) > left && Math.min(a.x,b.x) < right
            : a.x > left && a.x < right && Math.max(a.y,b.y) > top && Math.min(a.y,b.y) < bottom;
          expect(crosses, `${edge.source} → ${edge.target} crosses ${node.id}`).toBe(false);
        }
      }
    }
  });
});
