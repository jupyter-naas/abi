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
/** ``labelWidth``: the width of the connector's label, when it has one. */
export type ZoneLink = { source: string; target: string; labelWidth?: number };
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
// A label on a connector between two cards side by side sits in the gap between
// them: the gap is as wide as the widest label, with this much to spare, up to a limit.
const LABEL_ROOM = 28;
const MAX_GAP_X = 200;
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
 * Cells of a zone that holds subclasses of its own cards. ``down``: a class
 * above its subclasses; ``right``: a class left of them. Each class and its
 * subclasses make a rectangle of cells, and the rectangles of a class's
 * subclasses are packed below (right of) it in shelves: side by side across,
 * the first of them under (beside) the class, until a shelf would be more than
 * ``limit`` cells across; then a new shelf starts below (right of) it. With no
 * limit this is the usual tree, as wide as it has leaves; with one it is about
 * as wide as the limit. Cards outside any hierarchy fill the rows below. Null
 * when no card has a parent in the zone.
 */
function hierarchyCells(cards: ZoneCard[], direction: Direction, limit = Infinity) {
  const ids = new Set(cards.map(card => card.id));
  const children = new Map<string, ZoneCard[]>();
  for (const card of cards) {
    if (!card.parent || card.parent === card.id || !ids.has(card.parent)) continue;
    children.set(card.parent, [...(children.get(card.parent) || []), card]);
  }
  if (!children.size) return null;
  const hasParent = new Set([...children.values()].flat().map(card => card.id));
  const byLabel = (a: ZoneCard, b: ZoneCard) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id);
  // A block: its size ``across`` (columns when growing down) and ``along``, and
  // each card's offset in it.
  type Block = { across: number; along: number; at: Map<string, { across: number; along: number }> };
  const seen = new Set<string>();
  const shelve = (blocks: Block[], start: number, into: Block['at']) => {
    let across = 0, shelf = start, deepest = 0, widest = 0;
    for (const block of blocks) {
      if (across > 0 && across + block.across > limit) { shelf += deepest; across = 0; deepest = 0; }
      for (const [id, offset] of block.at) into.set(id, { across: across + offset.across, along: shelf + offset.along });
      across += block.across;
      widest = Math.max(widest, across);
      deepest = Math.max(deepest, block.along);
    }
    return { across: widest, along: shelf + deepest };
  };
  const block = (card: ZoneCard): Block => {
    seen.add(card.id);
    const at: Block['at'] = new Map([[card.id, { across: 0, along: 0 }]]);
    const blocks: Block[] = [];
    for (const child of (children.get(card.id) || []).sort(byLabel)) if (!seen.has(child.id)) blocks.push(block(child));
    if (!blocks.length) return { across: 1, along: 1, at };
    const size = shelve(blocks, 1, at);
    return { across: Math.max(1, size.across), along: size.along, at };
  };
  const blocks: Block[] = [];
  for (const root of cards.filter(card => !hasParent.has(card.id) && children.has(card.id)).sort(byLabel)) blocks.push(block(root));
  // A parent cycle has no root: start it anywhere.
  for (const card of cards.filter(card => children.has(card.id) || hasParent.has(card.id)).sort(byLabel)) if (!seen.has(card.id)) blocks.push(block(card));
  const placed: Block['at'] = new Map();
  const tree = shelve(blocks, 0, placed);
  const cells = new Map<string, { col: number; row: number }>();
  for (const [id, offset] of placed) cells.set(id, direction === 'right' ? { col: offset.along, row: offset.across } : { col: offset.across, row: offset.along });
  const singles = cards.filter(card => !cells.has(card.id));
  const treeCols = direction === 'right' ? tree.along : tree.across;
  const treeRows = direction === 'right' ? tree.across : tree.along;
  // Growing down, a narrow tree must not stack its loose cards in one tall column.
  const perRow = direction === 'right' ? treeCols : Math.max(treeCols, Math.ceil(Math.sqrt(singles.length)));
  singles.forEach((card, k) => cells.set(card.id, { col: k % perRow, row: treeRows + Math.floor(k / perRow) }));
  return { cells, cols: Math.max(treeCols, singles.length ? perRow : 0), rows: treeRows + Math.ceil(singles.length / perRow) };
}

/**
 * A hierarchy zone. ``fit`` decides the shelf limit: the smallest limit for
 * which it returns true, found by binary search (a larger limit gives a wider,
 * shallower tree), or no limit when none does.
 */
