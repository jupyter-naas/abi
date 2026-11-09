/** Pure helpers for the trace viewer: tree, colors, ruler, filters. */
import type { Span, Trace } from './traces-types';

export interface Row {
  span: Span;
  depth: number;
  children: number;
  /** Duration not covered by direct children (merged overlaps). */
  selfMs: number;
}

export interface Node {
  row: Row;
  kids: Node[];
}

/** The span tree in start order; spans whose parent is absent (or in a cycle) become roots. */
export function buildTree(trace: Trace): Node[] {
  const ids = new Set(trace.spans.map((s) => s.span_id));
  const children = new Map<string, Span[]>();
  const roots: Span[] = [];
  for (const span of trace.spans) {
    if (span.parent_id && ids.has(span.parent_id) && span.parent_id !== span.span_id) {
      const list = children.get(span.parent_id) ?? [];
      list.push(span);
      children.set(span.parent_id, list);
    } else roots.push(span);
  }
  const byStart = (a: Span, b: Span) => a.start_ms - b.start_ms || a.name.localeCompare(b.name);
  const seen = new Set<string>();
  const visit = (span: Span, depth: number): Node | null => {
    if (seen.has(span.span_id)) return null;
    seen.add(span.span_id);
    const kids = (children.get(span.span_id) ?? []).sort(byStart);
    const row = { span, depth, children: kids.length, selfMs: selfTime(span, kids) };
    return { row, kids: kids.map((k) => visit(k, depth + 1)).filter((n): n is Node => n !== null) };
  };
  const tree = roots.sort(byStart).map((r) => visit(r, 0));
  // Spans caught in a parent cycle are unreachable from any root; keep them.
  const stranded = trace.spans.filter((s) => !seen.has(s.span_id)).sort(byStart);
  return [...tree, ...stranded.map((s) => visit(s, 0))].filter((n): n is Node => n !== null);
}

/** The tree depth-first, as rows. */
export function flattenTree(roots: Node[]): Row[] {
  const rows: Row[] = [];
  const walk = (node: Node) => {
    rows.push(node.row);
    node.kids.forEach(walk);
  };
  roots.forEach(walk);
  return rows;
}

export const buildRows = (trace: Trace): Row[] => flattenTree(buildTree(trace));

/** A span's duration minus the union of its children's intervals (clipped to it). */
export function selfTime(span: Span, kids: Span[]): number {
  const start = span.start_ms;
  const end = span.start_ms + span.duration_ms;
  const intervals = kids
    .map((k) => [Math.max(start, k.start_ms), Math.min(end, k.start_ms + k.duration_ms)] as [number, number])
    .filter(([a, b]) => b > a)
    .sort((x, y) => x[0] - y[0]);
  let covered = 0;
  let cursorEnd = -Infinity;
  let cursorStart = 0;
  for (const [a, b] of intervals) {
    if (a > cursorEnd) {
      if (cursorEnd > -Infinity) covered += cursorEnd - cursorStart;
      cursorStart = a;
      cursorEnd = b;
    } else cursorEnd = Math.max(cursorEnd, b);
  }
  if (cursorEnd > -Infinity) covered += cursorEnd - cursorStart;
  return Math.max(0, span.duration_ms - covered);
}

/** Siblings repeated this many times (same service and operation) fold into one row. */
export const GROUP_MIN = 5;

export interface SpanGroup {
  key: string;
  service: string;
  name: string;
  spans: Span[];
  start_ms: number;
  end_ms: number;
  total_ms: number;
  errors: number;
  /** Median time between two starts (a polling cadence), or null under 3 calls. */
  every_ms: number | null;
}

export type DisplayRow =
  | { kind: 'span'; row: Row; depth: number }
  | { kind: 'group'; group: SpanGroup; depth: number; open: boolean };

/** The group a span folds into: its parent in the tree ('' for roots), service and operation. */
export const groupKey = (parentId: string, span: Span) => `${parentId}|${span.service}|${span.name}`;

