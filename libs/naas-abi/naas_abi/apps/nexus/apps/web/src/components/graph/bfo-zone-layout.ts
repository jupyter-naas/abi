/**
 * BFO zones: the seven buckets placed where the BFO 7 Buckets diagram puts them.
 *
 * Occurrents sit in a band on top (Process on the left, Temporal Region on the
 * right); continuants in a band below (Material Entity, Site, Generically
 * Dependent Continuant, Quality, Realizable). Anything else lands in an
 * "Other" zone at the end of the continuants. A zone is as big as the cards it
 * holds. Inside a zone a subclass follows its parent class: to its right in
 * the occurrents (temporal region, then temporal instant), below it in the
 * continuants (material entity above person and organization).
 * When the BFO edge rules fix the sides connectors use (bfo-edge-rules.ts), the
 * margins and corridors are widened for the connectors the rules send through
 * them, a track apiece, so those can be drawn side by side.
 * Ported from the people app's network layout
 * (naas_abi_marketplace intelligence/modules/people/apps/people/web/lib/network-layout.js).
 */
import { sideLoads, type Side, type SidesFor } from './bfo-edge-rules';
import { TRACK, type Room } from './orthogonal-grid-route';

/** ``parent``: the card of the nearest superclass, when it is in the same zone. */
export type ZoneCard = { id: string; width: number; height: number; bucket: string; label: string; parent?: string };
export type ZoneLink = { source: string; target: string };
export type Zone = { key: string; x: number; y: number; width: number; height: number };
export type Band = { label: 'OCCURRENTS' | 'CONTINUANTS'; x: number; y: number; width: number; height: number };
/** ``room``: the margin left outside the zones, per side, for the connectors that run there. */
export type ZoneLayout = { positions: Map<string, { x: number; y: number }>; zones: Zone[]; bands: Band[]; room?: Room };

export const OCCURRENT_BUCKETS = ['Process', 'Temporal Region'];
export const CONTINUANT_BUCKETS = ['Material Entity', 'Site', 'GDC', 'Quality', 'Realizable'];
export const OTHER_BUCKET = 'Other';
/** The share of the occurrents band that Process takes when Temporal Region shares it. */
export const PROCESS_SHARE = 0.7;

export const ZONE_PAD = 22;
export const ZONE_HEADER = 22;
const CARD_GAP_X = 64;
const CARD_GAP_Y = 56;
const ZONE_GAP = 64;
const CORRIDOR = 72;
const MARGIN = 48;
// Wide enough for the longest zone title ("HOW WE KNOW · GDC", "WHEN · Temporal Region").
const MIN_ZONE_WIDTH = 190;
// Most free connectors one gap between two bottom zones is widened for.
const MAX_GAP_LOAD = 176;

/** ``cells``: fixed (column, row) of every card when the zone holds a class hierarchy. */
type Measured = { cols: number; cellW: number; cellH: number; width: number; height: number; cells?: Map<string, { col: number; row: number }> };

/** Where subclasses go: right of their parent (occurrents) or below it (continuants). */
type Direction = 'right' | 'down';

/**
 * Cells of a zone that holds subclasses of its own cards. ``right``: a class
 * in column ``depth``, its subclasses one column to the right, the first of
 * them on its row. ``down``: a class in row ``depth``, its subclasses one row
 * below, side by side, the first of them in its column. Cards outside any
 * hierarchy fill the rows below. Null when no card has a parent in the zone.
 */
