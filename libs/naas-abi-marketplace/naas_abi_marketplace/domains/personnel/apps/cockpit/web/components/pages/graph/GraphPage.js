/**
 * Graph page — acts of working around a focus person, with labeled relations.
 */

import { BFO_SEVEN, bfoColor } from "../processes/bfo-buckets.js";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const DISTANCE_KEY = "cockpit-graph-distance";
const HIDDEN_CLASSES_KEY = "cockpit-graph-hidden-classes";
const MAX_PROCESSES_PER_CLASS = 10;
const MIN_SCALE = 0.25;
const MAX_SCALE = 2.5;
const GRAPH_NODE_RADIUS = 36;
const NODE_LABEL_FONT_SIZE = 11;
const NODE_LABEL_LINE_HEIGHT = 13;
const PROCESS_ROOT_RADIUS = 320;
const PARAMS_KEY = "cockpit-graph-params";

/**
 * Live graph parameters. Everything the simulation and the initial view read
 * comes from here rather than from a constant, so the parameters panel can
 * change any of it and repaint without a reload.
 */
const GRAPH_PARAM_DEFS = {
  physics: {
    label: "Physics",
    type: "toggle",
    default: true,
    hint: "Run the force simulation. Off leaves every node where the layout first placed it.",
  },
  linkDistance: {
    label: "Link length",
    min: 80,
    max: 520,
    step: 10,
    default: 260,
    unit: "px",
    hint: "How far apart the simulation tries to hold two connected nodes. Raise it to stretch the graph out and leave room for the relation name written along each line.",
  },
  repulsion: {
    label: "Repulsion",
    min: 200,
    max: 9000,
    step: 100,
    default: 3200,
    unit: "",
    hint: "How strongly every node pushes all the others away, connected or not. Raise it to spread the whole graph outward.",
  },
  nodeMinGap: {
    label: "Node spacing",
    min: 0,
    max: 180,
    step: 5,
    default: 60,
    unit: "px",
    hint: "The closest two nodes are ever allowed to get. Nodes are pushed apart to honour it after every step, so it holds whatever the other settings are.",
  },
  settleMs: {
    label: "Settle time",
    min: 500,
    max: 12000,
    step: 500,
    default: 3000,
    unit: "ms",
    hint: "How long nodes keep moving before the layout freezes in place. Raise it if a crowded graph has not finished spreading out.",
  },
  zoom: {
    label: "Default zoom",
    min: 0.25,
    max: 2.5,
    step: 0.05,
    default: 1,
    unit: "×",
    hint: "Scale the canvas opens at, and returns to with the ⟲ button. The graph may extend past the edges — drag to pan.",
  },
};

// Hops are counted from the selected person, who roots the traversal — the
// acts of working are one hop out, not the origin.
const DISTANCE_HINT =
  "Hops out from the selected person, who roots the graph. 1 — what they bear or carry: acts of working, employee roles, missions, skills, profile document. 2 — what those acts reach: organization, site, temporal region, contract, remuneration. 3 — the instants bounding each temporal region.";

function defaultGraphParams() {
  return Object.fromEntries(
    Object.entries(GRAPH_PARAM_DEFS).map(([key, def]) => [key, def.default])
  );
}

function readStoredParams() {
  const params = defaultGraphParams();
  try {
    const stored = JSON.parse(sessionStorage.getItem(PARAMS_KEY) || "{}");
    for (const [key, def] of Object.entries(GRAPH_PARAM_DEFS)) {
      const value = stored[key];
      if (def.type === "toggle") {
        if (typeof value === "boolean") params[key] = value;
      } else if (Number.isFinite(value)) {
        params[key] = Math.min(def.max, Math.max(def.min, value));
      }
    }
  } catch {
    // Malformed storage falls back to defaults.
  }
  return params;
}

// Mutated in place by the panel; the simulation reads it every tick.
const graphParams = readStoredParams();
// The gap floor is enforced positionally every tick — see graphParams.nodeMinGap.
// The repulsion force alone could not guarantee it: it is scaled by alpha, so
// as the simulation cools the push fades and nodes settle packed.

function buildGraphIndex(data) {
  const peopleById = Object.fromEntries((data.people || []).map((p) => [p.id, p]));
  const processesById = Object.fromEntries((data.processes || []).map((p) => [p.id, p]));
  const entitiesById = Object.fromEntries((data.entities || []).map((e) => [e.id, e]));
  const workingHubByPerson = new Map();
  const personToProcesses = new Map();
  const relations = data.relations || [];

  for (const rel of relations) {
    if (rel.predicateLabel === "has working" && peopleById[rel.from] && entitiesById[rel.to]?.isWorkingHub) {
      workingHubByPerson.set(rel.from, rel.to);
    }
    if (rel.predicateLabel === "Employee" && peopleById[rel.from] && processesById[rel.to]) {
      if (!personToProcesses.has(rel.from)) personToProcesses.set(rel.from, []);
      personToProcesses.get(rel.from).push(rel.to);
    }
  }

  const suppressedIds = suppressOldProcesses([
    ...Object.values(entitiesById),
    ...Object.values(processesById),
  ]);

  return {
    peopleById,
    processesById,
    entitiesById,
    relations,
    suppressedIds,
    workingHubByPerson,
    personToProcesses,
  };
}

/** ISO start of a record's temporal region — the ordering key for "most recent". */
function recencyKey(record) {
  return record?.startedAt || record?.endedAt || "";
}

/** Every process occupies a temporal region, so BFO bucket alone identifies one. */
function isProcessRecord(record) {
  return record?.bfoBucket === "Process";
}

/**
 * Keep only the {@link MAX_PROCESSES_PER_CLASS} most recent processes of each
 * class and return the ids of the rest. Suppressed processes are removed from
 * the relation graph before traversal, so nothing is reached through them.
 */
function suppressOldProcesses(records, limit = MAX_PROCESSES_PER_CLASS) {
  const byClass = new Map();
  for (const record of records) {
    if (!isProcessRecord(record)) continue;
    const key = record.classLabel || "Process";
    const list = byClass.get(key) || [];
    list.push(record);
    byClass.set(key, list);
  }

  const suppressed = new Set();
  for (const list of byClass.values()) {
    if (list.length <= limit) continue;
    const ordered = [...list].sort(
      (a, b) =>
        recencyKey(b).localeCompare(recencyKey(a)) || String(a.id).localeCompare(String(b.id))
    );
    for (const record of ordered.slice(limit)) suppressed.add(record.id);
  }
  return suppressed;
}