function makeGroup(key: string, spans: Span[]): SpanGroup {
  const starts = spans.map((s) => s.start_ms).sort((a, b) => a - b);
  const gaps = starts.slice(1).map((t, i) => t - starts[i]).sort((a, b) => a - b);
  return {
    key,
    service: spans[0].service,
    name: spans[0].name,
    spans,
    start_ms: starts[0],
    end_ms: Math.max(...spans.map((s) => s.start_ms + s.duration_ms)),
    total_ms: spans.reduce((n, s) => n + s.duration_ms, 0),
    errors: spans.filter((s) => s.status === 'error').length,
    every_ms: gaps.length >= 2 ? gaps[Math.floor(gaps.length / 2)] : null,
  };
}

/**
 * The rows to draw: subtrees under collapsed spans hidden and, when grouping,
 * repeated siblings folded into one group row where the first of them starts.
 * An open group lists its spans one level deeper.
 */
export function layoutRows(
  roots: Node[],
  { collapsed, openGroups, grouping }: { collapsed: Set<string>; openGroups: Set<string>; grouping: boolean },
): DisplayRow[] {
  const out: DisplayRow[] = [];
  const emit = (node: Node, depth: number) => {
    out.push({ kind: 'span', row: node.row, depth });
    if (!collapsed.has(node.row.span.span_id)) place(node.kids, node.row.span.span_id, depth + 1);
  };
  const place = (nodes: Node[], parentId: string, depth: number) => {
    const repeats = new Map<string, Node[]>();
    if (grouping) {
      for (const node of nodes) {
        const key = groupKey(parentId, node.row.span);
        const list = repeats.get(key) ?? [];
        list.push(node);
        repeats.set(key, list);
      }
    }
    const placed = new Set<string>();
    for (const node of nodes) {
      const key = groupKey(parentId, node.row.span);
      const members = repeats.get(key);
      if (!members || members.length < GROUP_MIN) {
        emit(node, depth);
        continue;
      }
      if (placed.has(key)) continue;
      placed.add(key);
      const open = openGroups.has(key);
      out.push({ kind: 'group', group: makeGroup(key, members.map((m) => m.row.span)), depth, open });
      if (open) members.forEach((m) => emit(m, depth + 1));
    }
  };
  place(roots, '', 0);
  return out;
}

/** What to open so ``spanId`` shows: its ancestors (closest first) and the groups on its path. */
export function pathTo(trace: Trace, spanId: string): { ancestors: string[]; groups: string[] } {
  const byId = new Map(trace.spans.map((s) => [s.span_id, s]));
  const parentOf = (span: Span) =>
    span.parent_id && span.parent_id !== span.span_id && byId.has(span.parent_id) ? span.parent_id : '';
  const ancestors: string[] = [];
  const groups: string[] = [];
  const seen = new Set<string>();
  let span = byId.get(spanId);
  while (span && !seen.has(span.span_id)) {
    seen.add(span.span_id);
    const parent = parentOf(span);
    groups.push(groupKey(parent, span));
    if (!parent) break;
    ancestors.push(parent);
    span = byId.get(parent);
  }
  return { ancestors, groups };
}

/** Span ids matching ``text`` (name, service, attributes), plus their ancestors. */
export function matchingSpans(rows: Row[], text: string): Set<string> | null {
  const needle = text.trim().toLowerCase();
  if (!needle) return null;
  const parents = new Map(rows.map((r) => [r.span.span_id, r.span.parent_id]));
  const hits = new Set<string>();
  for (const { span } of rows) {
    const haystack = [span.name, span.service, ...Object.entries(span.attributes).map(([k, v]) => `${k}=${v}`)]
      .join(' ')
      .toLowerCase();
    if (haystack.includes(needle)) {
      let id: string | null | undefined = span.span_id;
      while (id && !hits.has(id)) {
        hits.add(id);
        id = parents.get(id) ?? null;
      }
    }
  }
  return hits;
}

