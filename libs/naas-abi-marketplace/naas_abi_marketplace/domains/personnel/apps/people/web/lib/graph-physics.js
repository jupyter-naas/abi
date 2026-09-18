/** Force layout for the ontology class graph (Cockpit 2D physics subset). */

export const ONTOLOGY_GRAPH_FOCUS_ID = "abi:Person";
export const ONTOLOGY_GRAPH_FOCUS_IRI = "http://ontology.naas.ai/abi/Person";

const BUCKET_ORDER = [
  "Material Entity",
  "Process",
  "Temporal Region",
  "Site",
  "Quality",
  "Realizable",
  "GDC",
  "Entity",
  "Unknown",
];

export function resolveOverlaps(nodes, { iterations = 80, minGap = 10, nodeRadius = 30 } = {}) {
  const diameter = nodeRadius * 2 + minGap;
  for (let iter = 0; iter < iterations; iter += 1) {
    let moved = false;
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        if (a.pinned && b.pinned) continue;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        if (dist >= diameter) continue;
        const push = (diameter - dist) / 2;
        dx /= dist;
        dy /= dist;
        if (!a.pinned && !b.pinned) {
          a.x -= dx * push;
          a.y -= dy * push;
          b.x += dx * push;
          b.y += dy * push;
        } else if (a.pinned) {
          b.x += dx * push * 2;
          b.y += dy * push * 2;
        } else {
          a.x -= dx * push * 2;
          a.y -= dy * push * 2;
        }
        moved = true;
      }
    }
    if (!moved) break;
  }
}

function clusterKeyOf(node, clusterBy) {
  if (clusterBy === "bucket") {
    return node.bfo_bucket || node.bfoBucket || "Unknown";
  }
  return null;
}

export function seedOntologyLayout(nodes, params, { nodeRadius = 30 } = {}) {
  const clusterRadius = nodeRadius + params.nodeMinGap;
  const bucketGroups = new Map();
  for (const node of nodes) {
    const key = clusterKeyOf(node, params.clusterBy) || "all";
    if (!bucketGroups.has(key)) bucketGroups.set(key, []);
    bucketGroups.get(key).push(node);
  }

  const keys =
    params.clusterBy === "bucket"
      ? [...bucketGroups.keys()].sort(
          (a, b) => BUCKET_ORDER.indexOf(a) - BUCKET_ORDER.indexOf(b),
        )
      : ["all"];

  const rootRadius = Math.max(220, keys.length * (clusterRadius * 3.2));

  keys.forEach((key, index) => {
    const members = bucketGroups.get(key) || nodes;
    const angle = (index / Math.max(keys.length, 1)) * Math.PI * 2;
    const cx = Math.cos(angle) * rootRadius;
    const cy = Math.sin(angle) * rootRadius;
    members.forEach((node, memberIndex) => {
      const ring = clusterRadius * (1 + Math.floor(memberIndex / 6) * 0.85);
      const memberAngle = (memberIndex / Math.max(members.length, 1)) * Math.PI * 2;
      node.x = cx + Math.cos(memberAngle) * ring;
      node.y = cy + Math.sin(memberAngle) * ring;
      node.homeX = node.x;
      node.homeY = node.y;
      node.physicsEnabled = true;
      node.vx = 0;
      node.vy = 0;
    });
  });

  if (params.clusterBy === "none") {
    const radius = Math.min(900, 700) * 0.32;
    nodes.forEach((node, index) => {
      const a = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
      node.x = Math.cos(a) * radius;
      node.y = Math.sin(a) * radius;
      node.homeX = node.x;
      node.homeY = node.y;
      node.physicsEnabled = true;
    });
  }

  resolveOverlaps(nodes, {
    iterations: Math.max(60, nodes.length * 4),
    minGap: params.nodeMinGap,
    nodeRadius,
  });
}

