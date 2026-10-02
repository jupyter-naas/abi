/**
 * Card sizes and node positions for the ontology network, as laid out by the
 * Nexus ontology network (naas_abi nexus web: components/graph/vis-network.tsx
 * and compact-network-layout.ts).
 */

import { sideLoads } from "./bfo-edge-rules.js";
import { PORT_INSET, TRACK } from "./orthogonal-route.js";

const MAX_CHARS_PER_LINE = 16;
const MAX_LABEL_LINES = 4;
const BOX_WIDTH = 128;
const MIN_HEIGHT = 64;
const LINE_HEIGHT = 14;
const CHAR_WIDTH = 6.2;

export const LABEL_FONT_SIZE = 11;
export const LABEL_LINE_HEIGHT = LINE_HEIGHT;

// Spacing for the tree layouts.
const LR_LEVEL_GAP = 260;
const LR_NODE_SLOT = 110;
const TD_LEVEL_GAP = 180;
const TD_NODE_SLOT = 168;
// More leaf children than this under one parent are wrapped into lines.
const WRAP_LEAVES = 6;

function hardBreak(token, max) {
  if (token.length <= max) return [token];
  const chunks = [];
  let rest = token;
  while (rest.length > max) {
    chunks.push(rest.slice(0, max));
    rest = rest.slice(max);
  }
  if (rest) chunks.push(rest);
  return chunks;
}

/** Wrap a class label onto at most four short lines. */
export function wrapLabel(label, max = MAX_CHARS_PER_LINE, maxLines = MAX_LABEL_LINES) {
  const text = String(label ?? "").trim().replace(/\s+/g, " ");
  if (!text) return [];
  if (text.length <= max) return [text];
  const lines = [];
  let current = "";
  // A PascalCase name with no spaces breaks between its words, not mid-word.
  const words = text.split(" ").flatMap((word) => (word.length > max ? word.split(/(?<=[a-z0-9])(?=[A-Z])/) : [word]));
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= max) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = "";
    if (lines.length >= maxLines) break;
    if (word.length <= max) {
      current = word;
      continue;
    }
    const chunks = hardBreak(word, max);
    for (let i = 0; i < chunks.length && lines.length < maxLines; i += 1) {
      if (i === chunks.length - 1) current = chunks[i];
      else lines.push(chunks[i]);
    }
  }
  if (lines.length < maxLines && current) lines.push(current);
  return lines.slice(0, maxLines);
}

/** The length of a side that holds ``n`` connectors at least a track apart. */
const sideLength = (n) => (n > 0 ? (n + 1) * TRACK + 2 * PORT_INSET : 0);

/**
 * The card's size follows its label, and the connectors it ends: ``load`` is
 * {N, S, E, W, free}, the connectors on each side and those the router may put
 * anywhere. The ports on one side stay a track apart, so a class that many
 * connectors end on by its bottom is as wide as that needs, whatever it is called.
 */
export function cardSize(lines, load = {}) {
  const count = Math.max(1, lines.length);
  const longest = Math.max(...lines.map((line) => line.length), 8);
  const width = Math.min(220, Math.max(BOX_WIDTH, Math.ceil(longest * CHAR_WIDTH) + 24));
  const height = Math.max(MIN_HEIGHT, 10 + count * LINE_HEIGHT + 10 + 10);
  const { N = 0, S = 0, E = 0, W = 0, free = 0 } = load;
  // Free connectors may end on any side: count half of them on each.
  const anywhere = Math.ceil(free / 2);
  return {
    width: Math.max(width, sideLength(Math.max(N, S) + anywhere)),
    height: Math.max(height, sideLength(Math.max(E, W) + anywhere)),
  };
}

// ── BFO zones ──
//
// The seven buckets sit where the BFO 7 Buckets diagram puts them: the
// occurrents (Process, Temporal Region) in a band on top, Process on the left and
// Temporal Region on the right; the continuants in a band below, Material Entity
// then Site on the left, Generically Dependent Continuant in the middle, Quality
// then Realizable on the right. A zone is as big as the cards it holds.

