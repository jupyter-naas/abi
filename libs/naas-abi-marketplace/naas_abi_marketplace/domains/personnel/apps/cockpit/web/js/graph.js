/**
 * Graph page — birth process hub + employment, with labeled relations.
 */

import { BFO_SEVEN, bfoColor } from "./bfo-buckets.js";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const DISTANCE_KEY = "cockpit-graph-distance";
const SOURCES_KEY = "cockpit-graph-show-sources";
const MIN_SCALE = 0.25;
const MAX_SCALE = 2.5;
const LINK_TARGET_LENGTH = 220;
const LAYOUT_SETTLE_MS = 5000;
const GRAPH_NODE_RADIUS = 36;
const NODE_LABEL_FONT_SIZE = 11;
const NODE_LABEL_LINE_HEIGHT = 13;

function buildGraphIndex(data) {
  const peopleById = Object.fromEntries((data.people || []).map((p) => [p.id, p]));
  const processesById = Object.fromEntries((data.processes || []).map((p) => [p.id, p]));
  const sourcesById = Object.fromEntries((data.sources || []).map((s) => [s.id, s]));
  const entitiesById = Object.fromEntries((data.entities || []).map((e) => [e.id, e]));
  const birthHubByPerson = new Map();
  const workingHubByPerson = new Map();
  const personToProcesses = new Map();
  const relations = data.relations || [];

  for (const rel of relations) {
    if (rel.predicateLabel === "has birth" && peopleById[rel.from] && entitiesById[rel.to]?.isBirthHub) {
      birthHubByPerson.set(rel.from, rel.to);
    }
    if (rel.predicateLabel === "has working" && peopleById[rel.from] && entitiesById[rel.to]?.isWorkingHub) {
      workingHubByPerson.set(rel.from, rel.to);
    }
    if (rel.predicateLabel === "Employee" && peopleById[rel.from] && processesById[rel.to]) {
      if (!personToProcesses.has(rel.from)) personToProcesses.set(rel.from, []);
      personToProcesses.get(rel.from).push(rel.to);
    }
  }

  return {
    peopleById,
    processesById,
    sourcesById,
    entitiesById,
    relations,
    birthHubByPerson,
    workingHubByPerson,
    personToProcesses,
  };
}