function collectVisibleGraph(adj, rootId, distance) {
  const maxDistance = Math.max(1, Math.floor(distance));
  const suppressed = adj.suppressedIds || new Set();
  const relations = (adj.relations || [])
    .filter((rel) => rel.canvas !== false)
    .filter((rel) => !suppressed.has(rel.from) && !suppressed.has(rel.to));
  const adjacency = new Map();

  for (const rel of relations) {
    const fromRelations = adjacency.get(rel.from) || [];
    fromRelations.push(rel);
    adjacency.set(rel.from, fromRelations);
    const toRelations = adjacency.get(rel.to) || [];
    toRelations.push(rel);
    adjacency.set(rel.to, toRelations);
  }

  // True graph distance: ring 1 contains every class/process directly linked
  // to the selected person, ring 2 their neighbours, and so on.
  const nodeDistance = new Map([[rootId, 0]]);
  const queue = [rootId];
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const nodeId = queue[cursor];
    const currentDistance = nodeDistance.get(nodeId);
    if (currentDistance >= maxDistance) continue;
    for (const rel of adjacency.get(nodeId) || []) {
      const neighbourId = rel.from === nodeId ? rel.to : rel.from;
      if (nodeDistance.has(neighbourId)) continue;
      nodeDistance.set(neighbourId, currentDistance + 1);
      queue.push(neighbourId);
    }
  }

  const active = new Set(nodeDistance.keys());
  const visibleRelations = relations.filter(
    (rel) => active.has(rel.from) && active.has(rel.to)
  );

  return {
    people: [...active].map((id) => adj.peopleById[id]).filter(Boolean),
    processes: [...active].map((id) => adj.processesById?.[id]).filter(Boolean),
    entities: [...active].map((id) => adj.entitiesById[id]).filter(Boolean),
    relations: visibleRelations,
  };
}

/**
 * Distinct classes present in a visible set, with counts and BFO bucket. The
 * list is derived from whatever the current distance reaches, so it grows as
 * the distance grows.
 */
function visibleClassOptions(visible) {
  const byLabel = new Map();
  const add = (record, fallbackBucket) => {
    if (!record) return;
    const label = record.classLabel || fallbackBucket || "Unknown";
    const entry = byLabel.get(label) || {
      label,
      bucket: record.bfoBucket || fallbackBucket || "Unknown",
      count: 0,
    };
    entry.count += 1;
    byLabel.set(label, entry);
  };
  for (const person of visible.people || []) add(person, "Material Entity");
  for (const entity of visible.entities || []) add(entity, "Process");
  for (const process of visible.processes || []) add(process, "Process");
  return [...byLabel.values()].sort(
    (a, b) => a.bucket.localeCompare(b.bucket) || a.label.localeCompare(b.label)
  );
}

/**
 * Drop every node whose class the user has deselected, plus any relation left
 * dangling. The focus person is always kept — it anchors the canvas.
 */
function applyClassFilter(visible, hiddenClasses, focusPersonId) {
  if (!hiddenClasses || hiddenClasses.size === 0) return visible;
  const visibleClass = (record) => !hiddenClasses.has(record.classLabel || "");
  const people = (visible.people || []).filter(
    (person) => person.id === focusPersonId || visibleClass(person)
  );
  const entities = (visible.entities || []).filter(visibleClass);
  const processes = (visible.processes || []).filter(visibleClass);
  const liveIds = new Set(
    [...people, ...entities, ...processes].map((record) => record.id)
  );
  return {
    people,
    entities,
    processes,
    relations: (visible.relations || []).filter(
      (rel) => liveIds.has(rel.from) && liveIds.has(rel.to)
    ),
  };
}