const OCCURRENTS = ["Process", "Temporal Region"];
const CONTINUANTS = ["Material Entity", "Site", "GDC", "Quality", "Realizable"];
const OTHER = "Other";

const ZONE_PAD = 22;
const ZONE_HEADER = 22;
const CARD_GAP_X = 88;
const CARD_GAP_Y = 76;
const MARGIN = 56;
// What one forced connector end walled in by a card costs a layout, against the
// shape of the view: a wall is a detour of at least three bends.
const WALL_WEIGHT = 1;

/** Cards in the order they read: a parent, then what is under it. */
function inReadingOrder(cards, edges) {
  const ids = new Set(cards.map((card) => card.id));
  const byId = new Map(cards.map((card) => [card.id, card]));
  const childrenOf = new Map();
  const hasParent = new Set();
  for (const edge of edges) {
    if (edge.relation !== "hierarchy" || !ids.has(edge.source) || !ids.has(edge.target) || edge.source === edge.target) continue;
    if (hasParent.has(edge.source)) continue;
    if (!childrenOf.has(edge.target)) childrenOf.set(edge.target, []);
    childrenOf.get(edge.target).push(edge.source);
    hasParent.add(edge.source);
  }
  const byLabel = (a, b) => byId.get(a).label.localeCompare(byId.get(b).label);
  const order = [];
  const seen = new Set();
  const visit = (id) => {
    if (seen.has(id)) return;
    seen.add(id);
    order.push(id);
    for (const child of (childrenOf.get(id) || []).sort(byLabel)) visit(child);
  };
  for (const id of cards.map((card) => card.id).filter((id) => !hasParent.has(id)).sort(byLabel)) visit(id);
  for (const id of cards.map((card) => card.id).sort(byLabel)) visit(id); // a cycle, if any
  return order.map((id) => byId.get(id));
}

/** The cards' shared cell: as wide as the widest in the zone, as tall as ``cellH``. */
const cellWidth = (cards) => Math.max(...cards.map((card) => card.width));

/** A zone laid out in ``rows`` rows at most: its columns follow from how many cards it holds. */
function measureZone(cards, rows, cellH) {
  const cols = Math.max(1, Math.ceil(cards.length / Math.min(rows, cards.length)));
  const used = Math.ceil(cards.length / cols);
  const cellW = cellWidth(cards);
  return {
    cols,
    cellW,
    cellH,
    width: cols * cellW + (cols - 1) * CARD_GAP_X + 2 * ZONE_PAD,
    height: ZONE_HEADER + used * cellH + (used - 1) * CARD_GAP_Y + 2 * ZONE_PAD,
  };
}

/** A zone of a given width: as many columns as fit in it, and the rows that leaves. */
function fitZone(cards, width, cellH) {
  const cellW = cellWidth(cards);
  const fits = Math.max(1, Math.floor((width - 2 * ZONE_PAD + CARD_GAP_X) / (cellW + CARD_GAP_X)));
  const cols = Math.min(fits, cards.length);
  const used = Math.ceil(cards.length / cols);
  return { cols, cellW, cellH, width, height: ZONE_HEADER + used * cellH + (used - 1) * CARD_GAP_Y + 2 * ZONE_PAD };
}

/** The share of the occurrents band that Process takes, when Temporal Region shares it. */
export const PROCESS_SHARE = 0.7;

/**
 * Place the cards in BFO zones. ``cards`` are {id, width, height, bucket, label,
 * bucketLabel}; ``edges`` are {source, target, relation}. ``aspect`` is the
 * width to height of the view the layout is for. Returns the positions (card
 * centres), the zones and the two realm bands, all in canvas units.
 *
 * - Occurrents on top: Process on the left, taking 70% of the band, Temporal
 *   Region on the right.
 * - Continuants below: Material Entity, Site, Generically Dependent Continuant,
 *   Quality, Realizable. Each zone is as wide as the cards it holds, so a zone
 *   with fourteen cards is wider than one with a single card.
 * - Cards are centred in their zone. Rows are the same height across a band, so
 *   they line up from zone to zone, and a zone with fewer rows is centred by
 *   whole rows.
 * - The corridors between zones are widened for the connectors that have to run
 *   through them, so those can be drawn side by side and not on top of one another.
 */