function measureHierarchy(cards: ZoneCard[], cellH: number, direction: Direction, gapX: number,
  fit?: (tree: { cols: number; rows: number }) => boolean): Measured | null {
  let tree = hierarchyCells(cards, direction);
  if (!tree) return null;
  // The widest tree is the shallowest: when even it does not fit, keep it.
  if (fit && fit(tree)) {
    let lo = 1, hi = cards.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (fit(hierarchyCells(cards, direction, mid)!)) hi = mid; else lo = mid + 1;
    }
    tree = hierarchyCells(cards, direction, lo)!;
  }
  const cellW = cellWidth(cards);
  const width = Math.max(MIN_ZONE_WIDTH, tree.cols * cellW + (tree.cols - 1) * gapX + 2 * ZONE_PAD);
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
function measureZone(cards: ZoneCard[], rows: number, cellH: number, gapX: number): Measured {
  // Continuants: the bottom band, where subclasses sit below their parent.
  // A tree as narrow as it can be in ``rows`` rows.
  const tree = measureHierarchy(cards, cellH, 'down', gapX, size => size.rows <= rows);
  if (tree) return tree;
  const cols = Math.max(1, Math.ceil(cards.length / Math.min(rows, cards.length)));
  const used = Math.ceil(cards.length / cols);
  const cellW = cellWidth(cards);
  const width = Math.max(MIN_ZONE_WIDTH, cols * cellW + (cols - 1) * gapX + 2 * ZONE_PAD);
  return { cols, cellW, cellH, width, height: zoneHeight(used, cellH) };
}

