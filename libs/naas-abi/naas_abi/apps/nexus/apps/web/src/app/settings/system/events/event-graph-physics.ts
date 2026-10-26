/**
 * Force simulation, ported from the Personnel Cockpit's `classPhysicsStep` /
 * `runClassPhysics` / `resolveOverlaps` (`GraphPage.js`). Same forces, same
 * damping, same clustering-toward-the-seeded-centre trick — see the comment on
 * the cluster block for why a live centroid does not work.
 */

import type { GraphParams } from './event-graph-params';

export interface PhysicsNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** Seeded position. Cluster pull aims here, not at a live centroid. */
  homeX: number;
  homeY: number;
  pinned: boolean;
  physicsEnabled: boolean;
  /** Group this node belongs to under the current `clusterBy`. */
  clusterKey: string | null;
  radius: number;
}

export interface PhysicsEdge<N extends PhysicsNode = PhysicsNode> {
  from: N;
  to: N;
  linkWeight?: number;
  physicsLength?: number;
}

const EXTENT_PAD = 6;

export function resolveOverlaps<N extends PhysicsNode>(
  nodes: N[],
  { iterations = 120, minGap = 10 }: { iterations?: number; minGap?: number } = {},
): void {
  for (let iteration = 0; iteration < iterations; iteration++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        if (a.pinned && b.pinned) continue;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const distance = Math.hypot(dx, dy) || 0.01;
        const need = a.radius + EXTENT_PAD + b.radius + EXTENT_PAD + minGap;
        const overlap = need - distance;
        if (overlap <= 0) continue;
        const push = overlap * 0.55 + 0.5;
        if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) {
          dx = (j - i) * 0.37;
          dy = 1;
        }
        const nx = dx / distance;
        const ny = dy / distance;
        if (!a.pinned) {
          a.x -= nx * push * (b.pinned ? 1 : 0.5);
          a.y -= ny * push * (b.pinned ? 1 : 0.5);
          moved = true;
        }
        if (!b.pinned) {
          b.x += nx * push * (a.pinned ? 1 : 0.5);
          b.y += ny * push * (a.pinned ? 1 : 0.5);
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
}

function countDegrees<N extends PhysicsNode>(edges: PhysicsEdge<N>[]): void {
  const degree = new Map<string, number>();
  for (const edge of edges) {
    degree.set(edge.from.id, (degree.get(edge.from.id) || 0) + 1);
    degree.set(edge.to.id, (degree.get(edge.to.id) || 0) + 1);
  }
  for (const edge of edges) {
    edge.linkWeight =
      1 / Math.max(1, Math.min(degree.get(edge.from.id) || 1, degree.get(edge.to.id) || 1));
  }
}

export function physicsStep<N extends PhysicsNode>(
  nodes: N[],
  edges: PhysicsEdge<N>[],
  alpha: number,
  params: GraphParams,
): void {
  for (const node of nodes) {
    node.vx *= 0.68;
    node.vy *= 0.68;
  }

  if (edges.length && edges[0].linkWeight === undefined) countDegrees(edges);

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      if (!a.physicsEnabled && !b.physicsEnabled) continue;

      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let distance = Math.hypot(dx, dy);
      if (distance < 0.01) {
        dx = (j - i) * 0.37;
        dy = 1;
        distance = Math.hypot(dx, dy);
      }

      const minimumDistance = a.radius + b.radius + 54;
      let strength = (alpha * params.repulsion) / (distance * distance);
      if (distance < minimumDistance) {
        strength += ((minimumDistance - distance) / minimumDistance) * 1.2 * alpha;
      }
      const forceX = (dx / distance) * strength;
      const forceY = (dy / distance) * strength;
      if (a.physicsEnabled) {
        a.vx -= forceX;
        a.vy -= forceY;
      }
      if (b.physicsEnabled) {
        b.vx += forceX;
        b.vy += forceY;
      }
    }
  }

  for (const edge of edges) {
    const a = edge.from;
    const b = edge.to;
    if (!a.physicsEnabled && !b.physicsEnabled) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.hypot(dx, dy) || 0.01;
    if (!Number.isFinite(edge.physicsLength as number)) {
      edge.physicsLength = params.linkDistance;
    }
    const strength =
      (distance - (edge.physicsLength as number)) * 0.5 * (edge.linkWeight ?? 1) * alpha;
    const forceX = (dx / distance) * strength;
    const forceY = (dy / distance) * strength;
    if (a.physicsEnabled) {
      a.vx += forceX;
      a.vy += forceY;
    }
    if (b.physicsEnabled) {
      b.vx -= forceX;
      b.vy -= forceY;
    }
  }

  // Clustering anchors each group to where the seeding pass put it. Pulling
  // toward a live centroid cancels against all-pairs repulsion and the groups
  // end up evenly mixed; pulling toward the *seeded* centre keeps the sectors
  // intact while the simulation still handles spacing inside each one.
  if (params.clusterBy !== 'none' && params.clusterPull > 0) {
    const groups = new Map<string, { x: number; y: number; count: number }>();
    for (const node of nodes) {
      if (!node.clusterKey) continue;
      const entry = groups.get(node.clusterKey) ?? { x: 0, y: 0, count: 0 };
      entry.x += node.homeX;
      entry.y += node.homeY;
      entry.count += 1;
      groups.set(node.clusterKey, entry);
    }
    const pull = (params.clusterPull / 100) * 0.05;
    for (const node of nodes) {
      if (!node.physicsEnabled || !node.clusterKey) continue;
      const entry = groups.get(node.clusterKey);
      // A group of one has no centre to be drawn toward.
      if (!entry || entry.count < 2) continue;
      node.vx += (entry.x / entry.count - node.x) * pull * alpha;
      node.vy += (entry.y / entry.count - node.y) * pull * alpha;
    }
  }

  for (const node of nodes) {
    if (!node.physicsEnabled) {
      node.x = node.homeX;
      node.y = node.homeY;
      node.vx = 0;
      node.vy = 0;
      continue;
    }
    const speed = Math.hypot(node.vx, node.vy);
    if (speed > 10) {
      node.vx = (node.vx / speed) * 10;
      node.vy = (node.vy / speed) * 10;
    }
    node.x += node.vx;
    node.y += node.vy;
  }

  resolveOverlaps(nodes, { iterations: 2, minGap: params.nodeMinGap });
}