function hierarchyCells(cards: ZoneCard[], direction: Direction) {
  const ids = new Set(cards.map(card => card.id));
  const children = new Map<string, ZoneCard[]>();
  for (const card of cards) {
    if (!card.parent || card.parent === card.id || !ids.has(card.parent)) continue;
    children.set(card.parent, [...(children.get(card.parent) || []), card]);
  }
  if (!children.size) return null;
  const hasParent = new Set([...children.values()].flat().map(card => card.id));
  const byLabel = (a: ZoneCard, b: ZoneCard) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id);
  const cells = new Map<string, { col: number; row: number }>();
  // ``leaves`` counts the lines the hierarchy uses across: rows when it grows
  // right, columns when it grows down. ``depth`` is the other axis.
  let leaves = 0;
  let depth = 1;
  const visit = (card: ZoneCard, level: number) => {
    if (cells.has(card.id)) return;
    cells.set(card.id, direction === 'right' ? { col: level, row: leaves } : { col: leaves, row: level });
    depth = Math.max(depth, level + 1);
    const below = (children.get(card.id) || []).filter(child => !cells.has(child.id)).sort(byLabel);
    if (!below.length) { leaves += 1; return; }
    below.forEach(child => visit(child, level + 1));
  };
  const roots = cards.filter(card => !hasParent.has(card.id) && children.has(card.id)).sort(byLabel);
  roots.forEach(root => visit(root, 0));
  // A parent cycle has no root: start it anywhere.
  cards.filter(card => children.has(card.id) || hasParent.has(card.id)).sort(byLabel).forEach(card => visit(card, 0));
  const singles = cards.filter(card => !cells.has(card.id));
  const treeCols = direction === 'right' ? depth : leaves;
  const treeRows = direction === 'right' ? leaves : depth;
  // Growing down, a narrow tree must not stack its loose cards in one tall column.
  const perRow = direction === 'right' ? treeCols : Math.max(treeCols, Math.ceil(Math.sqrt(singles.length)));
  singles.forEach((card, k) => cells.set(card.id, { col: k % perRow, row: treeRows + Math.floor(k / perRow) }));
  return { cells, cols: Math.max(treeCols, singles.length ? perRow : 0), rows: treeRows + Math.ceil(singles.length / perRow) };
}

function measureHierarchy(cards: ZoneCard[], cellH: number, direction: Direction): Measured | null {
  const tree = hierarchyCells(cards, direction);
  if (!tree) return null;
  const cellW = cellWidth(cards);
  const width = Math.max(MIN_ZONE_WIDTH, tree.cols * cellW + (tree.cols - 1) * CARD_GAP_X + 2 * ZONE_PAD);
  return { cols: tree.cols, cellW, cellH, width, height: zoneHeight(tree.rows, cellH), cells: tree.cells };
}

/** Cards in reading order: each one followed by those linked to it, the root first. */
function inReadingOrder(cards: ZoneCard[], links: ZoneLink[]): ZoneCard[] {
  const byId = new Map(cards.map(card => [card.id, card]));
  const neighbours = new Map(cards.map(card => [card.id, [] as string[]]));
  for (const link of links) {
    if (link.source === link.target || !byId.has(link.source) || !byId.has(link.target)) continue;
    neighbours.get(link.source)!.push(link.target);
    neighbours.get(link.target)!.push(link.source);
  }
  const byLabel = (a: string, b: string) => byId.get(a)!.label.localeCompare(byId.get(b)!.label) || a.localeCompare(b);
  const order: ZoneCard[] = [];
  const seen = new Set<string>();
  const visit = (id: string) => {
    if (seen.has(id)) return;
    seen.add(id);
    order.push(byId.get(id)!);
    for (const next of [...neighbours.get(id)!].sort(byLabel)) visit(next);
  };
  for (const id of [...byId.keys()].sort(byLabel)) visit(id);
  return order;
}

const cellWidth = (cards: ZoneCard[]) => Math.max(...cards.map(card => card.width));

function zoneHeight(rows: number, cellH: number) {
  return ZONE_HEADER + rows * cellH + (rows - 1) * CARD_GAP_Y + 2 * ZONE_PAD;
}

/** A zone with at most ``rows`` rows: its columns follow from how many cards it holds. */
function measureZone(cards: ZoneCard[], rows: number, cellH: number): Measured {
  // Continuants: the bottom band, where subclasses sit below their parent.
  const tree = measureHierarchy(cards, cellH, 'down');
  if (tree) return tree;
  const cols = Math.max(1, Math.ceil(cards.length / Math.min(rows, cards.length)));
  const used = Math.ceil(cards.length / cols);
  const cellW = cellWidth(cards);
  const width = Math.max(MIN_ZONE_WIDTH, cols * cellW + (cols - 1) * CARD_GAP_X + 2 * ZONE_PAD);
  return { cols, cellW, cellH, width, height: zoneHeight(used, cellH) };
}