function renderPropertiesTable(properties) {
  // Property and label share a cell, stacked. As separate columns they left
  // the narrow inspector too little room and broke URIs mid-token.
  const rows = (properties || [])
    .map(
      (p) => `<tr>
        <td class="graph-prop-name">
          <span class="graph-prop-uri">${esc(p.uri || "—")}</span>
          <span class="graph-prop-label">${esc(p.label || "—")}</span>
        </td>
        <td>${esc(p.value)}</td>
      </tr>`
    )
    .join("");
  if (!rows) return `<p class="empty">No data properties on this node.</p>`;
  return `<table class="graph-props"><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderBfoBadge(bucketType) {
  const def = bfoColor(bucketType);
  return `<span class="graph-bfo-badge" style="--bfo-color:${def.color};--bfo-border:${def.border}">${esc(def.label)}</span>`;
}

function renderNodeDetail(node, { focusPersonId } = {}) {
  if (!node) return `<h2>Selection</h2><p class="empty">Select a node on the canvas.</p>`;
  if (node.kind === "person") {
    const person = node.person;
    return `<h2>${esc(person.label)}${node.isFocus ? " · focus" : ""}</h2>
      <dl><dt>Class</dt><dd>Person</dd><dt>BFO bucket</dt><dd>${renderBfoBadge("Material Entity")}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(person.properties)}`;
  }
  if (node.kind === "entity") {
    const entity = node.entity;
    return `<h2>${esc(entity.label)}</h2>
      <dl><dt>Class</dt><dd>${esc(entity.classLabel)}</dd><dt>BFO bucket</dt><dd>${renderBfoBadge(entity.bfoBucket)}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(entity.properties)}`;
  }
  if (node.kind === "process") {
    const process = node.process;
    return `<h2>${esc(process.classLabel || "Process")}</h2>
      <dl><dt>BFO bucket</dt><dd>${renderBfoBadge(process.bfoBucket || "Process")}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(process.properties)}`;
  }
  if (node.kind === "source") {
    const source = node.source;
    return `<h2>${esc(source.classLabel || "Source")}</h2>
      <dl><dt>BFO bucket</dt><dd>${renderBfoBadge(source.bfoBucket || "Process")}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(source.properties)}`;
  }
  return renderNodeDetail(null);
}

function nodePalette(entity, { faded = false } = {}) {
  const bucket = entity.bfoBucket || (entity.nodeKind === "person" ? "Material Entity" : "Process");
  return bfoColor(bucket, { faded });
}

function resolveNode(id, lookup) {
  if (lookup.peopleById[id]) {
    const person = lookup.peopleById[id];
    return { id: `person:${person.id}`, kind: "person", person, label: person.label, palette: nodePalette(person) };
  }
  const process = lookup.processesById[id];
  if (process) {
    return {
      id: process.id,
      kind: "process",
      process,
      label: process.classLabel || "Process",
      palette: nodePalette(process, { faded: true }),
      dashed: true,
    };
  }
  if (lookup.entitiesById[id]) {
    const entity = lookup.entitiesById[id];
    return {
      id: entity.id,
      kind: "entity",
      entity,
      label: entity.label,
      palette: nodePalette(entity),
      isWorkingHub: entity.isWorkingHub,
    };
  }
  return null;
}

function graphNodeRadius(_n) {
  return GRAPH_NODE_RADIUS;
}

function truncateLine(line, maxChars, forceEllipsis = false) {
  if (!forceEllipsis && line.length <= maxChars) return line;
  if (maxChars <= 1) return "…";
  if (forceEllipsis && line.length < maxChars) return `${line}…`;
  return `${line.slice(0, maxChars - 1)}…`;
}

function hardBreakToken(token, maxChars) {
  if (token.length <= maxChars) return [token];
  const chunks = [];
  let rest = token;
  while (rest.length > maxChars) {
    chunks.push(rest.slice(0, maxChars));
    rest = rest.slice(maxChars);
  }
  if (rest) chunks.push(rest);
  return chunks;
}

function wrapWordLabel(label, maxCharsPerLine, maxLines) {
  const words = label.split(" ");
  const lines = [];
  let current = "";
  let wordIndex = 0;

  const pushCurrent = () => {
    if (!current) return;
    lines.push(truncateLine(current, maxCharsPerLine));
    current = "";
  };

  while (wordIndex < words.length && lines.length < maxLines) {
    const word = words[wordIndex];
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxCharsPerLine) {
      current = candidate;
      wordIndex += 1;
      continue;
    }

    pushCurrent();
    if (lines.length >= maxLines) break;

    if (word.length <= maxCharsPerLine) {
      current = word;
      wordIndex += 1;
      continue;
    }

    let rest = word;
    while (rest.length > 0 && lines.length < maxLines) {
      if (rest.length <= maxCharsPerLine) {
        current = rest;
        rest = "";
        break;
      }
      lines.push(truncateLine(rest.slice(0, maxCharsPerLine), maxCharsPerLine));
      rest = rest.slice(maxCharsPerLine);
    }
    wordIndex += 1;
  }

  if (lines.length < maxLines && current) {
    lines.push(truncateLine(current, maxCharsPerLine));
    current = "";
  }

  const truncated = wordIndex < words.length || Boolean(current);
  const result = lines.slice(0, maxLines);
  if (truncated && result.length > 0) {
    const last = result[result.length - 1];
    result[result.length - 1] = truncateLine(last, maxCharsPerLine, true);
  }
  return result;
}

function wrapNodeLabelLines(label, maxCharsPerLine, maxLines) {
  const normalized = (label || "").trim().replace(/\s+/g, " ");
  if (!normalized) return [""];
  if (normalized.length <= maxCharsPerLine && maxLines >= 1) {
    return [truncateLine(normalized, maxCharsPerLine)];
  }
  const lines = wrapWordLabel(normalized, maxCharsPerLine, maxLines);
  if (lines.length > 0) return lines;
  return [truncateLine(normalized, maxCharsPerLine)];
}

function nodeLabelLayout(n) {
  const maxWidth = GRAPH_NODE_RADIUS * 1.75;
  const maxCharsPerLine = Math.max(4, Math.floor(maxWidth / (NODE_LABEL_FONT_SIZE * 0.52)));
  const maxLines = Math.max(1, Math.floor((GRAPH_NODE_RADIUS * 1.55) / NODE_LABEL_LINE_HEIGHT));
  return {
    fontSize: NODE_LABEL_FONT_SIZE,
    lineHeight: NODE_LABEL_LINE_HEIGHT,
    lines: wrapNodeLabelLines(n.label, maxCharsPerLine, maxLines),
  };
}

function graphNodeExtent(_n) {
  const pad = 6;
  return { rx: GRAPH_NODE_RADIUS + pad, ry: GRAPH_NODE_RADIUS + pad };
}

function resolveOverlaps(
  nodes,
  { iterations = 120, pinnedIds = new Set(), minGap = 10 } = {}
) {
  for (let iter = 0; iter < iterations; iter++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const aPinned = a.pinned || pinnedIds.has(a.id);
        const bPinned = b.pinned || pinnedIds.has(b.id);
        if (aPinned && bPinned) continue;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        const ea = graphNodeExtent(a);
        const eb = graphNodeExtent(b);
        const need = ea.rx + eb.rx + minGap;
        const overlap = need - dist;
        if (overlap <= 0) continue;
        const push = overlap * 0.55 + 0.5;
        if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) {
          dx = (j - i) * 0.37;
          dy = 1;
        }
        const nx = dx / dist;
        const ny = dy / dist;
        if (!aPinned) {
          a.x -= nx * push * (bPinned ? 1 : 0.5);
          a.y -= ny * push * (bPinned ? 1 : 0.5);
          moved = true;
        }
        if (!bPinned) {
          b.x += nx * push * (aPinned ? 1 : 0.5);
          b.y += ny * push * (aPinned ? 1 : 0.5);
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
}

function seedSemanticLayout(focusNode, workingNode, nodes, edges, focusPersonId) {
  focusNode.x = 0;
  focusNode.y = 0;
  const processRoots = nodes
    .filter(
      (node) =>
        node.id !== focusNode.id &&
        (node.isWorkingHub || node.kind === "process")
    )
    .sort((a, b) => {
      const priority = (node) => {
        if (node.id === workingNode?.id) return 0;
        if (node.isWorkingHub) return 1;
        return 2;
      };
      return priority(a) - priority(b) || a.label.localeCompare(b.label) || a.id.localeCompare(b.id);
    });

  if (processRoots.length === 0) {
    const others = nodes.filter((node) => node.id !== focusNode.id);
    others.forEach((node, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(1, others.length);
      const radius = 170 + Math.floor(index / 8) * 170;
      node.x = Math.cos(angle) * radius;
      node.y = Math.sin(angle) * radius;
      node.rayId = null;
      node.radialLevel = Math.floor(index / 8) + 1;
    });
    for (const node of nodes) {
      node.homeX = node.x;
      node.homeY = node.y;
      node.physicsEnabled = node.id !== focusNode.id;
    }
    return;
  }

  const rootIds = new Set(processRoots.map((node) => node.id));
  const rootRank = new Map(processRoots.map((node, index) => [node.id, index]));
  const adjacency = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    if (edge.hidden) continue;
    adjacency.get(edge.a.id)?.push(edge.b);
    adjacency.get(edge.b.id)?.push(edge.a);
  }
  for (const neighbours of adjacency.values()) {
    neighbours.sort((a, b) => a.id.localeCompare(b.id));
  }

  // Assign every class to its nearest process without traversing through the
  // centered person, which would otherwise merge otherwise distinct rays.
  const assignments = new Map();
  const queue = [];
  for (const root of processRoots) {
    assignments.set(root.id, { rootId: root.id, hop: 0 });
    queue.push(root);
  }
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const node = queue[cursor];
    const current = assignments.get(node.id);
    for (const neighbour of adjacency.get(node.id) || []) {
      if (neighbour.id === focusNode.id || rootIds.has(neighbour.id)) continue;
      const candidate = { rootId: current.rootId, hop: current.hop + 1 };
      const existing = assignments.get(neighbour.id);
      const candidateRank = rootRank.get(candidate.rootId);
      const existingRank = existing ? rootRank.get(existing.rootId) : Infinity;
      if (
        !existing ||
        candidate.hop < existing.hop ||
        (candidate.hop === existing.hop && candidateRank < existingRank)
      ) {
        assignments.set(neighbour.id, candidate);
        queue.push(neighbour);
      }
    }
  }

  // Source-only or disconnected nodes still receive a stable ray.
  const unassigned = nodes
    .filter((node) => node.id !== focusNode.id && !assignments.has(node.id))
    .sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  unassigned.forEach((node, index) => {
    const root = processRoots[index % processRoots.length];
    assignments.set(node.id, { rootId: root.id, hop: 1 });
  });

  const minimumRootSpacing = GRAPH_NODE_RADIUS * 2 + 48;
  const rootRadius =
    processRoots.length === 1
      ? PROCESS_ROOT_RADIUS
      : Math.max(
          PROCESS_ROOT_RADIUS,
          minimumRootSpacing / (2 * Math.sin(Math.PI / processRoots.length))
        );
  const ringGap = 180;
  const sectorSize = (Math.PI * 2) / processRoots.length;
  const sectorSpan =
    processRoots.length === 1 ? Math.PI * 1.5 : Math.min(Math.PI * 0.8, sectorSize * 0.72);

  const bucketOrder = [
    "Site",
    "Temporal Region",
    "Quality",
    "Realizable",
    "GDC",
    "Material Entity",
    "Process",
  ];
  const bucketRank = (node) => {
    const bucket =
      node.entity?.bfoBucket || node.person?.bfoBucket || node.process?.bfoBucket || "";
    const index = bucketOrder.indexOf(bucket);
    return index === -1 ? bucketOrder.length : index;
  };

  processRoots.forEach((root, rayIndex) => {
    const rayAngle = rayIndex * sectorSize;
    root.x = Math.cos(rayAngle) * rootRadius;
    root.y = Math.sin(rayAngle) * rootRadius;
    root.rayId = root.id;
    root.radialLevel = 1;
    root.isProcessAnchor = true;

    const members = nodes
      .filter(
        (node) =>
          node.id !== focusNode.id &&
          node.id !== root.id &&
          assignments.get(node.id)?.rootId === root.id
      )
      .sort((a, b) => {
        const assignmentA = assignments.get(a.id);
        const assignmentB = assignments.get(b.id);
        return (
          assignmentA.hop - assignmentB.hop ||
          bucketRank(a) - bucketRank(b) ||
          a.label.localeCompare(b.label) ||
          a.id.localeCompare(b.id)
        );
      });

    const levels = new Map();
    for (const node of members) {
      const minimumLevel = Math.max(2, assignments.get(node.id).hop + 1);
      let level = minimumLevel;
      while ((levels.get(level)?.length || 0) >= 2 ** (level - 1)) level += 1;
      const levelNodes = levels.get(level) || [];
      levelNodes.push(node);
      levels.set(level, levelNodes);
    }

    for (const [level, levelNodes] of levels.entries()) {
      const radius = rootRadius + (level - 1) * ringGap;
      levelNodes.forEach((node, index) => {
        const offset =
          levelNodes.length === 1
            ? 0
            : -sectorSpan / 2 + (sectorSpan * index) / (levelNodes.length - 1);
        const angle = rayAngle + offset;
        node.x = Math.cos(angle) * radius;
        node.y = Math.sin(angle) * radius;
        node.rayId = root.id;
        node.radialLevel = level;
      });
    }
  });

  resolveOverlaps(nodes, {
    iterations: Math.max(120, nodes.length * 6),
    pinnedIds: new Set([focusNode.id].filter(Boolean)),
    minGap: graphParams.nodeMinGap,
  });
  for (const node of nodes) {
    node.homeX = node.x;
    node.homeY = node.y;
    // Everything but the focus is simulated — the focus stays put so the
    // canvas keeps a stable centre to fit and pan around.
    node.physicsEnabled = node.id !== focusNode.id;
  }
}

function directedEdgeKey(fromId, toId) {
  return `${fromId}\x00${toId}`;
}

function canonicalPairKey(idA, idB) {
  return idA < idB ? `${idA}\x00${idB}` : `${idB}\x00${idA}`;
}

function splitCanonicalPair(key) {
  const sep = key.indexOf("\0");
  return [key.slice(0, sep), key.slice(sep + 1)];
}

/** Roundness values for parallel edges between the same node pair (max 0.6). Ported from Nexus vis-network. */
function computeParallelEdgeRoundness(count) {
  if (count <= 0) return [];
  if (count === 1) return [0];
  if (count === 2) return [0.28, -0.28];

  const pairCount = Math.floor(count / 2);
  const hasCenter = count % 2 === 1;
  const tierOffset = hasCenter ? 1 : 0;
  const baseRoundness = 0.18;
  const roundnessStep = 0.12;
  const maxRoundness = 0.6;

  const values = [];
  for (let tier = 1; tier <= pairCount; tier++) {
    const r = Math.min(maxRoundness, baseRoundness + (tier + tierOffset - 1) * roundnessStep);
    values.push(r, -r);
  }
  if (hasCenter) {
    values.splice(Math.floor(values.length / 2), 0, 0);
  }
  return values;
}

/** Assign non-overlapping curved/straight routing per edge within each undirected node pair. */
function annotateEdgeCurves(edges) {
  const groups = new Map();
  let idx = 0;

  for (const edge of edges) {
    if (edge.hidden) {
      edge.curveConfig = { enabled: false };
      continue;
    }
    edge.edgeId =
      edge.edgeId || `${edge.a.id}\0${edge.b.id}\0${edge.predicateLabel || ""}\0${idx++}`;
    const key = canonicalPairKey(edge.a.id, edge.b.id);
    const list = groups.get(key) ?? [];
    list.push(edge);
    groups.set(key, list);
  }

  for (const [key, group] of groups.entries()) {
    if (group.length <= 1) {
      if (group.length === 1) group[0].curveConfig = { enabled: false };
      continue;
    }

    const sorted = [...group].sort((a, b) => a.edgeId.localeCompare(b.edgeId));
    const roundnesses = computeParallelEdgeRoundness(sorted.length);
    const [canonicalA, canonicalB] = splitCanonicalPair(key);

    const forward = sorted.filter((e) => e.a.id === canonicalA && e.b.id === canonicalB);
    const reverse = sorted.filter((e) => e.a.id === canonicalB && e.b.id === canonicalA);

    if (forward.length > 0 && reverse.length > 0) {
      // Bidirectional inverses: same curve direction so mirrored routes do not overlap.
      let roundIdx = 0;
      for (const edge of [...forward, ...reverse]) {
        const magnitude = Math.abs(roundnesses[roundIdx] ?? roundnesses.at(-1) ?? 0.1) || 0.1;
        edge.curveConfig = { enabled: true, type: "curvedCW", roundness: magnitude };
        roundIdx += 1;
      }
      continue;
    }

    sorted.forEach((edge, i) => {
      const magnitude = Math.abs(roundnesses[i] ?? 0);
      if (magnitude === 0) {
        edge.curveConfig = { enabled: false };
        return;
      }
      edge.curveConfig = {
        enabled: true,
        type: i % 2 === 0 ? "curvedCW" : "curvedCCW",
        roundness: magnitude,
      };
    });
  }
}

function nodeBoundaryPoint(from, to, radius) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dist = Math.hypot(dx, dy) || 1;
  return {
    x: from.x + (dx / dist) * radius,
    y: from.y + (dy / dist) * radius,
  };
}

function pointOnQuadratic(t, start, control, end) {
  const u = 1 - t;
  return {
    x: u * u * start.x + 2 * u * t * control.x + t * t * end.x,
    y: u * u * start.y + 2 * u * t * control.y + t * t * end.y,
  };
}

function tangentOnQuadratic(t, start, control, end) {
  const u = 1 - t;
  return {
    x: 2 * u * (control.x - start.x) + 2 * t * (end.x - control.x),
    y: 2 * u * (control.y - start.y) + 2 * t * (end.y - control.y),
  };
}

function edgeGeometry(edge) {
  const startRadius = graphNodeRadius(edge.a) + 4;
  const endRadius = graphNodeRadius(edge.b) + 4;
  const start = nodeBoundaryPoint(edge.a, edge.b, startRadius);
  const end = nodeBoundaryPoint(edge.b, edge.a, endRadius);
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const len = Math.hypot(dx, dy) || 1;
  const normalX = -dy / len;
  const normalY = dx / len;
  const cfg = edge.curveConfig || { enabled: false };
  if (!cfg.enabled || !cfg.roundness) {
    return { start, end, control: { x: midX, y: midY }, curved: false };
  }
  const sign = cfg.type === "curvedCCW" ? -1 : 1;
  const offset = cfg.roundness * len;
  return {
    start,
    end,
    control: { x: midX + normalX * offset * sign, y: midY + normalY * offset * sign },
    curved: true,
  };
}

function classPhysicsStep(nodes, edges, alpha) {
  for (const node of nodes) {
    node.vx = (node.vx || 0) * 0.68;
    node.vy = (node.vy || 0) * 0.68;
  }

  if (!edges.degreesCounted) {
    const degree = new Map();
    for (const edge of edges) {
      if (edge.hidden) continue;
      degree.set(edge.a.id, (degree.get(edge.a.id) || 0) + 1);
      degree.set(edge.b.id, (degree.get(edge.b.id) || 0) + 1);
    }
    for (const edge of edges) {
      edge.linkWeight =
        1 / Math.max(1, Math.min(degree.get(edge.a.id) || 1, degree.get(edge.b.id) || 1));
    }
    edges.degreesCounted = true;
  }

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

      const minimumDistance = GRAPH_NODE_RADIUS * 2 + 54;
      let strength = (alpha * graphParams.repulsion) / (distance * distance);
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
    if (edge.hidden) continue;
    const a = edge.a;
    const b = edge.b;
    if (!a.physicsEnabled && !b.physicsEnabled) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.hypot(dx, dy) || 0.01;
    if (!Number.isFinite(edge.physicsLength)) {
      // A uniform target length. Freezing the seeded distance here made every
      // edge start at rest, so the simulation had no work to do and the seed
      // was the layout — which is why nothing ever appeared to move.
      edge.physicsLength = graphParams.linkDistance;
    }
    const strength =
      (distance - edge.physicsLength) * 0.5 * (edge.linkWeight ?? 1) * alpha;
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

  for (const node of nodes) {
    if (!node.physicsEnabled) {
      node.x = node.homeX;
      node.y = node.homeY;
      node.vx = 0;
      node.vy = 0;
      continue;
    }

    // No tether: the seeded ray is a starting point only, and the link and
    // repulsion forces decide where every node ends up.
    const speed = Math.hypot(node.vx, node.vy);
    if (speed > 10) {
      node.vx = (node.vx / speed) * 10;
      node.vy = (node.vy / speed) * 10;
    }
    node.x += node.vx;
    node.y += node.vy;
  }

  resolveOverlaps(nodes, { iterations: 2, minGap: graphParams.nodeMinGap });
}

function settleClassPhysicsSync(nodes, edges, focusNode, { steps = 90 } = {}) {
  for (let step = 0; step < steps; step++) {
    const alpha = Math.max(0.04, 1 - step / steps);
    classPhysicsStep(nodes, edges, alpha);
  }
  resolveOverlaps(nodes, {
    iterations: Math.max(80, nodes.length * 4),
    pinnedIds: new Set([focusNode.id].filter(Boolean)),
  });
}

function runClassPhysics(
  nodes,
  edges,
  focusNode,
  { onTick, onEnd, maxMs = graphParams.settleMs } = {}
) {
  const started = performance.now();
  let rafId = 0;

  const stop = (complete = false) => {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    if (complete) {
      settleClassPhysicsSync(nodes, edges, focusNode, { steps: 24 });
      onEnd?.();
    }
  };

  const tick = () => {
    const elapsed = performance.now() - started;
    if (elapsed >= maxMs) {
      stop(true);
      return;
    }
    const alpha = Math.max(0.04, 1 - elapsed / maxMs);
    classPhysicsStep(nodes, edges, alpha);
    onTick?.();
    rafId = requestAnimationFrame(tick);
  };

  rafId = requestAnimationFrame(tick);
  return () => stop(false);
}

function buildGraph(focusPerson, visible, lookup) {
  const nodeMap = new Map();
  const addNode = (id, extra = {}) => {
    const base = resolveNode(id, lookup);
    if (!base || nodeMap.has(base.id)) return nodeMap.get(base.id);
    const node = { ...base, x: 0, y: 0, ...extra };
    nodeMap.set(node.id, node);
    return node;
  };

  const workingId =
    lookup.workingHubByPerson?.get?.(focusPerson.id) ||
    visible.entities.find((e) => e.isWorkingHub)?.id;
  const workingNode = workingId ? addNode(workingId, { isWorkingHub: true }) : null;
  const focusNode = addNode(focusPerson.id, { isFocus: true, pinned: true });

  for (const proc of visible.processes) addNode(proc.id);

  const edges = [];
  for (const rel of visible.relations) {
    const a = addNode(rel.from);
    const b = addNode(rel.to);
    if (!a || !b) continue;
    edges.push({ a, b, predicateLabel: rel.predicateLabel, hidden: rel.canvas === false });
  }

  annotateEdgeCurves(edges);

  const nodes = [...nodeMap.values()];
  focusNode.x = 0;
  focusNode.y = 0;

  return { nodes, edges, focusNode, workingNode };
}

export function layoutGraphNodes(focusPerson, visible, lookup) {
  const graph = buildGraph(focusPerson, visible, lookup);
  seedSemanticLayout(
    graph.focusNode,
    graph.workingNode,
    graph.nodes,
    graph.edges,
    focusPerson.id
  );
  return graph;
}

function countOverlaps(nodes) {
  let n = 0;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      const ea = graphNodeExtent(a);
      const eb = graphNodeExtent(b);
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      if (dist < ea.rx + eb.rx) n += 1;
    }
  }
  return n;
}

export {
  GRAPH_NODE_RADIUS,
  PROCESS_ROOT_RADIUS,
  graphNodeExtent,
  countOverlaps,
  MAX_PROCESSES_PER_CLASS,
  buildGraphIndex,
  collectVisibleGraph,
  visibleClassOptions,
  applyClassFilter,
  suppressOldProcesses,
  resolveNode,
  resolveOverlaps,
  seedSemanticLayout,
  settleClassPhysicsSync,
  computeParallelEdgeRoundness,
  annotateEdgeCurves,
  nodeLabelLayout,
  wrapNodeLabelLines,
};

/**
 * Open at 1:1 on the focus node. Fitting the whole graph in shrank it until the
 * relations between nodes were unreadable; at a standard zoom the labels are
 * legible and the canvas is pannable to reach the rest.
 */
function resetGraphView(canvas, focusNode, setPanScale) {
  const scale = graphParams.zoom;
  setPanScale({
    scale,
    panX: -(focusNode?.x ?? 0) * scale,
    panY: -(focusNode?.y ?? 0) * scale,
  });
}

function mountGraphCanvas(root, options) {
  const { focusPerson, visible, lookup } = options;
  const stage = root.querySelector("#graph-stage");
  const canvas = root.querySelector("#graph-canvas");
  const detail = root.querySelector("#graph-detail");
  const ctx = canvas.getContext("2d");
  const style = getComputedStyle(document.documentElement);
  const panel = style.getPropertyValue("--panel").trim() || "#fff";
  const colors = {
    ink: style.getPropertyValue("--ink").trim() || "#1a1f2b",
    muted: style.getPropertyValue("--muted").trim() || "#5c6578",
    panel,
    canvas: panel,
  };

  const { nodes, edges, focusNode } = layoutGraphNodes(focusPerson, visible, {
    ...lookup,
    workingHubByPerson: options.workingHubByPerson,
  });
  let selected = focusNode;
  let pan = { x: 0, y: 0 };
  let scale = 1;
  let dragging = null;
  let panning = null;
  let offset = { x: 0, y: 0 };
  let pointerStart = null;
  const layoutDone = true;
  let stopPhysics = null;

  function setPanScale({ scale: s, panX, panY }) {
    scale = s;
    pan.x = panX;
    pan.y = panY;
  }

  function showDetail(node) {
    if (!detail) return;
    if (!node) {
      detail.innerHTML = `<p class="graph-inspect-kicker">Inspect</p>${renderNodeDetail(null)}`;
      return;
    }
    detail.innerHTML = `<p class="graph-inspect-kicker">Inspect</p>${renderNodeDetail(node, { focusPersonId: focusPerson.id })}`;
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(stage.clientWidth * dpr);
    canvas.height = Math.floor(stage.clientHeight * dpr);
    canvas.style.width = `${stage.clientWidth}px`;
    canvas.style.height = `${stage.clientHeight}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (layoutDone) resetGraphView(canvas, focusNode, setPanScale);
    draw();
  }

  function screenToWorld(sx, sy) {
    return {
      x: (sx - canvas.clientWidth / 2 - pan.x) / scale,
      y: (sy - canvas.clientHeight / 2 - pan.y) / scale,
    };
  }

  function zoomAt(sx, sy, factor) {
    const wx = (sx - canvas.clientWidth / 2 - pan.x) / scale;
    const wy = (sy - canvas.clientHeight / 2 - pan.y) / scale;
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
    pan.x = sx - canvas.clientWidth / 2 - wx * scale;
    pan.y = sy - canvas.clientHeight / 2 - wy * scale;
    draw();
  }

  function nodeRadius(n) {
    return graphNodeRadius(n);
  }

  function drawEdgeLabel(text, x, y) {
    const fontSize = 10;
    ctx.font = `${fontSize}px var(--font-body), sans-serif`;
    const textW = ctx.measureText(text).width;
    const padX = 5;
    const padY = 3;
    const boxW = textW + padX * 2;
    const boxH = fontSize + padY * 2;
    ctx.fillStyle = colors.canvas;
    ctx.fillRect(x - boxW / 2, y - boxH / 2, boxW, boxH);
    ctx.fillStyle = colors.ink;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
  }

  function drawArrowhead(x, y, angle, size, color) {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(
      x - size * Math.cos(angle - Math.PI / 7),
      y - size * Math.sin(angle - Math.PI / 7)
    );
    ctx.lineTo(
      x - size * Math.cos(angle + Math.PI / 7),
      y - size * Math.sin(angle + Math.PI / 7)
    );
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  function drawEdge(e) {
    if (e.hidden) return;
    const geom = edgeGeometry(e);
    const { start, end, control, curved } = geom;
    const stroke = e.b.palette.border;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    if (curved) {
      ctx.quadraticCurveTo(control.x, control.y, end.x, end.y);
    } else {
      ctx.lineTo(end.x, end.y);
    }
    ctx.strokeStyle = stroke;
    ctx.globalAlpha = 0.7;
    ctx.lineWidth = 1.6 / Math.max(scale, 0.6);
    if (e.b.dashed) ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    const tangent = curved
      ? tangentOnQuadratic(0.985, start, control, end)
      : { x: end.x - start.x, y: end.y - start.y };
    const angle = Math.atan2(tangent.y, tangent.x);
    drawArrowhead(end.x, end.y, angle, 14 / Math.max(scale, 0.6), stroke);

    const label = e.predicateLabel;
    if (!label) return;
    const labelPoint = curved
      ? pointOnQuadratic(0.5, start, control, end)
      : { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    drawEdgeLabel(label, labelPoint.x, labelPoint.y);
  }

  function drawNodeBody(n) {
    const r = nodeRadius(n);
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = n.palette.color;
    ctx.fill();
    ctx.strokeStyle = n.palette.border;
    ctx.lineWidth = n.dashed ? 1.2 : 2;
    if (n.dashed) ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    if (selected?.id === n.id) {
      ctx.strokeStyle = colors.ink;
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
  }

  function drawNodeLabel(n) {
    const { fontSize, lineHeight, lines } = nodeLabelLayout(n);
    ctx.font = `600 ${fontSize}px var(--font-body), sans-serif`;
    ctx.fillStyle = n.dashed ? "rgba(255,255,255,0.82)" : "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const blockHeight = lines.length * lineHeight;
    let y = n.y - blockHeight / 2 + lineHeight / 2;
    for (const line of lines) {
      ctx.fillText(line, n.x, y);
      y += lineHeight;
    }
  }

  function draw() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(w / 2 + pan.x, h / 2 + pan.y);
    ctx.scale(scale, scale);
    for (const e of edges) drawEdge(e);
    for (const n of nodes) drawNodeBody(n);
    for (const n of nodes) drawNodeLabel(n);
    ctx.restore();
  }

  function hit(pos) {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      if (Math.hypot(n.x - pos.x, n.y - pos.y) <= nodeRadius(n) + 5) return n;
    }
    return null;
  }

  canvas.addEventListener("pointerdown", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
    const node = hit(pos);
    pointerStart = node ? { node, x: ev.clientX, y: ev.clientY, moved: false } : null;
    if (node && !node.pinned) {
      dragging = node;
      offset = { x: pos.x - node.x, y: pos.y - node.y };
    } else if (node) {
      selected = node;
      showDetail(node);
    } else {
      panning = { x: ev.clientX - pan.x, y: ev.clientY - pan.y };
    }
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", (ev) => {
    const rect = canvas.getBoundingClientRect();
    if (pointerStart && Math.hypot(ev.clientX - pointerStart.x, ev.clientY - pointerStart.y) > 4) {
      pointerStart.moved = true;
    }
    if (dragging) {
      const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      dragging.x = pos.x - offset.x;
      dragging.y = pos.y - offset.y;
      resolveOverlaps(nodes, {
        iterations: 16,
        pinnedIds: new Set([focusNode.id].filter(Boolean)),
        minGap: graphParams.nodeMinGap,
      });
      draw();
    } else if (panning) {
      pan.x = ev.clientX - panning.x;
      pan.y = ev.clientY - panning.y;
      draw();
    }
  });
  canvas.addEventListener("pointerup", () => {
    if (pointerStart && !pointerStart.moved && pointerStart.node && !pointerStart.node.pinned) {
      selected = pointerStart.node;
      showDetail(selected);
    }
    dragging = null;
    panning = null;
    pointerStart = null;
  });
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = canvas.getBoundingClientRect();
    zoomAt(ev.clientX - rect.left, ev.clientY - rect.top, ev.deltaY < 0 ? 1.1 : 0.9);
  }, { passive: false });

  root.querySelector("#graph-zoom-in")?.addEventListener("click", () => zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 1.15));
  root.querySelector("#graph-zoom-out")?.addEventListener("click", () => zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 0.87));
  root.querySelector("#graph-zoom-reset")?.addEventListener("click", () => {
    resetGraphView(canvas, focusNode, setPanScale);
    selected = focusNode;
    showDetail(focusNode);
    draw();
  });

  window.addEventListener("resize", resize);
  resize();
  selected = focusNode;
  showDetail(focusNode);
  if (graphParams.physics) {
    stopPhysics = runClassPhysics(nodes, edges, focusNode, {
      onTick: draw,
      onEnd: () => {
        resetGraphView(canvas, focusNode, setPanScale);
        draw();
      },
    });
  } else {
    // Physics off: the seeded layout is the layout.
    resetGraphView(canvas, focusNode, setPanScale);
    draw();
  }

  return () => {
    window.removeEventListener("resize", resize);
    stopPhysics?.();
  };
}