function physicsStep(nodes, edges, params, alpha, nodeRadius) {
  for (const node of nodes) {
    node.vx = (node.vx || 0) * 0.68;
    node.vy = (node.vy || 0) * 0.68;
  }

  if (!edges.degreesCounted) {
    const degree = new Map();
    for (const edge of edges) {
      degree.set(edge.a.id, (degree.get(edge.a.id) || 0) + 1);
      degree.set(edge.b.id, (degree.get(edge.b.id) || 0) + 1);
    }
    for (const edge of edges) {
      edge.linkWeight =
        1 / Math.max(1, Math.min(degree.get(edge.a.id) || 1, degree.get(edge.b.id) || 1));
    }
    edges.degreesCounted = true;
  }

  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
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
      const minimumDistance = nodeRadius * 2 + 54;
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
    const a = edge.a;
    const b = edge.b;
    if (!a.physicsEnabled && !b.physicsEnabled) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.hypot(dx, dy) || 0.01;
    if (!Number.isFinite(edge.physicsLength)) {
      edge.physicsLength = params.linkDistance;
    }
    const strength = (distance - edge.physicsLength) * 0.5 * (edge.linkWeight ?? 1) * alpha;
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

  if (params.clusterBy !== "none" && params.clusterPull > 0) {
    const groups = new Map();
    for (const node of nodes) {
      const key = clusterKeyOf(node, params.clusterBy);
      if (!key) continue;
      const entry = groups.get(key) || { x: 0, y: 0, count: 0 };
      entry.x += node.homeX ?? node.x;
      entry.y += node.homeY ?? node.y;
      entry.count += 1;
      groups.set(key, entry);
    }
    const pull = (params.clusterPull / 100) * 0.05;
    for (const node of nodes) {
      if (!node.physicsEnabled) continue;
      const entry = groups.get(clusterKeyOf(node, params.clusterBy));
      if (!entry || entry.count < 2) continue;
      node.vx += (entry.x / entry.count - node.x) * pull * alpha;
      node.vy += (entry.y / entry.count - node.y) * pull * alpha;
    }
  }

  for (const node of nodes) {
    if (node.pinned) {
      node.x = node.homeX ?? node.x;
      node.y = node.homeY ?? node.y;
      node.vx = 0;
      node.vy = 0;
      continue;
    }
    if (!node.physicsEnabled) continue;
    const speed = Math.hypot(node.vx, node.vy);
    if (speed > 10) {
      node.vx = (node.vx / speed) * 10;
      node.vy = (node.vy / speed) * 10;
    }
    node.x += node.vx;
    node.y += node.vy;
  }

  resolveOverlaps(nodes, { iterations: 2, minGap: params.nodeMinGap, nodeRadius });
}

export function settleLayoutSync(nodes, edges, params, { nodeRadius = 30, steps = 90 } = {}) {
  for (let step = 0; step < steps; step += 1) {
    const alpha = Math.max(0.04, 1 - step / steps);
    physicsStep(nodes, edges, params, alpha, nodeRadius);
  }
  resolveOverlaps(nodes, {
    iterations: Math.max(60, nodes.length * 4),
    minGap: params.nodeMinGap,
    nodeRadius,
  });
}

export function anchorOntologyFocusNode(
  nodes,
  {
    focusId = ONTOLOGY_GRAPH_FOCUS_ID,
    focusIri = ONTOLOGY_GRAPH_FOCUS_IRI,
  } = {},
) {
  const focus =
    nodes.find((node) => node.id === focusId) ||
    nodes.find((node) => node.iri === focusIri) ||
    null;
  if (!focus) return null;

  const dx = -focus.x;
  const dy = -focus.y;
  for (const node of nodes) {
    node.x += dx;
    node.y += dy;
    node.homeX = node.x;
    node.homeY = node.y;
  }
  focus.x = 0;
  focus.y = 0;
  focus.homeX = 0;
  focus.homeY = 0;
  focus.pinned = true;
  focus.physicsEnabled = false;
  focus.vx = 0;
  focus.vy = 0;
  return focus;
}

export function runLayoutSimulation(
  nodes,
  edges,
  params,
  { nodeRadius = 30, onFrame, onEnd } = {},
) {
  const started = performance.now();
  let rafId = 0;
  let ended = false;

  function finish() {
    if (ended) return;
    ended = true;
    onEnd?.();
  }

  function tick() {
    const elapsed = performance.now() - started;
    const alpha = Math.max(0.04, 1 - elapsed / Math.max(500, params.settleMs));
    physicsStep(nodes, edges, params, alpha, nodeRadius);
    onFrame?.();
    if (elapsed < params.settleMs && params.physics) {
      rafId = requestAnimationFrame(tick);
    } else {
      finish();
    }
  }

  if (params.physics) {
    rafId = requestAnimationFrame(tick);
  } else {
    settleLayoutSync(nodes, edges, params, { nodeRadius, steps: 90 });
    onFrame?.();
    finish();
  }

  return () => {
    if (rafId) cancelAnimationFrame(rafId);
  };
}

export function layoutOntologyGraph(graph, params, { nodeRadius = 30 } = {}) {
  const nodes = graph.nodes.map((node) => ({
    ...node,
    x: 0,
    y: 0,
    vx: 0,
    vy: 0,
    pinned: false,
    physicsEnabled: true,
  }));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = graph.edges
    .filter((edge) => byId.has(edge.from) && byId.has(edge.to))
    .map((edge) => ({
      ...edge,
      a: byId.get(edge.from),
      b: byId.get(edge.to),
      predicateLabel: edge.label || edge.kind || "",
    }));

  edges.degreesCounted = false;
  seedOntologyLayout(nodes, params, { nodeRadius });
  if (params.physics) {
    settleLayoutSync(nodes, edges, params, {
      nodeRadius,
      steps: Math.max(30, Math.round(params.settleMs / 33)),
    });
  }
  const focus = anchorOntologyFocusNode(nodes);

  return { nodes, edges, focus };
}