const PALETTE = [
  '#34D399', '#60A5FA', '#F59E0B', '#A78BFA', '#F472B6', '#22D3EE',
  '#FB923C', '#4ADE80', '#818CF8', '#FACC15', '#2DD4BF', '#E879F9',
];

/** A stable color per service name. */
export function serviceColor(service: string): string {
  let hash = 0;
  for (let i = 0; i < service.length; i += 1) hash = (hash * 31 + service.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

/** "820 µs", "4.21 ms", "1.3 s". */
export function formatSpanMs(ms: number): string {
  if (ms < 1) return `${Math.round(ms * 1000)} µs`;
  if (ms < 10) return `${ms.toFixed(2)} ms`;
  if (ms < 1000) return `${ms.toFixed(ms < 100 ? 1 : 0)} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`;
}

/** A module id's last segment ("operations.projects.nats_probe.probe" → "probe"); other names as is. */
export function shortService(service: string): string {
  const cut = service.lastIndexOf('.');
  return cut > 0 && cut < service.length - 1 ? service.slice(cut + 1) : service;
}

/** Where a bar's duration label fits: after the bar, before it, or inside a bar that fills the lane. */
export function labelSide(p: { left: number; width: number }): 'right' | 'left' | 'inside' {
  if (p.left + p.width < 78) return 'right';
  if (p.left > 12) return 'left';
  return 'inside';
}

/** Ruler ticks at a readable step covering [from, to]. */
export function ticks(from: number, to: number, count = 5): number[] {
  const span = Math.max(to - from, 1e-6);
  const raw = span / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let t = Math.ceil(from / step) * step; t <= to + step * 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}

/** Position of [start, start+duration] in a window, as percentages (clamped). */
export function placement(startMs: number, durationMs: number, window: [number, number]): { left: number; width: number } {
  const [from, to] = window;
  const total = Math.max(to - from, 1e-6);
  const a = Math.max(startMs, from);
  const b = Math.min(startMs + durationMs, to);
  if (b < a) return { left: Math.min(100, Math.max(0, ((startMs - from) / total) * 100)), width: 0 };
  return { left: ((a - from) / total) * 100, width: ((b - a) / total) * 100 };
}

export const ATTRIBUTE_GROUPS: { prefix: string; label: string }[] = [
  { prefix: 'abi.', label: 'ABI' },
  { prefix: 'messaging.', label: 'Messaging' },
  { prefix: 'rpc.', label: 'RPC' },
  { prefix: 'http.', label: 'HTTP' },
  { prefix: 'url.', label: 'HTTP' },
  { prefix: 'server.', label: 'HTTP' },
  { prefix: 'db.', label: 'Database' },
  { prefix: 'otel.', label: 'OpenTelemetry' },
];

/** Attributes grouped by namespace, groups in a stable order, keys sorted. */
export function groupAttributes(attributes: Record<string, unknown>): { label: string; entries: [string, unknown][] }[] {
  const groups = new Map<string, [string, unknown][]>();
  for (const [key, value] of Object.entries(attributes)) {
    const label = ATTRIBUTE_GROUPS.find((g) => key.startsWith(g.prefix))?.label ?? 'Other';
    const list = groups.get(label) ?? [];
    list.push([key, value]);
    groups.set(label, list);
  }
  const order = [...new Set([...ATTRIBUTE_GROUPS.map((g) => g.label), 'Other'])];
  return order
    .filter((label) => groups.has(label))
    .map((label) => ({ label, entries: (groups.get(label) ?? []).sort(([a], [b]) => a.localeCompare(b)) }));
}

export const LOOKBACKS = [
  { id: '15m', label: 'Last 15 min' },
  { id: '1h', label: 'Last hour' },
  { id: '6h', label: 'Last 6 hours' },
  { id: '24h', label: 'Last 24 hours' },
  { id: '7d', label: 'Last 7 days' },
];

export const isTraceId = (value: string) => /^[0-9a-f]{32}$/i.test(value.trim());