function renderClassFilter(options, hiddenClasses) {
  const items = options
    .map((option) => {
      const def = bfoColor(option.bucket);
      const checked = hiddenClasses.has(option.label) ? "" : " checked";
      return `<li><label>
        <input type="checkbox" data-class="${esc(option.label)}"${checked} />
        <i class="graph-swatch" style="background:${def.color};border:1px solid ${def.border}"></i>
        <span class="graph-class-name">${esc(option.label)}</span>
        <span class="graph-class-count">${option.count}</span>
      </label></li>`;
    })
    .join("");
  const shown = options.filter((option) => !hiddenClasses.has(option.label)).length;
  const summary = shown === options.length ? `All ${options.length}` : `${shown} of ${options.length}`;
  return `<div class="graph-classes"><span>Classes</span>
    <button type="button" class="graph-classes-toggle" id="graph-classes-toggle" aria-expanded="false" aria-haspopup="true">
      <span>${esc(summary)}</span>
      <svg class="graph-classes-chevron" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6" /></svg>
    </button>
    <div class="graph-classes-menu" id="graph-classes-menu" hidden>
      <ul>${items || `<li class="muted">No classes at this distance</li>`}</ul>
      <div class="graph-classes-actions">
        <button type="button" data-classes-action="all">Select all</button>
        <button type="button" data-classes-action="none">Clear all</button>
      </div>
    </div>
  </div>`;
}