/** A zone of a given width: as many columns as fit, and the rows that leaves. */
function fitZone(cards: ZoneCard[], width: number, cellH: number): Measured {
  // Occurrents: the top band, where subclasses sit right of their parent.
  const tree = measureHierarchy(cards, cellH, 'right');
  if (tree) return { ...tree, width: Math.max(width, tree.width) };
  const cellW = cellWidth(cards);
  const fits = Math.max(1, Math.floor((width - 2 * ZONE_PAD + CARD_GAP_X) / (cellW + CARD_GAP_X)));
  const cols = Math.min(fits, cards.length);
  return { cols, cellW, cellH, width, height: zoneHeight(Math.ceil(cards.length / cols), cellH) };
}

/**
 * Place ``cards`` in BFO zones, choosing the number of rows that gives the whole
 * the shape of the view (``aspect`` is its width to height). Positions are card
 * centres; zones and bands are rectangles, all in canvas units.
 */
export function bfoZoneLayout(cards: ZoneCard[], links: ZoneLink[], { aspect = 1.7, sidesFor }: { aspect?: number; sidesFor?: SidesFor | null } = {}): ZoneLayout {
  if (!cards.length) return { positions: new Map(), zones: [], bands: [] };
  const known = new Set([...OCCURRENT_BUCKETS, ...CONTINUANT_BUCKETS]);
  const groups = new Map<string, ZoneCard[]>();
  for (const card of cards) {
    const key = known.has(card.bucket) ? card.bucket : OTHER_BUCKET;
    groups.set(key, [...(groups.get(key) || []), card]);
  }
  for (const [key, list] of groups) groups.set(key, inReadingOrder(list, links));

  const top = OCCURRENT_BUCKETS.filter(key => groups.has(key));
  const bottom = [...CONTINUANT_BUCKETS, OTHER_BUCKET].filter(key => groups.has(key));
  const zoneOf = new Map<string, string>();
  for (const [key, list] of groups) for (const card of list) zoneOf.set(card.id, key);
  const linked = links.filter(link => link.source !== link.target && zoneOf.has(link.source) && zoneOf.has(link.target));

  // A side a card's neighbour stands in front of cannot be left by in a straight
  // line. So the cards that most connectors leave by the bottom go last in their
  // zone (its bottom row); in the top band, those going out west first and east last.
  if (sidesFor) {
    const demand = sideLoads(linked, sidesFor);
    const need = (id: string, side: Side) => demand.get(id)?.[side] || 0;
    for (const key of bottom) groups.set(key, [...groups.get(key)!].sort((a, b) => need(a.id, 'S') - need(b.id, 'S')));
    for (const key of top) groups.set(key, [...groups.get(key)!].sort((a, b) => need(a.id, 'E') - need(a.id, 'W') - (need(b.id, 'E') - need(b.id, 'W'))));
  }
  const spacing = connectorRoom(linked, zoneOf, top, bottom, sidesFor);
  const cellHeight = (keys: string[]) => Math.max(0, ...keys.flatMap(key => groups.get(key)!.map(card => card.height)));
  const topCellH = cellHeight(top);
  const bottomCellH = cellHeight(bottom);

  const bottomBand = (rows: number) => {
    const zones = bottom.map(key => measureZone(groups.get(key)!, rows, bottomCellH));
    const width = zones.reduce((sum, zone, i) => sum + zone.width + spacing.gapBefore(i), 0);
    return { zones, width, height: Math.max(0, ...zones.map(zone => zone.height)) };
  };
  // The top band spans the view: Process takes 70% of it when Temporal Region shares it.
  const shares = top.length > 1 ? [PROCESS_SHARE, 1 - PROCESS_SHARE] : [1];
  const topGap = top.length > 1 ? spacing.topGap : 0;
  const oneColumn = (key: string) => measureHierarchy(groups.get(key)!, topCellH, 'right')?.width ?? Math.max(MIN_ZONE_WIDTH, cellWidth(groups.get(key)!) + 2 * ZONE_PAD);
  const innerMin = top.length ? Math.max(...top.map((key, i) => (oneColumn(key) + topGap / 2) / shares[i])) : 0;
  const topBand = (inner: number) => {
    const zones = top.map((key, i) => fitZone(groups.get(key)!, shares[i] * inner - topGap / 2, topCellH));
    return { zones, height: Math.max(0, ...zones.map(zone => zone.height)) };
  };

  const corridor = top.length && bottom.length ? spacing.corridor : 0;
  let best: { score: number; lower: ReturnType<typeof bottomBand>; upper: ReturnType<typeof topBand>; inner: number; width: number; height: number } | null = null;
  for (let rows = 1; rows <= 8; rows += 1) {
    const lower = bottomBand(rows);
    const inner = Math.max(lower.width, innerMin);
    const upper = topBand(inner);
    const width = inner + spacing.left + MARGIN;
    const height = spacing.above + upper.height + corridor + lower.height + (bottom.length ? spacing.below : MARGIN);
    const score = Math.abs(Math.log(width / height / aspect));
    if (!best || score < best.score - 1e-9) best = { score, lower, upper, inner, width, height };
  }
  const layout = best!;

  const positions = new Map<string, { x: number; y: number }>();
  const zones: Zone[] = [];
  const place = (key: string, zone: Measured, x: number, y: number, bandHeight: number) => {
    const list = groups.get(key)!;
    zones.push({ key, x, y, width: zone.width, height: bandHeight });
    const used = zone.cells ? Math.max(...[...zone.cells.values()].map(cell => cell.row)) + 1 : Math.ceil(list.length / zone.cols);
    const pitch = zone.cellH + CARD_GAP_Y;
    const room = bandHeight - ZONE_HEADER - 2 * ZONE_PAD;
    // Centred by whole rows, so rows line up with the zones beside it.
    const offset = Math.max(0, Math.floor(Math.floor((room + CARD_GAP_Y) / pitch - used) / 2));
    if (zone.cells) {
      const blockWidth = zone.cols * zone.cellW + (zone.cols - 1) * CARD_GAP_X;
      for (const card of list) {
        const cell = zone.cells.get(card.id)!;
        positions.set(card.id, {
          x: x + (zone.width - blockWidth) / 2 + cell.col * (zone.cellW + CARD_GAP_X) + zone.cellW / 2,
          y: y + ZONE_HEADER + ZONE_PAD + (offset + cell.row) * pitch + zone.cellH / 2,
        });
      }
      return;
    }
    list.forEach((card, k) => {
      const line = Math.floor(k / zone.cols);
      const inLine = Math.min(zone.cols, list.length - line * zone.cols);
      const rowWidth = inLine * zone.cellW + (inLine - 1) * CARD_GAP_X;
      positions.set(card.id, {
        x: x + (zone.width - rowWidth) / 2 + (k % zone.cols) * (zone.cellW + CARD_GAP_X) + zone.cellW / 2,
        y: y + ZONE_HEADER + ZONE_PAD + (offset + line) * pitch + zone.cellH / 2,
      });
    });
  };
  const upperY = spacing.above;
  const lowerY = (top.length ? spacing.above : MARGIN) + layout.upper.height + corridor;
  if (top.length) {
    place(top[0], layout.upper.zones[0], spacing.left, upperY, layout.upper.height);
    if (top.length > 1) {
      const right = layout.upper.zones[1];
      place(top[1], right, spacing.left + layout.inner - right.width, upperY, layout.upper.height);
    }
  }
  let x = spacing.left + (layout.inner - layout.lower.width) / 2;
  bottom.forEach((key, i) => {
    x += spacing.gapBefore(i);
    place(key, layout.lower.zones[i], x, lowerY, layout.lower.height);
    x += layout.lower.zones[i].width;
  });

  const bands: Band[] = [];
  const split = upperY + layout.upper.height + corridor / 2;
  if (top.length) bands.push({ label: 'OCCURRENTS', x: 0, y: 0, width: layout.width, height: bottom.length ? split : layout.height });
  if (bottom.length) {
    const y = top.length ? split : 0;
    bands.push({ label: 'CONTINUANTS', x: 0, y, width: layout.width, height: layout.height - y });
  }
  const room = { top: spacing.above, bottom: bottom.length ? spacing.below : MARGIN, left: spacing.left, right: MARGIN };
  return { positions, zones, bands, room };
}