export function bucketLayout(cards, edges, { aspect = 1.7, sidesFor } = {}) {
  if (!cards.length) return { positions: new Map(), zones: [], bands: [], room: {} };
  const known = new Set([...OCCURRENTS, ...CONTINUANTS]);
  const bucketOf = (card) => (known.has(card.bucket) ? card.bucket : OTHER);
  const groups = new Map();
  for (const card of cards) {
    const key = bucketOf(card);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(card);
  }
  const zoneOf = new Map();
  for (const [key, list] of groups) for (const card of list) zoneOf.set(card.id, key);
  for (const [key, list] of groups) groups.set(key, inReadingOrder(list, edges));

  const top = OCCURRENTS.filter((key) => groups.has(key));
  const bottom = [...CONTINUANTS, OTHER].filter((key) => groups.has(key));

  // A side a card's neighbour stands in front of cannot be left by in a straight
  // line: the connector must detour, and pays in bends. So the cards that most
  // connectors leave by a side go where that side is open: the ones with the
  // most going out of the bottom, last in a zone (its bottom row); in the top
  // band, the ones going out to the west first and to the east last.
  const demand = sideLoads(edges.filter((edge) => zoneOf.has(edge.source) && zoneOf.has(edge.target)), sidesFor);
  const need = (id, side) => demand.get(id)?.[side] || 0;
  if (sidesFor) {
    for (const key of bottom) groups.set(key, [...groups.get(key)].sort((a, b) => need(a.id, "S") - need(b.id, "S")));
    for (const key of top) groups.set(key, [...groups.get(key)].sort((a, b) => need(a.id, "E") - need(a.id, "W") - (need(b.id, "E") - need(b.id, "W"))));
  }
  const cellHeight = (keys) => Math.max(0, ...keys.flatMap((key) => groups.get(key).map((card) => card.height)));
  const topCellH = cellHeight(top);
  const bottomCellH = cellHeight(bottom);

  // Room for the connectors, counted from the sides they are given: what the
  // rules send under the bottom band, over the top band or down the left margin
  // needs a margin of its own, and the corridors carry only what passes through.
  // A connector with free sides is counted as before, by where its ends are.
  const linked = edges.filter((edge) => zoneOf.has(edge.source) && zoneOf.has(edge.target));
  const only = (sides) => (sides?.length === 1 ? sides[0] : null);
  const inTop = (zone) => top.includes(zone);
  const budget = { top: 0, bottom: 0, left: 0, mid: 0, eastOfTop: 0, west: new Map() };
  const free = [];
  for (const edge of linked) {
    const rule = sidesFor?.(edge) ?? null;
    const from = zoneOf.get(edge.source);
    const to = zoneOf.get(edge.target);
    const s = only(rule?.source);
    const t = only(rule?.target);
    const crossing = inTop(from) !== inTop(to);
    if (!rule || !s || !t) {
      free.push(edge);
      if (crossing) budget.mid += 1;
      continue;
    }
    if (s === "N" && t === "N") budget.top += 1;
    if (s === "S" && t === "S") budget.bottom += 1;
    for (const [zone, side, other] of [[from, s, to], [to, t, from]]) {
      if (inTop(zone) && side === "W") budget.left += 1;
      if (inTop(zone) && side === "E") budget.eastOfTop += 1;
      if (!inTop(zone) && side === "W" && inTop(other)) budget.west.set(zone, (budget.west.get(zone) || 0) + 1);
    }
    if (crossing && !(s === "W" && t === "W")) budget.mid += 1;
  }
  const gapBetween = (row, i) => {
    if (i === 0) return 0;
    const left = new Set(row.slice(0, i));
    const load = free.reduce((sum, edge) => {
      const a = zoneOf.get(edge.source);
      const b = zoneOf.get(edge.target);
      const inRow = row.includes(a) && row.includes(b);
      if (inRow) return sum + (left.has(a) !== left.has(b) ? 1 : 0);
      // A free connector from the other band lands in one zone of this row.
      const landing = row.includes(a) ? a : row.includes(b) ? b : null;
      return landing === row[i - 1] || landing === row[i] ? sum + 0.5 : sum;
    }, 0);
    // The connectors the rules send in by the west side of this zone come down this gap.
    return 64 + TRACK * (budget.west.get(row[i]) || 0) + Math.min(176, Math.round(3 * load));
  };
  const corridor = budget.mid ? 60 + TRACK * budget.mid : 0;
  // Free connectors that skip over a zone in the bottom row run under it.
  const skipping = free.filter((edge) => {
    const x = bottom.indexOf(zoneOf.get(edge.source));
    const y = bottom.indexOf(zoneOf.get(edge.target));
    return x >= 0 && y >= 0 && Math.abs(x - y) > 1;
  }).length;
  // Margins: under the bottom band for the U shapes, over the top band for the
  // others, down the left for the C shapes, at a track apiece.
  const below = MARGIN + TRACK * (budget.bottom + Math.ceil(skipping / 2));
  const above = MARGIN + TRACK * budget.top;
  const leftMargin = MARGIN + TRACK * budget.left;

  function bottomBand(rows) {
    const zones = bottom.map((key) => measureZone(groups.get(key), rows, bottomCellH));
    const width = zones.reduce((sum, zone, i) => sum + zone.width + gapBetween(bottom, i), 0);
    return { zones, width, height: Math.max(0, ...zones.map((zone) => zone.height)) };
  }

  // The top band spans the view: Process takes 70% of it when Temporal Region shares it.
  const freeBetweenTop = free.filter((e) => inTop(zoneOf.get(e.source)) && inTop(zoneOf.get(e.target)) && zoneOf.get(e.source) !== zoneOf.get(e.target)).length;
  // Connectors leaving Process by its east side go down between it and Temporal Region.
  const topGap = top.length > 1 ? 64 + TRACK * (budget.eastOfTop + freeBetweenTop) : 0;
  const shares = top.length > 1 ? [PROCESS_SHARE, 1 - PROCESS_SHARE] : [1];
  const oneColumn = (key) => cellWidth(groups.get(key)) + 2 * ZONE_PAD;
  const innerMin = top.length ? Math.max(...top.map((key, i) => (oneColumn(key) + topGap / 2) / shares[i])) : 0;
  function topBand(inner) {
    const zones = top.map((key, i) => fitZone(groups.get(key), shares[i] * inner - (top.length > 1 ? topGap / 2 : 0), topCellH));
    return { zones, width: inner, height: Math.max(0, ...zones.map((zone) => zone.height)) };
  }

  // The number of rows that gives the whole the shape of the view.
  let best = null;
  for (let rows = 1; rows <= 8; rows += 1) {
    const lower = bottomBand(rows);
    const inner = Math.max(lower.width, innerMin);
    const upper = topBand(inner);
    const width = inner + leftMargin + MARGIN;
    const height = above + upper.height + (top.length && bottom.length ? corridor : 0) + lower.height + (bottom.length ? below : MARGIN);
    // Bottom cards that connectors leave by the south side but that have a card below them.
    let walled = 0;
    let southward = 0;
    bottom.forEach((key, i) => {
      const cards = groups.get(key);
      for (let k = 0; k < cards.length; k += 1) {
        const count = need(cards[k].id, "S");
        southward += count;
        if (k < cards.length - lower.zones[i].cols) walled += count;
      }
    });
    const score = Math.abs(Math.log(width / height / aspect)) + (southward ? (WALL_WEIGHT * walled) / southward : 0);
    if (!best || score < best.score - 1e-9) best = { score, rows, lower, upper, inner, width, height };
  }

  const positions = new Map();
  const zones = [];
  function place(key, zone, x, originY, bandHeight) {
    const cards = groups.get(key);
    zones.push({ key, label: cards[0].bucketLabel || key, type: key, x, y: originY, width: zone.width, height: bandHeight });
    const used = Math.ceil(cards.length / zone.cols);
    const pitch = zone.cellH + CARD_GAP_Y;
    const room = bandHeight - ZONE_HEADER - 2 * ZONE_PAD;
    // Centred by whole rows, so the rows line up with the zones beside it.
    const offset = Math.floor(Math.floor((room + CARD_GAP_Y) / pitch - used) / 2);
    cards.forEach((card, k) => {
      const line = Math.floor(k / zone.cols);
      const inLine = Math.min(zone.cols, cards.length - line * zone.cols);
      const rowWidth = inLine * zone.cellW + (inLine - 1) * CARD_GAP_X;
      positions.set(card.id, {
        x: x + (zone.width - rowWidth) / 2 + (k % zone.cols) * (zone.cellW + CARD_GAP_X) + zone.cellW / 2,
        y: originY + ZONE_HEADER + ZONE_PAD + (Math.max(0, offset) + line) * pitch + zone.cellH / 2,
      });
    });
  }
  const upperY = above;
  const lowerY = above + best.upper.height + (top.length && bottom.length ? corridor : 0);
  if (top.length) {
    place(top[0], best.upper.zones[0], leftMargin, upperY, best.upper.height);
    if (top.length > 1) place(top[1], best.upper.zones[1], leftMargin + best.inner - best.upper.zones[1].width, upperY, best.upper.height);
  }
  let x = leftMargin + (best.inner - best.lower.width) / 2;
  bottom.forEach((key, i) => {
    x += gapBetween(bottom, i);
    place(key, best.lower.zones[i], x, lowerY, best.lower.height);
    x += best.lower.zones[i].width;
  });

  const bands = [];
  const split = upperY + best.upper.height + corridor / 2;
  if (top.length) bands.push({ label: "OCCURRENTS", x: 0, y: 0, width: best.width, height: bottom.length ? split : best.height });
  if (bottom.length) {
    const y = top.length ? split : 0;
    bands.push({ label: "CONTINUANTS", x: 0, y, width: best.width, height: best.height - y });
  }
  // What is left outside the outermost cards, for the connectors that go round.
  const room = { top: above + ZONE_PAD, left: leftMargin + ZONE_PAD, right: MARGIN + ZONE_PAD, bottom: (bottom.length ? below : MARGIN) + ZONE_PAD };
  return { positions, zones, bands, room };
}