function formatParamValue(key, value) {
  const def = GRAPH_PARAM_DEFS[key];
  const unit = def.unit || "";
  return def.step < 1 ? `${Number(value).toFixed(2)}${unit}` : `${value}${unit}`;
}

function renderParamsPanel(params, distance, open) {
  const rows = Object.entries(GRAPH_PARAM_DEFS)
    .map(([key, def]) => {
      if (def.type === "toggle") {
        return `<label class="graph-param graph-param-toggle">
          <span class="graph-param-head">${esc(def.label)}
            <input type="checkbox" data-param="${key}" ${params[key] ? "checked" : ""} />
          </span>
          <em>${esc(def.hint)}</em>
        </label>`;
      }
      return `<label class="graph-param">
        <span class="graph-param-head">${esc(def.label)} <strong data-param-value="${key}">${esc(formatParamValue(key, params[key]))}</strong></span>
        <input type="range" data-param="${key}" min="${def.min}" max="${def.max}" step="${def.step}" value="${params[key]}" />
        <em>${esc(def.hint)}</em>
      </label>`;
    })
    .join("");

  return `<div class="graph-params">
    <button type="button" class="graph-params-toggle" id="graph-params-toggle"
      aria-expanded="${open ? "true" : "false"}" aria-haspopup="true" title="Graph parameters">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
        <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
      </svg>
      <span>Parameters</span>
    </button>
    <div class="graph-params-menu" id="graph-params-menu" ${open ? "" : "hidden"}>
      <label class="graph-param">
        <span class="graph-param-head">Distance <strong data-param-value="distance">${distance}</strong></span>
        <input type="range" data-param="distance" min="1" max="3" step="1" value="${distance}" />
        <em>${esc(DISTANCE_HINT)}</em>
      </label>
      <hr />
      ${rows}
      <button type="button" id="graph-params-reset">Reset to defaults</button>
    </div>
  </div>`;
}