function collectVisibleGraph(adj, rootId, distance, showSources) {
  const people = new Set([rootId]);
  const births = new Set();
  const workings = new Set();

  const focusBirthId = adj.birthHubByPerson.get(rootId);
  if (focusBirthId) births.add(focusBirthId);

  const focusWorkingId = adj.workingHubByPerson.get(rootId);
  if (focusWorkingId) workings.add(focusWorkingId);

  for (const pid of adj.personToProcesses.get(rootId) || []) {
    workings.add(pid);
  }

  if (distance >= 2) {
    for (const rel of adj.relations) {
      if (rel.predicateLabel === "declared" && births.has(rel.to)) {
        people.add(rel.from);
      }
    }
  }

  if (distance >= 3) {
    for (const rel of adj.relations) {
      const label = rel.predicateLabel || "";
      if ((label === "has mother" || label === "has father") && rel.from === rootId) {
        people.add(rel.to);
      }
    }
    for (const pid of people) {
      if (pid === rootId) continue;
      const hub = adj.birthHubByPerson.get(pid);
      if (hub) births.add(hub);
    }
  }

  const allowedBirthIds = new Set([focusBirthId].filter(Boolean));
  if (distance >= 3) {
    for (const pid of people) {
      if (pid === rootId) continue;
      const hub = adj.birthHubByPerson.get(pid);
      if (hub) allowedBirthIds.add(hub);
    }
  }

  const allowedWorkingIds = new Set([focusWorkingId].filter(Boolean));

  const active = new Set([...people, ...births, ...workings]);
  const visibleRelations = [];

  let changed = true;
  while (changed) {
    changed = false;
    for (const rel of adj.relations) {
      if (visibleRelations.includes(rel)) continue;
      const label = rel.predicateLabel || "";
      const touches = active.has(rel.from) || active.has(rel.to);
      if (!touches) continue;

      if (distance < 2 && label === "declared") continue;
      if (distance < 3 && (label === "has mother" || label === "has father")) continue;

      const birthFrom = adj.entitiesById[rel.from]?.isBirthHub ? rel.from : null;
      const birthTo = adj.entitiesById[rel.to]?.isBirthHub ? rel.to : null;
      const birthId = birthFrom || birthTo;
      if (birthId && !allowedBirthIds.has(birthId)) continue;

      const workingFrom = adj.entitiesById[rel.from]?.isWorkingHub ? rel.from : null;
      const workingTo = adj.entitiesById[rel.to]?.isWorkingHub ? rel.to : null;
      const workingId = workingFrom || workingTo;
      if (workingId && !allowedWorkingIds.has(workingId)) continue;
      if (
        distance < 3 &&
        (label === "has birth" || label === "is birth of") &&
        birthId &&
        birthId !== focusBirthId
      ) {
        continue;
      }

      visibleRelations.push(rel);
      const before = active.size;
      active.add(rel.from);
      active.add(rel.to);
      if (active.size > before) changed = true;
    }
  }

  if (showSources) {
    for (const ledger of adj.ledgerProcesses || []) {
      active.add(ledger.id);
      active.add(ledger.sourceId);
    }
  }

  if (showSources && adj.allRelations) {
    for (const rel of adj.allRelations) {
      if (rel.canvas === false && (active.has(rel.from) || active.has(rel.to))) {
        if (!visibleRelations.includes(rel)) visibleRelations.push(rel);
        active.add(rel.from);
        active.add(rel.to);
      }
    }
  }

  return {
    people: [...people].map((id) => adj.peopleById[id]).filter(Boolean),
    processes: [...workings].map((id) => adj.processesById[id]).filter(Boolean),
    entities: [...active].map((id) => adj.entitiesById[id]).filter(Boolean),
    relations: visibleRelations,
  };
}

