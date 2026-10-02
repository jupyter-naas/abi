/**
 * BFO zones: the seven buckets placed where the BFO 7 Buckets diagram puts them.
 *
 * Occurrents sit in a band on top (Process on the left, Temporal Region on the
 * right); continuants in a band below (Material Entity, Site, Generically
 * Dependent Continuant, Quality, Realizable). Anything else lands in an
 * "Other" zone at the end of the continuants. A zone is as big as the cards it
 * holds. Ported from the people app's network layout
 * (naas_abi_marketplace intelligence/modules/people/apps/people/web/lib/network-layout.js).
 */

export type ZoneCard = { id: string; width: number; height: number; bucket: string; label: string };
export type ZoneLink = { source: string; target: string };
export type Zone = { key: string; x: number; y: number; width: number; height: number };
export type Band = { label: 'OCCURRENTS' | 'CONTINUANTS'; x: number; y: number; width: number; height: number };
export type ZoneLayout = { positions: Map<string, { x: number; y: number }>; zones: Zone[]; bands: Band[] };

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

type Measured = { cols: number; cellW: number; cellH: number; width: number; height: number };

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
  const cols = Math.max(1, Math.ceil(cards.length / Math.min(rows, cards.length)));
  const used = Math.ceil(cards.length / cols);
  const cellW = cellWidth(cards);
  const width = Math.max(MIN_ZONE_WIDTH, cols * cellW + (cols - 1) * CARD_GAP_X + 2 * ZONE_PAD);
  return { cols, cellW, cellH, width, height: zoneHeight(used, cellH) };
}

/** A zone of a given width: as many columns as fit, and the rows that leaves. */
function fitZone(cards: ZoneCard[], width: number, cellH: number): Measured {
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
export function bfoZoneLayout(cards: ZoneCard[], links: ZoneLink[], { aspect = 1.7 } = {}): ZoneLayout {
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
  const cellHeight = (keys: string[]) => Math.max(0, ...keys.flatMap(key => groups.get(key)!.map(card => card.height)));
  const topCellH = cellHeight(top);
  const bottomCellH = cellHeight(bottom);

  const bottomBand = (rows: number) => {
    const zones = bottom.map(key => measureZone(groups.get(key)!, rows, bottomCellH));
    const width = zones.reduce((sum, zone, i) => sum + zone.width + (i ? ZONE_GAP : 0), 0);
    return { zones, width, height: Math.max(0, ...zones.map(zone => zone.height)) };
  };
  // The top band spans the view: Process takes 70% of it when Temporal Region shares it.
  const shares = top.length > 1 ? [PROCESS_SHARE, 1 - PROCESS_SHARE] : [1];
  const topGap = top.length > 1 ? ZONE_GAP : 0;
  const oneColumn = (key: string) => Math.max(MIN_ZONE_WIDTH, cellWidth(groups.get(key)!) + 2 * ZONE_PAD);
  const innerMin = top.length ? Math.max(...top.map((key, i) => (oneColumn(key) + topGap / 2) / shares[i])) : 0;
  const topBand = (inner: number) => {
    const zones = top.map((key, i) => fitZone(groups.get(key)!, shares[i] * inner - topGap / 2, topCellH));
    return { zones, height: Math.max(0, ...zones.map(zone => zone.height)) };
  };

  const corridor = top.length && bottom.length ? CORRIDOR : 0;
  let best: { score: number; lower: ReturnType<typeof bottomBand>; upper: ReturnType<typeof topBand>; inner: number; width: number; height: number } | null = null;
  for (let rows = 1; rows <= 8; rows += 1) {
    const lower = bottomBand(rows);
    const inner = Math.max(lower.width, innerMin);
    const upper = topBand(inner);
    const width = inner + 2 * MARGIN;
    const height = 2 * MARGIN + upper.height + corridor + lower.height;
    const score = Math.abs(Math.log(width / height / aspect));
    if (!best || score < best.score - 1e-9) best = { score, lower, upper, inner, width, height };
  }
  const layout = best!;

  const positions = new Map<string, { x: number; y: number }>();
  const zones: Zone[] = [];
  const place = (key: string, zone: Measured, x: number, y: number, bandHeight: number) => {
    const list = groups.get(key)!;
    zones.push({ key, x, y, width: zone.width, height: bandHeight });
    const used = Math.ceil(list.length / zone.cols);
    const pitch = zone.cellH + CARD_GAP_Y;
    const room = bandHeight - ZONE_HEADER - 2 * ZONE_PAD;
    // Centred by whole rows, so rows line up with the zones beside it.
    const offset = Math.max(0, Math.floor(Math.floor((room + CARD_GAP_Y) / pitch - used) / 2));
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
  const upperY = MARGIN;
  const lowerY = MARGIN + layout.upper.height + corridor;
  if (top.length) {
    place(top[0], layout.upper.zones[0], MARGIN, upperY, layout.upper.height);
    if (top.length > 1) {
      const right = layout.upper.zones[1];
      place(top[1], right, MARGIN + layout.inner - right.width, upperY, layout.upper.height);
    }
  }
  let x = MARGIN + (layout.inner - layout.lower.width) / 2;
  bottom.forEach((key, i) => {
    if (i) x += ZONE_GAP;
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
  return { positions, zones, bands };
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