/** Nodes with nothing to hang from: a sunflower spiral, so none overlap. */
function spreadPositions(ids, spacing = 300) {
  const result = new Map();
  const golden = Math.PI * (3 - Math.sqrt(5));
  ids.forEach((id, i) => {
    const r = spacing * Math.sqrt(i);
    result.set(id, { x: r * Math.cos(i * golden), y: r * Math.sin(i * golden) });
  });
  return result;
}

/**
 * Subtree layout (Reingold-Tilford style) over the class hierarchy. A leaf takes
 * one slot on the cross axis and a parent is centred over its children, so every
 * subtree occupies its own range and nothing overlaps. Siblings are grouped by
 * BFO bucket. ``edges`` are {source: child, target: parent}.
 */
export function hierarchicalPositions(nodes, edges, direction, extraSpacing = 0) {
  if (!nodes.length) return new Map();
  const byId = new Map(nodes.map((node) => [node.id, node]));
  if (!edges.length) return spreadPositions(nodes.map((node) => node.id), 180 + extraSpacing);

  const childrenOf = new Map();
  const parentOf = new Map();
  for (const edge of edges) {
    const child = edge.source;
    const parent = edge.target;
    if (!byId.has(child) || !byId.has(parent) || child === parent) continue;
    if (parentOf.has(child)) continue; // one parent per node keeps this a tree
    // Never let a cycle become an endless descent.
    let ancestor = parent;
    let cyclic = false;
    while (ancestor) {
      if (ancestor === child) {
        cyclic = true;
        break;
      }
      ancestor = parentOf.get(ancestor);
    }
    if (cyclic) continue;
    if (!childrenOf.has(parent)) childrenOf.set(parent, []);
    childrenOf.get(parent).push(child);
    parentOf.set(child, parent);
  }

  const bucketOf = (id) => byId.get(id)?.bucket || "Unknown";
  const labelOf = (id) => byId.get(id)?.label ?? id;
  const bySiblingOrder = (a, b) =>
    bucketOf(a).localeCompare(bucketOf(b)) || labelOf(a).localeCompare(labelOf(b));
  for (const children of childrenOf.values()) children.sort(bySiblingOrder);

  const roots = nodes.map((node) => node.id).filter((id) => !parentOf.has(id)).sort(bySiblingOrder);
  // A class with no parent and no children is not a tree. Laid out as a root
  // each, they would make one endless row, so they are packed into a grid.
  const treeRoots = roots.filter((id) => (childrenOf.get(id) || []).length);
  const loose = roots.filter((id) => !(childrenOf.get(id) || []).length);

  const slot = (direction === "LR" ? LR_NODE_SLOT : TD_NODE_SLOT) + extraSpacing;
  const level = (direction === "LR" ? LR_LEVEL_GAP : TD_LEVEL_GAP) + extraSpacing;
  const bucketGap = Math.round(slot * 0.55);
  const positions = new Map();
  let cursor = 0;
  const setPosition = (id, depth, cross) =>
    positions.set(id, direction === "LR" ? { x: depth * level, y: cross } : { x: cross, y: depth * level });

  let deepest = 0;
  // Lines of a wrapped group of leaves advance by this much along the main axis.
  const lineStep = direction === "LR" ? level : 130;
  const place = (id, depth) => {
    deepest = Math.max(deepest, depth);
    const children = childrenOf.get(id) || [];
    if (!children.length) {
      const cross = cursor + slot / 2;
      cursor += slot;
      setPosition(id, depth, cross);
      return cross;
    }
    // Many leaves under one parent would make one endless row: wrap them into
    // a block of short lines, the parent centred over it.
    if (children.length > WRAP_LEAVES && children.every((child) => !(childrenOf.get(child) || []).length)) {
      const perLine = Math.ceil(Math.sqrt(children.length * 1.5));
      const start = cursor;
      children.forEach((child, k) => {
        const at = depth + 1 + Math.floor(k / perLine) * (lineStep / level);
        deepest = Math.max(deepest, at);
        setPosition(child, at, start + slot / 2 + (k % perLine) * slot);
      });
      cursor += perLine * slot;
      const centre = start + (Math.min(perLine, children.length) * slot) / 2;
      setPosition(id, depth, centre);
      return centre;
    }
    let previous = "";
    const centres = [];
    for (const child of children) {
      const bucket = bucketOf(child);
      if (previous && previous !== bucket) cursor += bucketGap;
      previous = bucket;
      centres.push(place(child, depth + 1));
    }
    const middle = (centres[0] + centres[centres.length - 1]) / 2;
    setPosition(id, depth, middle);
    return middle;
  };

  treeRoots.forEach((root, i) => {
    if (i > 0) cursor += slot; // a gap between independent subtrees
    place(root, 0);
  });

  if (loose.length) {
    const perLine = Math.max(1, Math.ceil(Math.sqrt(loose.length * 1.6)));
    const alongStep = direction === "LR" ? level : 130;
    const start = treeRoots.length ? deepest + 1 : 0;
    const crossValues = [...positions.values()].map((p) => (direction === "LR" ? p.y : p.x));
    const centre = crossValues.length ? (Math.min(...crossValues) + Math.max(...crossValues)) / 2 : 0;
    loose.forEach((id, k) => {
      const line = Math.floor(k / perLine);
      const cross = centre + ((k % perLine) - (perLine - 1) / 2) * slot;
      const along = start * level + line * alongStep;
      positions.set(id, direction === "LR" ? { x: along, y: cross } : { x: cross, y: along });
    });
  }

  const cross = [...positions.values()].map((p) => (direction === "LR" ? p.y : p.x));
  const middle = (Math.min(...cross) + Math.max(...cross)) / 2;
  for (const [id, p] of positions) {
    positions.set(id, direction === "LR" ? { x: p.x, y: p.y - middle } : { x: p.x - middle, y: p.y });
  }
  return positions;
}