function renderLegend() {
  const items = BFO_SEVEN.map(
    (b) => `<span><i class="graph-swatch" style="background:${b.color};border:1px solid ${b.border}"></i> ${esc(b.label)}</span>`
  ).join("");
  return `<strong>BFO buckets</strong>${items}`;
}

function readStoredHiddenClasses() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(HIDDEN_CLASSES_KEY) || "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

// Landing on an empty canvas hides what the page is for, so the graph opens on
// a person with a full working history rather than on a prompt to search.
const DEFAULT_PERSON_LABEL = "Alice Dupont";
const DEFAULT_DISTANCE = 2;

function defaultPerson(people) {
  return (
    people.find((person) => person.label === DEFAULT_PERSON_LABEL) ||
    people.find((person) => person.kind === "employee") ||
    people[0] ||
    null
  );
}

function graphFiltersFromUrl(people, fallbackDistance) {
  const params = new URLSearchParams(window.location.search);
  const personParam = params.get("person");
  const selectedPerson = personParam
    ? people.find((person) => person.id === personParam || person.label === personParam)
    : defaultPerson(people);
  const distanceParam = Number(params.get("distance"));
  const distance = [1, 2, 3].includes(distanceParam) ? distanceParam : fallbackDistance;
  return {
    selectedId: selectedPerson?.id || null,
    distance,
  };
}