/**
 * Room for the connectors, counted from the sides the rules give them: what the
 * rules send under the bottom band, over the top band or down the left margin
 * needs a margin of its own, and the corridors carry only what passes through.
 * Without rules, the fixed gaps.
 */
function connectorRoom(links: ZoneLink[], zoneOf: Map<string, string>, top: string[], bottom: string[], sidesFor?: SidesFor | null) {
  if (!sidesFor) {
    return { above: MARGIN, below: MARGIN, left: MARGIN, corridor: CORRIDOR, topGap: ZONE_GAP, gapBefore: (i: number) => (i ? ZONE_GAP : 0) };
  }
  const only = (sides?: Side[]) => (sides?.length === 1 ? sides[0] : null);
  const inTop = (zone: string) => top.includes(zone);
  const budget = { top: 0, bottom: 0, left: 0, mid: 0, eastOfTop: 0, west: new Map<string, number>() };
  const free: ZoneLink[] = [];
  for (const link of links) {
    const rule = sidesFor(link);
    const from = zoneOf.get(link.source)!, to = zoneOf.get(link.target)!;
    const s = only(rule?.source), t = only(rule?.target);
    const crossing = inTop(from) !== inTop(to);
    if (!s || !t) {
      free.push(link);
      if (crossing) budget.mid += 1;
      continue;
    }
    if (s === 'N' && t === 'N') budget.top += 1;
    if (s === 'S' && t === 'S') budget.bottom += 1;
    for (const [zone, side, other] of [[from, s, to], [to, t, from]] as const) {
      if (inTop(zone) && side === 'W') budget.left += 1;
      if (inTop(zone) && side === 'E') budget.eastOfTop += 1;
      if (!inTop(zone) && side === 'W' && inTop(other)) budget.west.set(zone, (budget.west.get(zone) || 0) + 1);
    }
    if (crossing && !(s === 'W' && t === 'W')) budget.mid += 1;
  }
  const gapBefore = (i: number) => {
    if (i === 0) return 0;
    const left = new Set(bottom.slice(0, i));
    const load = free.reduce((sum, link) => {
      const a = zoneOf.get(link.source)!, b = zoneOf.get(link.target)!;
      if (bottom.includes(a) && bottom.includes(b)) return sum + (left.has(a) !== left.has(b) ? 1 : 0);
      // A free connector from the other band lands in one zone of this row.
      const landing = bottom.includes(a) ? a : bottom.includes(b) ? b : null;
      return landing === bottom[i - 1] || landing === bottom[i] ? sum + 0.5 : sum;
    }, 0);
    // The connectors the rules send in by the west side of this zone come down this gap.
    return ZONE_GAP + TRACK * (budget.west.get(bottom[i]) || 0) + Math.min(MAX_GAP_LOAD, Math.round(3 * load));
  };
  // Free connectors that skip over a zone in the bottom row run under it.
  const skipping = free.filter(link => {
    const x = bottom.indexOf(zoneOf.get(link.source)!), y = bottom.indexOf(zoneOf.get(link.target)!);
    return x >= 0 && y >= 0 && Math.abs(x - y) > 1;
  }).length;
  const freeBetweenTop = free.filter(link => inTop(zoneOf.get(link.source)!) && inTop(zoneOf.get(link.target)!) && zoneOf.get(link.source) !== zoneOf.get(link.target)).length;
  return {
    // Over the top band for the U shapes, under the bottom band for theirs, down the left for the C shapes.
    above: MARGIN + TRACK * budget.top,
    below: MARGIN + TRACK * (budget.bottom + Math.ceil(skipping / 2)),
    left: MARGIN + TRACK * budget.left,
    corridor: Math.max(CORRIDOR, 60 + TRACK * budget.mid),
    // Connectors leaving Process by its east side go down between it and Temporal Region.
    topGap: ZONE_GAP + TRACK * (budget.eastOfTop + freeBetweenTop),
    gapBefore,
  };
}