function renderPropertiesTable(properties) {
  const rows = (properties || [])
    .map(
      (p) => `<tr><td class="graph-prop-uri">${esc(p.uri || "—")}</td><td>${esc(p.label || "—")}</td><td>${esc(p.value)}</td></tr>`
    )
    .join("");
  if (!rows) return `<p class="empty">No data properties on this node.</p>`;
  return `<table class="graph-props"><thead><tr><th>Property</th><th>Label</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
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
  if (lookup.processesById[id]) {
    const process = lookup.processesById[id];
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
      label: entity.isBirthHub ? "Birth" : entity.isWorkingHub ? "Working" : entity.label,
      palette: nodePalette(entity),
      isBirthHub: entity.isBirthHub,
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

function resolveOverlaps(nodes, { iterations = 120, pinnedIds = new Set() } = {}) {
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
        const needX = ea.rx + eb.rx + 22;
        const needY = ea.ry + eb.ry + 14;
        const overlapX = needX - Math.abs(dx);
        const overlapY = needY - Math.abs(dy);
        if (overlapX <= 0 || overlapY <= 0) continue;
        const push = Math.min(overlapX, overlapY) * 0.55 + 1.5;
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

function seedSemanticLayout(focusNode, birthNode, workingNode, nodes, edges, focusPersonId) {
  focusNode.x = 0;
  focusNode.y = 0;

  const placed = new Set([focusNode.id]);
  const place = (node, x, y) => {
    if (!node || placed.has(node.id)) return;
    node.x = x;
    node.y = y;
    placed.add(node.id);
  };

  if (birthNode) {
    birthNode.x = 190;
    birthNode.y = 0;
    placed.add(birthNode.id);

    const birthEntityId = birthNode.entity?.id;
    const satellites = [];
    for (const edge of edges) {
      if (edge.hidden) continue;
      const label = edge.predicateLabel || "";
      if (label === "has mother" || label === "has father") continue;
      const touchesBirth =
        edge.a.id === birthNode.id ||
        edge.b.id === birthNode.id ||
        edge.a.entity?.id === birthEntityId ||
        edge.b.entity?.id === birthEntityId;
      if (!touchesBirth) continue;
      const other = edge.a.id === birthNode.id ? edge.b : edge.a;
      if (other.id === focusNode.id || other.id === birthNode.id) continue;
      if (other.kind === "person" && other.person?.id === focusPersonId) continue;
      if (!satellites.includes(other)) satellites.push(other);
    }

    const bucketRank = (n) => {
      const bucket = n.entity?.bfoBucket || n.person?.bfoBucket || n.process?.bfoBucket || "";
      const order = ["Site", "Temporal Region", "Quality", "GDC", "Material Entity", "Process"];
      const idx = order.indexOf(bucket);
      if (n.kind === "person") return 50;
      if (n.label === "Birth Record" || n.entity?.classLabel === "Birth Record") return 35;
      return idx >= 0 ? idx : 40;
    };
    satellites.sort((a, b) => bucketRank(a) - bucketRank(b));

    const start = -Math.PI * 0.62;
    const end = Math.PI * 0.62;
    satellites.forEach((node, i) => {
      const t = satellites.length === 1 ? 0.5 : i / (satellites.length - 1);
      const angle = start + (end - start) * t;
      place(node, birthNode.x + Math.cos(angle) * 155, birthNode.y + Math.sin(angle) * 125);
    });
  }

  if (workingNode) {
    workingNode.x = -190;
    workingNode.y = 0;
    placed.add(workingNode.id);

    const workingEntityId = workingNode.entity?.id;
    const satellites = [];
    for (const edge of edges) {
      if (edge.hidden) continue;
      const touchesWorking =
        edge.a.id === workingNode.id ||
        edge.b.id === workingNode.id ||
        edge.a.entity?.id === workingEntityId ||
        edge.b.entity?.id === workingEntityId;
      if (!touchesWorking) continue;
      const other = edge.a.id === workingNode.id ? edge.b : edge.a;
      if (other.id === focusNode.id || other.id === workingNode.id) continue;
      if (other.kind === "person" && other.person?.id === focusPersonId) continue;
      if (!satellites.includes(other)) satellites.push(other);
    }

    const bucketRank = (n) => {
      const bucket = n.entity?.bfoBucket || n.person?.bfoBucket || n.process?.bfoBucket || "";
      const order = ["Site", "Temporal Region", "Quality", "GDC", "Realizable", "Material Entity", "Process"];
      const idx = order.indexOf(bucket);
      if (n.kind === "person") return 50;
      return idx >= 0 ? idx : 40;
    };
    satellites.sort((a, b) => bucketRank(a) - bucketRank(b));

    const start = Math.PI * 0.38;
    const end = Math.PI * 1.62;
    satellites.forEach((node, i) => {
      const t = satellites.length === 1 ? 0.5 : i / (satellites.length - 1);
      const angle = start + (end - start) * t;
      place(node, workingNode.x + Math.cos(angle) * 155, workingNode.y + Math.sin(angle) * 125);
    });
  }

  for (const edge of edges) {
    if (edge.hidden) continue;
    const label = edge.predicateLabel || "";
    if (label === "has mother" && (edge.a.id === focusNode.id || edge.a.isBirthHub)) {
      place(edge.b, -185, -115);
    }
    if (label === "has father" && (edge.a.id === focusNode.id || edge.a.isBirthHub)) {
      place(edge.b, -185, 115);
    }
  }

  const processes = nodes.filter((n) => n.kind === "process");
  processes.forEach((node, i) => {
    place(node, -30 + i * 55, 175);
  });

  const workingHubs = nodes.filter((n) => n.isWorkingHub && n.id !== workingNode?.id);
  workingHubs.forEach((hub, i) => {
    place(hub, -320 - i * 40, 160 + i * 30);
  });

  const otherPeople = nodes.filter(
    (n) =>
      n.kind === "person" &&
      n.id !== focusNode.id &&
      !placed.has(n.id)
  );
  otherPeople.forEach((node, i) => {
    const angle = Math.PI * 0.85 + (i * Math.PI * 0.12);
    place(node, Math.cos(angle) * 250, Math.sin(angle) * 210);
  });

  const otherBirths = nodes.filter((n) => n.isBirthHub && n.id !== birthNode?.id);
  otherBirths.forEach((hub, i) => {
    const baseX = -320 - i * 40;
    const baseY = i % 2 === 0 ? -200 : 200;
    place(hub, baseX, baseY);
    for (const edge of edges) {
      if (edge.hidden) continue;
      if (edge.a.id !== hub.id && edge.b.id !== hub.id) continue;
      const other = edge.a.id === hub.id ? edge.b : edge.a;
      if (other.isBirthHub || other.id === focusNode.id) continue;
      const angle = (Math.PI * 2 * placed.size) / 17;
      place(other, hub.x + Math.cos(angle) * 120, hub.y + Math.sin(angle) * 95);
    }
  });

  let ring = 0;
  for (const node of nodes) {
    if (placed.has(node.id)) continue;
    const angle = ring * 0.95;
    place(node, Math.cos(angle) * (240 + (ring % 3) * 28), Math.sin(angle) * (210 + (ring % 2) * 24));
    ring += 1;
  }

  resolveOverlaps(nodes, { pinnedIds: new Set([focusNode.id].filter(Boolean)) });
}

function linkTargetLength(_edge) {
  return LINK_TARGET_LENGTH;
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

function simulationStep(nodes, edges, alpha) {
  const pinned = (n) => n.pinned;

  for (const n of nodes) {
    n.vx = (n.vx || 0) * 0.56;
    n.vy = (n.vy || 0) * 0.56;
  }

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let dist = Math.hypot(dx, dy) || 0.01;
      const ea = graphNodeExtent(a);
      const eb = graphNodeExtent(b);
      const minDist = ea.rx + eb.rx + 24;
      const minDistY = ea.ry + eb.ry + 16;
      let force = (alpha * 620) / (dist * dist);
      if (dist < minDist) force += ((minDist - dist) / dist) * 0.48 * alpha;
      if (Math.abs(dy) < minDistY && Math.abs(dx) < minDist) {
        force += ((minDistY - Math.abs(dy)) / (Math.abs(dy) || 0.01)) * 0.22 * alpha;
      }
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      if (!pinned(a)) {
        a.vx -= dx;
        a.vy -= dy;
      }
      if (!pinned(b)) {
        b.vx += dx;
        b.vy += dy;
      }
    }
  }

  for (const edge of edges) {
    if (edge.hidden) continue;
    const a = edge.a;
    const b = edge.b;
    let dx = b.x - a.x;
    let dy = b.y - a.y;
    let dist = Math.hypot(dx, dy) || 0.01;
    const target = linkTargetLength(edge);
    const force = ((dist - target) / dist) * 0.12 * alpha;
    dx *= force;
    dy *= force;
    if (!pinned(a)) {
      a.vx += dx;
      a.vy += dy;
    }
    if (!pinned(b)) {
      b.vx -= dx;
      b.vy -= dy;
    }
  }

  for (const n of nodes) {
    if (pinned(n)) {
      n.x = 0;
      n.y = 0;
      n.vx = 0;
      n.vy = 0;
      continue;
    }
    n.x += n.vx;
    n.y += n.vy;
  }
}

function settleGraphLayoutSync(nodes, edges, focusNode, { steps = 90 } = {}) {
  let alpha = 1;
  const alphaDecay = 0.028;
  for (let i = 0; i < steps; i++) {
    simulationStep(nodes, edges, alpha);
    alpha *= 1 - alphaDecay;
  }
  resolveOverlaps(nodes, { iterations: 40, pinnedIds: new Set([focusNode.id].filter(Boolean)) });
}

function runForceLayout(nodes, edges, focusNode, { onTick, onEnd, maxMs = LAYOUT_SETTLE_MS } = {}) {
  const started = performance.now();
  let rafId = 0;

  const stop = (complete = false) => {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    if (complete) {
      settleGraphLayoutSync(nodes, edges, focusNode, { steps: 24 });
      onEnd?.();
    }
  };

  const tick = () => {
    const elapsed = performance.now() - started;
    if (elapsed >= maxMs) {
      stop(true);
      return;
    }
    const alpha = Math.max(0.035, 1 - (elapsed / maxMs) * 0.92);
    simulationStep(nodes, edges, alpha);
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
    const node = { ...base, x: 0, y: 0, vx: 0, vy: 0, ...extra };
    nodeMap.set(node.id, node);
    return node;
  };

  const birthId = lookup.birthHubByPerson?.get?.(focusPerson.id) || visible.entities.find((e) => e.isBirthHub)?.id;
  const birthNode = birthId ? addNode(birthId, { isBirthHub: true }) : null;
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

  return { nodes, edges, focusNode, birthNode, workingNode };
}

export function layoutGraphNodes(focusPerson, visible, lookup, { physics = false } = {}) {
  const graph = buildGraph(focusPerson, visible, lookup);
  seedSemanticLayout(
    graph.focusNode,
    graph.birthNode,
    graph.workingNode,
    graph.nodes,
    graph.edges,
    focusPerson.id
  );
  if (physics) {
    settleGraphLayoutSync(graph.nodes, graph.edges, graph.focusNode);
  }
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
      if (Math.abs(a.x - b.x) < ea.rx + eb.rx && Math.abs(a.y - b.y) < ea.ry + eb.ry) n += 1;
    }
  }
  return n;
}

export {
  GRAPH_NODE_RADIUS,
  graphNodeExtent,
  countOverlaps,
  buildGraphIndex,
  collectVisibleGraph,
  resolveNode,
  resolveOverlaps,
  seedSemanticLayout,
  settleGraphLayoutSync,
  computeParallelEdgeRoundness,
  annotateEdgeCurves,
  nodeLabelLayout,
  wrapNodeLabelLines,
};

function fitGraphToView(nodes, canvas, focusNode, setPanScale) {
  if (!nodes.length) return;
  const fx = focusNode?.x ?? 0;
  const fy = focusNode?.y ?? 0;
  let maxR = 90;
  for (const n of nodes) {
    const ext = graphNodeExtent(n);
    maxR = Math.max(maxR, Math.hypot(n.x - fx, n.y - fy) + Math.max(ext.rx, ext.ry));
  }
  const pad = 52;
  const scale = Math.min(
    MAX_SCALE,
    Math.max(MIN_SCALE, Math.min(canvas.clientWidth, canvas.clientHeight) / (2 * (maxR + pad)))
  );
  setPanScale({
    scale,
    panX: -fx * scale,
    panY: -fy * scale,
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
    birthHubByPerson: options.birthHubByPerson,
    workingHubByPerson: options.workingHubByPerson,
  });
  let selected = focusNode;
  let pan = { x: 0, y: 0 };
  let scale = 1;
  let dragging = null;
  let panning = null;
  let offset = { x: 0, y: 0 };
  let pointerStart = null;
  let layoutDone = false;
  let stopLayout = null;

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
    if (layoutDone) fitGraphToView(nodes, canvas, focusNode, setPanScale);
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
      resolveOverlaps(nodes, { iterations: 16, pinnedIds: new Set([focusNode.id].filter(Boolean)) });
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
    fitGraphToView(nodes, canvas, focusNode, setPanScale);
    selected = focusNode;
    showDetail(focusNode);
    draw();
  });

  window.addEventListener("resize", resize);
  resize();
  selected = focusNode;
  showDetail(focusNode);
  stopLayout = runForceLayout(nodes, edges, focusNode, {
    onTick: draw,
    onEnd: () => {
      layoutDone = true;
      fitGraphToView(nodes, canvas, focusNode, setPanScale);
      draw();
    },
  });

  return () => {
    window.removeEventListener("resize", resize);
    stopLayout?.();
  };
}

function renderLegend() {
  const items = BFO_SEVEN.map(
    (b) => `<span><i class="graph-swatch" style="background:${b.color};border:1px solid ${b.border}"></i> ${esc(b.label)}</span>`
  ).join("");
  return `<strong>BFO buckets</strong>${items}`;
}

export function mountGraphPage(el, data) {
  const adj = buildGraphIndex(data);
  adj.ledgerProcesses = data.ledgerProcesses || [];
  adj.allRelations = data.allRelations || data.relations || [];
  const lookup = {
    peopleById: adj.peopleById,
    processesById: adj.processesById,
    entitiesById: adj.entitiesById,
    birthHubByPerson: adj.birthHubByPerson,
    workingHubByPerson: adj.workingHubByPerson,
  };
  const people = [...(data.people || [])].sort((a, b) => a.label.localeCompare(b.label));
  let selectedId = null;
  let distance = Math.min(3, Math.max(1, Number(sessionStorage.getItem(DISTANCE_KEY)) || 1));
  let showSources = sessionStorage.getItem(SOURCES_KEY) === "1";
  let disposeCanvas = null;

  function paint() {
    const person = people.find((p) => p.id === selectedId) || null;
    const visible = person ? collectVisibleGraph(adj, person.id, distance, showSources) : null;

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
                  <label class="graph-distance"><span>Distance</span>
                    <select id="graph-distance">
                      <option value="1" ${distance === 1 ? "selected" : ""}>1 — birth & working hubs</option>
                      <option value="2" ${distance === 2 ? "selected" : ""}>2 — + declarant</option>
                      <option value="3" ${distance === 3 ? "selected" : ""}>3 — + linked people</option>
                    </select>
                  </label>
                  <label class="graph-toggle">
                    <input type="checkbox" id="graph-show-sources" ${showSources ? "checked" : ""} />
                    <span>Show ledger sources</span>
                  </label>
                </div>
                <div class="graph-legend">${renderLegend()}</div>
                <div class="graph-zoom"><button type="button" id="graph-zoom-in" title="Zoom in">+</button><button type="button" id="graph-zoom-out" title="Zoom out">−</button><button type="button" id="graph-zoom-reset" title="Fit view">⟲</button></div>
                <p class="graph-hint">Focus at center · layout settles in ~5s · arrows show edge direction · drag nodes · scroll to zoom</p>
              </div>
              <aside class="graph-detail" id="graph-detail"></aside>
            </div></div>`
          : `<div class="graph-page"><div class="graph-toolbar">
              <label class="graph-search"><span>Person</span>
                <input type="search" id="graph-person-search" placeholder="Search people…" value="" autocomplete="off" />
                <ul class="graph-suggestions" id="graph-suggestions" hidden></ul>
              </label>
            </div><div class="graph-empty panel"><h2>Select a person</h2><p>Try <strong>Emma Petit</strong>, <strong>Alice Dupont</strong>, or <strong>Grace Lambert</strong> for birth and working decomposition.</p></div></div>`
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
      paint();
    });
    el.querySelector("#graph-distance")?.addEventListener("change", (e) => {
      distance = Number(e.target.value) || 1;
      sessionStorage.setItem(DISTANCE_KEY, String(distance));
      paint();
    });
    el.querySelector("#graph-show-sources")?.addEventListener("change", (e) => {
      showSources = e.target.checked;
      sessionStorage.setItem(SOURCES_KEY, showSources ? "1" : "0");
      paint();
    });

    if (disposeCanvas) disposeCanvas();
    if (person) {
      disposeCanvas = mountGraphCanvas(el, {
        focusPerson: person,
        visible,
        lookup,
        birthHubByPerson: adj.birthHubByPerson,
        workingHubByPerson: adj.workingHubByPerson,
      });
    }
  }

  paint();
  return () => {
    if (disposeCanvas) disposeCanvas();
  };
}