/** A zone of a given width: as many columns as fit, and the rows that leaves. */
function fitZone(cards: ZoneCard[], width: number, cellH: number, gapX: number): Measured {
  // Occurrents: the top band, where subclasses sit right of their parent.
  // A tree as shallow as it can be in the columns that fit.
  const within = (cols: number) => cols * cellWidth(cards) + (cols - 1) * gapX + 2 * ZONE_PAD <= Math.max(width, MIN_ZONE_WIDTH);
  const tree = measureHierarchy(cards, cellH, 'right', gapX, size => within(size.cols));
  if (tree) return { ...tree, width: Math.max(width, tree.width) };
  const cellW = cellWidth(cards);
  const fits = Math.max(1, Math.floor((width - 2 * ZONE_PAD + gapX) / (cellW + gapX)));
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
  const widest = Math.max(0, ...linked.map(link => link.labelWidth || 0));
  const gapX = widest ? Math.min(MAX_GAP_X, Math.max(CARD_GAP_X, Math.ceil(widest + LABEL_ROOM))) : CARD_GAP_X;
  const cellHeight = (keys: string[]) => Math.max(0, ...keys.flatMap(key => groups.get(key)!.map(card => card.height)));
  const topCellH = cellHeight(top);
  const bottomCellH = cellHeight(bottom);

  const bottomBand = (rows: number) => {
    const zones = bottom.map(key => measureZone(groups.get(key)!, rows, bottomCellH, gapX));
    const width = zones.reduce((sum, zone, i) => sum + zone.width + spacing.gapBefore(i), 0);
    return { zones, width, height: Math.max(0, ...zones.map(zone => zone.height)) };
  };
  // The top band spans the view: Process takes 70% of it when Temporal Region shares it.
  const shares = top.length > 1 ? [PROCESS_SHARE, 1 - PROCESS_SHARE] : [1];
  const topGap = top.length > 1 ? spacing.topGap : 0;
  const oneColumn = (key: string) => measureHierarchy(groups.get(key)!, topCellH, 'right', gapX)?.width ?? Math.max(MIN_ZONE_WIDTH, cellWidth(groups.get(key)!) + 2 * ZONE_PAD);
  const innerMin = top.length ? Math.max(...top.map((key, i) => (oneColumn(key) + topGap / 2) / shares[i])) : 0;
  const topBand = (inner: number) => {
    const zones = top.map((key, i) => fitZone(groups.get(key)!, shares[i] * inner - topGap / 2, topCellH, gapX));
    return { zones, height: Math.max(0, ...zones.map(zone => zone.height)) };
  };

  const corridor = top.length && bottom.length ? spacing.corridor : 0;
  let best: { score: number; lower: ReturnType<typeof bottomBand>; upper: ReturnType<typeof topBand>; inner: number; width: number; height: number } | null = null;
  // Enough rows for the largest zone to stand in one column, if that is the shape of the view.
  const most = Math.max(1, ...bottom.map(key => groups.get(key)!.length));
  for (let rows = 1; rows <= Math.max(8, most); rows += 1) {
    const lower = bottomBand(rows);
    const inner = Math.max(lower.width, innerMin);
    const upper = topBand(inner);
    const width = inner + spacing.left + MARGIN;
    const height = spacing.above + upper.height + corridor + lower.height + (bottom.length ? spacing.below : MARGIN);
    const score = Math.abs(Math.log(width / height / aspect));
    if (!best || score < best.score - 1e-9) best = { score, lower, upper, inner, width, height };
  }
  const layout = best!;

  // Where a connector leaving a zone heads: the side of the card its rule gives,
  // or else the side the other zone lies on.
  const heading = (key: string, link: ZoneLink, end: 'source' | 'target'): Side => {
    const fixed = sidesFor?.(link)?.[end];
    if (fixed?.length === 1) return fixed[0];
    const other = zoneOf.get(end === 'source' ? link.target : link.source)!;
    if (top.includes(key) !== top.includes(other)) return top.includes(key) ? 'S' : 'N';
    const row = top.includes(key) ? top : bottom;
    return row.indexOf(other) > row.indexOf(key) ? 'E' : 'W';
  };
  const positions = new Map<string, { x: number; y: number }>();
  const zones: Zone[] = [];
  const place = (key: string, zone: Measured, x: number, y: number, bandHeight: number) => {
    const list = groups.get(key)!;
    zones.push({ key, x, y, width: zone.width, height: bandHeight });
    const flow = !zone.cells;
    const start = zone.cells ?? new Map(list.map((card, k) => [card.id, { col: k % zone.cols, row: Math.floor(k / zone.cols) }]));
    const used = Math.max(...[...start.values()].map(cell => cell.row)) + 1;
    const pitch = zone.cellH + CARD_GAP_Y;
    const room = bandHeight - ZONE_HEADER - 2 * ZONE_PAD;
    // Centred by whole rows, so rows line up with the zones beside it.
    const offset = Math.max(0, Math.floor(Math.floor((room + CARD_GAP_Y) / pitch - used) / 2));
    // Classes in a hierarchy keep their cells; the others move to where their connectors are short.
    const inTree = new Set(flow ? [] : list.filter(card => (card.parent && start.has(card.parent)) || list.some(other => other.parent === card.id)).map(card => card.id));
    const cells = arrangeCells(list.map(card => card.id), start, {
      cols: zone.cols, rows: used, pitchX: zone.cellW + gapX, pitchY: pitch, fixed: inTree,
      links: links.filter(link => link.source !== link.target && (zoneOf.get(link.source) === key || zoneOf.get(link.target) === key))
        .map(link => ({ source: link.source, target: link.target,
          sourceSide: zoneOf.get(link.source) === key ? heading(key, link, 'source') : undefined,
          targetSide: zoneOf.get(link.target) === key ? heading(key, link, 'target') : undefined,
          inside: zoneOf.get(link.source) === key && zoneOf.get(link.target) === key })),
    });
    const cols = Math.max(...[...cells.values()].map(cell => cell.col)) + 1;
    const blockWidth = cols * zone.cellW + (cols - 1) * gapX;
    for (const card of list) {
      const cell = cells.get(card.id)!;
      positions.set(card.id, {
        x: x + (zone.width - blockWidth) / 2 + cell.col * (zone.cellW + gapX) + zone.cellW / 2,
        y: y + ZONE_HEADER + ZONE_PAD + (offset + cell.row) * pitch + zone.cellH / 2,
      });
    }
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

type Cell = { col: number; row: number };
type CellLink = { source: string; target: string; sourceSide?: Side; targetSide?: Side; inside: boolean };
const LINK_WEIGHT = 1; // per unit of connector length
const BEND_WEIGHT = 90; // two cards in neither the same row nor column need a bend
const BLOCK_WEIGHT = 260; // a card in the way of a straight connector forces a detour
const EXIT_WEIGHT = 0.6; // per unit from the border a connector leaves the zone by
const GATHER_WEIGHT = 0.02; // connected cards gather in the top-left; loose cards take what is left

/**
 * Cells for the cards of one zone: the assignment of cards to the cells of a
 * ``cols`` × ``rows`` grid that makes the connectors shortest and straightest.
 * The cost of a placement is, over the connectors inside the zone, their length
 * (Manhattan, in canvas units), a bend when the two cards share neither row nor
 * column, and a detour when a card stands between two that do; over those that
 * leave the zone, the distance from the card to the border they leave by. It is
 * minimised by local search: swap two cells (one may be empty) whenever that
 * lowers the cost, until no swap does. ``fixed`` cards keep their cells.
 */
export function arrangeCells(ids: string[], start: Map<string, Cell>, options: {
  cols: number; rows: number; pitchX: number; pitchY: number; fixed?: Set<string>; links: CellLink[];
}): Map<string, Cell> {
  const { cols, rows, pitchX, pitchY, links } = options;
  const fixed = options.fixed || new Set<string>();
  const cells = new Map(start);
  const movable = ids.filter(id => !fixed.has(id));
  if (movable.length < 1 || !links.length) return cells;
  const byCell = new Map<number, string>();
  const index = (cell: Cell) => cell.row * cols + cell.col;
  for (const [id, cell] of cells) byCell.set(index(cell), id);
  const touching = new Map(ids.map(id => [id, [] as CellLink[]]));
  for (const link of links) {
    touching.get(link.source)?.push(link);
    if (link.target !== link.source) touching.get(link.target)?.push(link);
  }
  const exit = (cell: Cell, side: Side) => side === 'N' ? cell.row * pitchY : side === 'S' ? (rows - 1 - cell.row) * pitchY
    : side === 'W' ? cell.col * pitchX : (cols - 1 - cell.col) * pitchX;
  const blocked = (a: Cell, b: Cell) => {
    if (a.row === b.row) { for (let c = Math.min(a.col, b.col) + 1; c < Math.max(a.col, b.col); c += 1) if (byCell.has(a.row * cols + c)) return true; }
    else if (a.col === b.col) { for (let r = Math.min(a.row, b.row) + 1; r < Math.max(a.row, b.row); r += 1) if (byCell.has(r * cols + a.col)) return true; }
    return false;
  };
  const linkCost = (link: CellLink) => {
    if (link.inside) {
      const a = cells.get(link.source)!, b = cells.get(link.target)!;
      const dx = Math.abs(a.col - b.col), dy = Math.abs(a.row - b.row);
      return LINK_WEIGHT * (dx * pitchX + dy * pitchY) + (dx && dy ? BEND_WEIGHT : 0) + (blocked(a, b) ? BLOCK_WEIGHT : 0);
    }
    let cost = 0;
    if (link.sourceSide) cost += EXIT_WEIGHT * exit(cells.get(link.source)!, link.sourceSide);
    if (link.targetSide) cost += EXIT_WEIGHT * exit(cells.get(link.target)!, link.targetSide);
    return cost;
  };
  const gather = (id: string) => (touching.get(id)!.length ? GATHER_WEIGHT * (cells.get(id)!.row * pitchY + cells.get(id)!.col * pitchX) : 0);
  // A swap changes the cost of the links of the two cards, and may put a card
  // between two others: ``blockers`` counts those over every inside link.
  const inside = links.filter(link => link.inside);
  const local = (ids2: string[]) => {
    const seen = new Set<CellLink>();
    let cost = 0;
    for (const id of ids2) for (const link of touching.get(id) || []) if (!seen.has(link)) { seen.add(link); cost += linkCost(link); }
    for (const id of ids2) cost += gather(id);
    return cost;
  };
  const blockers = () => inside.reduce((sum, link) => sum + (blocked(cells.get(link.source)!, cells.get(link.target)!) ? BLOCK_WEIGHT : 0), 0);
  const free: Cell[] = [];
  const reserved = new Set([...fixed].map(id => index(cells.get(id)!)));
  for (let row = 0; row < rows; row += 1) for (let col = 0; col < cols; col += 1) if (!reserved.has(row * cols + col)) free.push({ col, row });
  const move = (id: string | undefined, cell: Cell) => { if (id) { cells.set(id, cell); byCell.set(index(cell), id); } else byCell.delete(index(cell)); };
  for (let round = 0; round < 30; round += 1) {
    let improved = false;
    for (const id of movable) {
      for (const target of free) {
        const here = cells.get(id)!;
        if (here.col === target.col && here.row === target.row) continue;
        const other = byCell.get(index(target));
        const involved = other ? [id, other] : [id];
        const before = local(involved) + blockers();
        move(id, target); move(other, here);
        const after = local(involved) + blockers();
        if (after < before - 1e-6) { improved = true; continue; }
        move(id, here); move(other, target);
      }
    }
    if (!improved) break;
  }
  return cells;
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