export type ZoneClass = { id: string; bucket: string; iri?: string; equivalents?: string[]; ancestors?: string[] };

/**
 * Each card's nearest superclass among the cards of its zone, by IRI.
 * ``ancestors`` lists superclasses nearest first; a card answers to its IRI
 * and its equivalents, so time:Instant (subclass of bfo:BFO_0000203) goes
 * under abi:TemporalInstant (equivalent to it). Equivalent classes never
 * become each other's parent.
 */
export function zoneParents(classes: ZoneClass[]): Map<string, string> {
  const names = new Map(classes.map(item => [item.id, new Set([item.iri, ...(item.equivalents || [])].filter((iri): iri is string => Boolean(iri)))]));
  const above = new Map(classes.map(item => [item.id, new Set(item.ancestors || [])]));
  const byIri = new Map<string, ZoneClass[]>();
  for (const item of classes) for (const iri of names.get(item.id)!) byIri.set(iri, [...(byIri.get(iri) || []), item]);
  const isAbove = (upper: ZoneClass, lower: ZoneClass) => [...names.get(upper.id)!].some(iri => above.get(lower.id)!.has(iri));
  const same = (a: ZoneClass, b: ZoneClass) => [...names.get(a.id)!].some(iri => names.get(b.id)!.has(iri));
  const parents = new Map<string, string>();
  for (const item of classes) {
    for (const iri of item.ancestors || []) {
      const parent = (byIri.get(iri) || []).find(other => other.id !== item.id && other.bucket === item.bucket && !isAbove(item, other) && !same(item, other));
      if (parent) { parents.set(item.id, parent.id); break; }
    }
  }
  return parents;
}

