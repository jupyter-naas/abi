import { describe, expect, it } from 'vitest';
import type { PlatformEvent } from './bfo-event-projection';
import { buildEventGraphModel, emptyFilters } from './event-graph-model';
import { defaultGraphParams } from './event-graph-params';
import {
  depthAlpha,
  projectNodes,
  seedEventGraph,
  wrapNodeLabel,
} from './event-graph-layout';

function event(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'http://ontology.naas.ai/abi/agent/evt-1',
    _class_uri: 'http://ontology.naas.ai/abi/agent/AgentToolCalled',
    _seq: 42,
    _stored_at: '2026-07-31T12:00:00Z',
    _site: 'nexus.localhost',
    user_id: 'alice',
    tool_name: 'search_web',
    ...overrides,
  };
}

function seedOne(params = defaultGraphParams('3d')) {
  const model = buildEventGraphModel([event()], emptyFilters(), {
    focusUri: null,
    processCount: params.processCount,
  });
  return seedEventGraph(model, params);
}

describe('seedEventGraph', () => {
  it('pins the focus process at the origin and rings its satellites around it', () => {
    const layout = seedOne();
    expect(layout.focus?.x).toBe(0);
    expect(layout.focus?.y).toBe(0);
    expect(layout.focus?.pinned).toBe(true);
    expect(layout.focus?.physicsEnabled).toBe(false);
    for (const node of layout.nodes) {
      if (node.isProcess) continue;
      expect(Math.hypot(node.x, node.y)).toBeGreaterThan(200);
    }
  });

  it('gives every satellite exactly one edge to its process', () => {
    const layout = seedOne();
    const satellites = layout.nodes.filter((node) => !node.isProcess);
    expect(layout.edges).toHaveLength(satellites.length);
    for (const edge of layout.edges) {
      expect(edge.from.isProcess || edge.to.isProcess).toBe(true);
    }
  });

  it('points the GDC edge into the process, matching "is about"', () => {
    const layout = seedOne();
    expect(layout.edges.find((edge) => edge.label === 'is about')?.to.isProcess).toBe(true);
  });

  it('dashes the edge to an unmapped bucket so the gap reads as a gap', () => {
    const layout = seedOne();
    expect(layout.edges.find((edge) => edge.to.bucket === 'Quality')?.dashed).toBe(true);
  });

  it('separates buckets in depth when clustering by bucket', () => {
    const params = { ...defaultGraphParams('3d'), clusterBy: 'bucket' };
    const depths = new Map<string, number>();
    for (const node of seedOne(params).nodes) {
      if (node.isProcess) continue;
      depths.set(node.bucket, node.z);
    }
    expect(new Set(depths.values()).size).toBe(depths.size);
  });

  it('flattens depth when clustering is off', () => {
    const params = { ...defaultGraphParams('3d'), clusterBy: 'none' };
    for (const node of seedOne(params).nodes) expect(node.z).toBe(0);
  });

  it('seeds a second process away from the focus and shares its participants', () => {
    const model = buildEventGraphModel(
      [event(), event({ _uri: 'evt-2', _seq: 43, tool_name: 'git_push' })],
      emptyFilters(),
      { focusUri: null, processCount: 8 },
    );
    const layout = seedEventGraph(model, defaultGraphParams('3d'));
    const processes = layout.nodes.filter((node) => node.isProcess);
    expect(processes).toHaveLength(2);
    expect(Math.hypot(processes[1].x, processes[1].y)).toBeGreaterThan(400);
    // One user, one host: both processes point at the same nodes.
    const alice = layout.nodes.find((node) => node.label === 'alice');
    expect(alice?.processIds).toHaveLength(2);
  });
});

describe('projectNodes', () => {
  it('keeps the seeded z as depth when the camera faces the plane head on', () => {
    const layout = seedOne();
    projectNodes(layout.nodes, 0, 0, '3d');
    for (const node of layout.nodes) {
      expect(node.depth).toBeCloseTo(node.z, 5);
      expect(node.px).toBeCloseTo(node.x * node.ds, 5);
    }
  });

  it('is the identity in 2D: there is no depth to reveal', () => {
    const layout = seedOne();
    projectNodes(layout.nodes, 1.2, 0.8, '2d');
    for (const node of layout.nodes) {
      expect(node.px).toBe(node.x);
      expect(node.py).toBe(node.y);
      expect(node.ds).toBe(1);
      expect(depthAlpha(node, '2d')).toBe(1);
    }
  });

  it('shrinks what the orbit pushes behind the camera plane', () => {
    const layout = seedOne();
    projectNodes(layout.nodes, 0, 0.6, '3d');
    const behind = layout.nodes.filter((n) => n.depth > 0);
    const inFront = layout.nodes.filter((n) => n.depth < 0);
    expect(behind.length).toBeGreaterThan(0);
    expect(inFront.length).toBeGreaterThan(0);
    for (const node of behind) expect(node.ds).toBeLessThan(1);
    for (const node of inFront) expect(node.ds).toBeGreaterThan(1);
  });

  it('never fades a node past the floor that keeps it readable', () => {
    const layout = seedOne();
    projectNodes(layout.nodes, 1.2, 1.2, '3d');
    for (const node of layout.nodes) {
      expect(depthAlpha(node, '3d')).toBeGreaterThanOrEqual(0.42);
      expect(depthAlpha(node, '3d')).toBeLessThanOrEqual(1);
    }
  });
});

describe('wrapNodeLabel', () => {
  it('keeps a short label on one line', () => {
    expect(wrapNodeLabel('alice', 12, 3)).toEqual(['alice']);
  });

  it('wraps on words before breaking them', () => {
    expect(wrapNodeLabel('AI Message Emitted', 10, 3)).toEqual(['AI Message', 'Emitted']);
  });

  it('hard-breaks a token longer than the line', () => {
    expect(wrapNodeLabel('event-log#seq=42', 8, 3)).toEqual(['event-lo', 'g#seq=42']);
  });

  it('ellipsises what does not fit in the allowed lines', () => {
    const lines = wrapNodeLabel('one two three four five six', 6, 2);
    expect(lines).toHaveLength(2);
    expect(lines[1].endsWith('…')).toBe(true);
  });
});