export function settlePhysicsSync<N extends PhysicsNode>(
  nodes: N[],
  edges: PhysicsEdge<N>[],
  params: GraphParams,
  { steps = 90 }: { steps?: number } = {},
): void {
  for (let step = 0; step < steps; step++) {
    physicsStep(nodes, edges, Math.max(0.04, 1 - step / steps), params);
  }
  resolveOverlaps(nodes, {
    iterations: Math.max(80, nodes.length * 4),
    minGap: params.nodeMinGap,
  });
}

/** Run the simulation on animation frames until `settleMs` elapses. */
export function runPhysics<N extends PhysicsNode>(
  nodes: N[],
  edges: PhysicsEdge<N>[],
  params: GraphParams,
  { onTick, onEnd }: { onTick?: () => void; onEnd?: () => void } = {},
): () => void {
  const started = performance.now();
  let rafId = 0;

  const stop = (complete = false) => {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    if (complete) {
      settlePhysicsSync(nodes, edges, params, { steps: 24 });
      onEnd?.();
    }
  };

  const tick = () => {
    const elapsed = performance.now() - started;
    if (elapsed >= params.settleMs) {
      stop(true);
      return;
    }
    physicsStep(nodes, edges, Math.max(0.04, 1 - elapsed / params.settleMs), params);
    onTick?.();
    rafId = requestAnimationFrame(tick);
  };

  rafId = requestAnimationFrame(tick);
  return () => stop(false);
}