/** The rectangle the bands cover, to frame the whole drawing. */
export function zoneBounds(layout: ZoneLayout) {
  const boxes = layout.bands.length ? layout.bands : layout.zones;
  if (!boxes.length) return null;
  const left = Math.min(...boxes.map(box => box.x));
  const top = Math.min(...boxes.map(box => box.y));
  const right = Math.max(...boxes.map(box => box.x + box.width));
  const bottom = Math.max(...boxes.map(box => box.y + box.height));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function withAlpha(hex: string, alpha: number) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const int = parseInt(m[1], 16);
  return `rgba(${(int >> 16) & 255}, ${(int >> 8) & 255}, ${int & 255}, ${alpha})`;
}

/**
 * Paint the realm bands and the bucket zones, in canvas coordinates (vis-network
 * ``beforeDrawing``), under the nodes and edges. ``buckets`` maps a zone key to
 * its colour and its 7 buckets question (Who, What, …).
 */
export function drawBfoZones(
  ctx: CanvasRenderingContext2D,
  layout: ZoneLayout,
  buckets: Record<string, { label: string; color: string } | undefined>,
  { dark = false, bands = true, zones = true } = {},
) {
  ctx.save();
  ctx.textBaseline = 'top';
  if (bands) {
    const ink = dark ? '#a1a1aa' : '#71717a';
    layout.bands.forEach((band, i) => {
      ctx.fillStyle = withAlpha(dark ? '#ffffff' : '#18181b', i % 2 ? 0.035 : 0.02);
      ctx.fillRect(band.x, band.y, band.width, band.height);
      ctx.fillStyle = ink;
      ctx.font = '600 13px ui-sans-serif, system-ui, sans-serif';
      ctx.fillText(band.label, band.x + 14, band.y + 12);
    });
    if (layout.bands.length > 1) {
      const split = layout.bands[1];
      ctx.strokeStyle = withAlpha(ink, 0.5);
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(split.x, split.y);
      ctx.lineTo(split.x + split.width, split.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
  if (zones) {
    for (const zone of layout.zones) {
      const bucket = buckets[zone.key];
      const color = bucket?.color || '#9ca3af';
      ctx.fillStyle = withAlpha(color, 0.07);
      ctx.fillRect(zone.x, zone.y, zone.width, zone.height);
      ctx.strokeStyle = withAlpha(color, 0.55);
      ctx.lineWidth = 1;
      ctx.strokeRect(zone.x + 0.5, zone.y + 0.5, zone.width - 1, zone.height - 1);
      ctx.fillStyle = color;
      ctx.font = '600 11px ui-sans-serif, system-ui, sans-serif';
      const title = bucket ? `${bucket.label.toUpperCase()} · ${zone.key}` : zone.key.toUpperCase();
      ctx.fillText(title, zone.x + 12, zone.y + 10);
    }
  }
  ctx.restore();
}