function entitySlugFromPathname() {
  const segments = window.location.pathname.split("/").filter(Boolean);
  if (segments.length >= 2) return segments[0];
  if (segments.length === 1 && !["workforce", "graph", "logs", "processes"].includes(segments[0])) {
    return segments[0];
  }
  return "demo";
}

function syncGraphFiltersToUrl(personId, distance) {
  const url = new URL(window.location.href);
  url.pathname = `/${entitySlugFromPathname()}/graph`;
  if (personId) url.searchParams.set("person", personId);
  else url.searchParams.delete("person");
  url.searchParams.set("distance", String(distance));
  window.history.replaceState(window.history.state, "", url);
}

export function mountGraphPage(el, data) {
  const adj = buildGraphIndex(data);
  const lookup = {
    peopleById: adj.peopleById,
    processesById: adj.processesById,
    entitiesById: adj.entitiesById,
    workingHubByPerson: adj.workingHubByPerson,
  };
  const people = [...(data.people || [])].sort((a, b) => a.label.localeCompare(b.label));
  const storedDistance = Math.min(
    3,
    Math.max(1, Number(sessionStorage.getItem(DISTANCE_KEY)) || DEFAULT_DISTANCE)
  );
  const initialFilters = graphFiltersFromUrl(people, storedDistance);
  let selectedId = initialFilters.selectedId;
  let distance = initialFilters.distance;
  // Deselected classes are stored, not selected ones, so classes that only
  // appear at a larger distance start out visible.
  let hiddenClasses = new Set(readStoredHiddenClasses());
  let classMenuOpen = false;
  // Survives the repaint each parameter change triggers, so the panel stays
  // open while several values are being tuned.
  let paramsOpen = false;
  let disposeCanvas = null;
  syncGraphFiltersToUrl(selectedId, distance);

  function persistParams() {
    sessionStorage.setItem(PARAMS_KEY, JSON.stringify(graphParams));
  }

  function persistHiddenClasses() {
    sessionStorage.setItem(HIDDEN_CLASSES_KEY, JSON.stringify([...hiddenClasses]));
  }

  function paint() {
    const person = people.find((p) => p.id === selectedId) || null;
    const reachable = person ? collectVisibleGraph(adj, person.id, distance) : null;
    const classOptions = reachable ? visibleClassOptions(reachable) : [];
    const visible = reachable ? applyClassFilter(reachable, hiddenClasses, person.id) : null;

    el.innerHTML = `
      ${
        person
          ? `<div class="graph-page"><div class="graph-body">
              <div class="graph-stage" id="graph-stage">
                <canvas id="graph-canvas"></canvas>
                <div class="graph-toolbar">
                  <label class="graph-search"><span>Person</span>
                    <input type="search" id="graph-person-search" placeholder="Search people…" value="${esc(person?.label || "")}" autocomplete="off" />
                    <ul class="graph-suggestions" id="graph-suggestions" hidden></ul>
                  </label>
                  ${renderClassFilter(classOptions, hiddenClasses)}
                </div>
                <div class="graph-legend">${renderLegend()}</div>
                ${renderParamsPanel(graphParams, distance, paramsOpen)}
                <div class="graph-zoom"><button type="button" id="graph-zoom-in" title="Zoom in">+</button><button type="button" id="graph-zoom-out" title="Zoom out">−</button><button type="button" id="graph-zoom-reset" title="Reset view">⟲</button></div>
                <p class="graph-hint">Focus at center · every other node is simulated · drag to pan · scroll to zoom</p>
              </div>
              <aside class="graph-detail" id="graph-detail"></aside>
            </div></div>`
          : `<div class="graph-page"><div class="graph-toolbar">
              <label class="graph-search"><span>Person</span>
                <input type="search" id="graph-person-search" placeholder="Search people…" value="" autocomplete="off" />
                <ul class="graph-suggestions" id="graph-suggestions" hidden></ul>
              </label>
            </div><div class="graph-empty panel"><h2>Select a person</h2><p>Try <strong>Alice Dupont</strong>, <strong>Emma Petit</strong>, or <strong>Grace Lambert</strong> to decompose their acts of working.</p></div></div>`
      }`;

    const input = el.querySelector("#graph-person-search");
    const suggestions = el.querySelector("#graph-suggestions");
    const openSuggestions = (query) => {
      const q = query.trim().toLowerCase();
      const hits = people.filter((p) => !q || p.label.toLowerCase().includes(q)).slice(0, 8);
      suggestions.innerHTML = hits.map((p) => `<li data-person="${esc(p.id)}"><strong>${esc(p.label)}</strong></li>`).join("") || `<li class="muted">No matches</li>`;
      suggestions.hidden = false;
    };
    input.addEventListener("focus", () => openSuggestions(input.value));
    input.addEventListener("input", () => openSuggestions(input.value));
    suggestions.addEventListener("click", (e) => {
      const li = e.target.closest("[data-person]");
      if (!li) return;
      selectedId = li.dataset.person;
      syncGraphFiltersToUrl(selectedId, distance);
      paint();
    });
    const paramsToggle = el.querySelector("#graph-params-toggle");
    const paramsMenu = el.querySelector("#graph-params-menu");
    paramsToggle?.addEventListener("click", () => {
      paramsOpen = !paramsOpen;
      paramsMenu.hidden = !paramsOpen;
      paramsToggle.setAttribute("aria-expanded", paramsOpen ? "true" : "false");
    });

    // `input` updates the readout on every frame of the drag; `change` — once
    // the thumb is released — is what repaints, so dragging a slider does not
    // rebuild the whole canvas dozens of times.
    for (const input of el.querySelectorAll("[data-param]")) {
      const key = input.dataset.param;
      input.addEventListener("input", (e) => {
        const readout = el.querySelector(`[data-param-value="${key}"]`);
        if (!readout) return;
        readout.textContent =
          key === "distance"
            ? String(Number(e.target.value) || 1)
            : formatParamValue(key, Number(e.target.value));
      });
      input.addEventListener("change", (e) => {
        if (key === "distance") {
          distance = Number(e.target.value) || 1;
          sessionStorage.setItem(DISTANCE_KEY, String(distance));
          syncGraphFiltersToUrl(selectedId, distance);
        } else if (GRAPH_PARAM_DEFS[key]?.type === "toggle") {
          graphParams[key] = e.target.checked;
          persistParams();
        } else {
          graphParams[key] = Number(e.target.value);
          persistParams();
        }
        paint();
      });
    }

    el.querySelector("#graph-params-reset")?.addEventListener("click", () => {
      Object.assign(graphParams, defaultGraphParams());
      persistParams();
      paint();
    });
    const classToggle = el.querySelector("#graph-classes-toggle");
    const classMenu = el.querySelector("#graph-classes-menu");
    if (classToggle && classMenu) {
      // The menu survives the repaint a checkbox triggers, so several classes
      // can be toggled without reopening it.
      const setMenuOpen = (open) => {
        classMenuOpen = open;
        classMenu.hidden = !open;
        classToggle.setAttribute("aria-expanded", String(open));
      };
      setMenuOpen(classMenuOpen);
      classToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        setMenuOpen(classMenu.hidden);
      });
      classMenu.addEventListener("click", (e) => e.stopPropagation());
      classMenu.addEventListener("change", (e) => {
        const box = e.target.closest("input[data-class]");
        if (!box) return;
        if (box.checked) hiddenClasses.delete(box.dataset.class);
        else hiddenClasses.add(box.dataset.class);
        persistHiddenClasses();
        paint();
      });
      classMenu.querySelectorAll("[data-classes-action]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.dataset.classesAction === "none") {
            for (const option of classOptions) hiddenClasses.add(option.label);
          } else {
            hiddenClasses = new Set();
          }
          persistHiddenClasses();
          paint();
        });
      });
    }

    if (disposeCanvas) disposeCanvas();
    if (person) {
      disposeCanvas = mountGraphCanvas(el, {
        focusPerson: person,
        visible,
        lookup,
        workingHubByPerson: adj.workingHubByPerson,
      });
    }
  }

  const closeClassMenu = () => {
    if (!classMenuOpen) return;
    classMenuOpen = false;
    const menu = el.querySelector("#graph-classes-menu");
    const toggle = el.querySelector("#graph-classes-toggle");
    if (menu) menu.hidden = true;
    toggle?.setAttribute("aria-expanded", "false");
  };
  document.addEventListener("click", closeClassMenu);

  paint();
  return () => {
    document.removeEventListener("click", closeClassMenu);
    if (disposeCanvas) disposeCanvas();
  };
}

/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  const data = await ctx.loadJson("graph/index.json");
  return mountGraphPage(el, data);
}
