'use client';

/**
 * A trace as a waterfall: one row per span in tree order, bars placed on the
 * trace's time axis. Repeated calls (polling) fold into one row. Drag on the
 * minimap or double-click a span to zoom.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown, Layers, Search, ZoomOut } from 'lucide-react';
import { Hint } from '../data/data-ui';
import {
  buildTree,
  flattenTree,
  formatSpanMs,
  labelSide,
  layoutRows,
  matchingSpans,
  pathTo,
  placement,
  serviceColor,
  shortService,
  ticks,
  type DisplayRow,
  type Row,
  type SpanGroup,
} from './traces-model';
import type { Trace } from './traces-types';

const ROW_HEIGHT = 30;
const VIRTUAL_FROM = 300;
const OVERSCAN = 12;
const GROUP_TICKS = 400;

function Minimap({
  rows,
  total,
  window,
  onZoom,
}: {
  rows: Row[];
  total: number;
  window: [number, number];
  onZoom: (window: [number, number]) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // The ref is the source of truth (events can outrun renders); the state draws the selection.
  const dragging = useRef<[number, number] | null>(null);
  const [drag, setDrag] = useState<[number, number] | null>(null);
  const track = (next: [number, number] | null) => {
    dragging.current = next;
    setDrag(next);
  };
  const toMs = (clientX: number) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box || box.width === 0) return 0;
    return Math.min(total, Math.max(0, ((clientX - box.left) / box.width) * total));
  };
  const lanes = Math.max(1, Math.min(rows.length, 40));
  const selection = drag ?? (window[0] > 0 || window[1] < total ? window : null);
  return (
    <div
      ref={ref}
      className="trace-minimap"
      role="presentation"
      onPointerDown={(e) => {
        try {
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
        } catch {
          // Not an active pointer (synthetic events); dragging still works inside the minimap.
        }
        const at = toMs(e.clientX);
        track([at, at]);
      }}
      onPointerMove={(e) => dragging.current && track([dragging.current[0], toMs(e.clientX)])}
      onPointerUp={(e) => {
        const current = dragging.current;
        if (current) {
          const [a, b] = [Math.min(current[0], toMs(e.clientX)), Math.max(current[0], toMs(e.clientX))];
          if (b - a > total / 500) onZoom([a, b]);
        }
        track(null);
      }}
    >
      <svg viewBox={`0 0 100 ${lanes}`} preserveAspectRatio="none" aria-hidden="true">
        {rows.slice(0, 2000).map((row, i) => {
          const p = placement(row.span.start_ms, row.span.duration_ms, [0, total]);
          return (
            <rect
              key={row.span.span_id}
              x={p.left}
              width={Math.max(p.width, 0.15)}
              y={(i % lanes) + 0.15}
              height={0.7}
              fill={row.span.status === 'error' ? '#EF4444' : serviceColor(row.span.service)}
            />
          );
        })}
      </svg>
      {selection && (
        <span
          className="trace-minimap-window"
          style={{
            left: `${(Math.min(...selection) / total) * 100}%`,
            width: `${(Math.abs(selection[1] - selection[0]) / total) * 100}%`,
          }}
        />
      )}
    </div>
  );
}

function Ruler({ window }: { window: [number, number] }) {
  const marks = ticks(window[0], window[1]);
  const total = Math.max(window[1] - window[0], 1e-6);
  return (
    <div className="trace-ruler" aria-hidden="true">
      {marks.map((t) => (
        <span key={t} className="trace-tick" style={{ left: `${((t - window[0]) / total) * 100}%` }}>
          {formatSpanMs(t)}
        </span>
      ))}
    </div>
  );
}

function SpanRow({
  row,
  depth,
  window,
  selected,
  collapsed,
  onSelect,
  onToggle,
  onZoom,
}: {
  row: Row;
  depth: number;
  window: [number, number];
  selected: boolean;
  collapsed: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onZoom: () => void;
}) {
  const { span } = row;
  const color = serviceColor(span.service);
  const p = placement(span.start_ms, span.duration_ms, window);
  const error = span.status === 'error';
  const side = labelSide(p);
  return (
    <div
      role="treeitem"
      aria-selected={selected}
      aria-expanded={row.children ? !collapsed : undefined}
      aria-level={depth + 1}
      tabIndex={-1}
      data-span={span.span_id}
      className={`trace-row${selected ? ' trace-row-selected' : ''}${error ? ' trace-row-error' : ''}`}
      style={{ height: ROW_HEIGHT }}
      onClick={onSelect}
      onDoubleClick={onZoom}
    >
      <span className="trace-label" style={{ paddingLeft: 8 + depth * 14 }}>
        {row.children ? (
          <button
            type="button"
            className="trace-caret"
            aria-label={collapsed ? 'Expand' : 'Collapse'}
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
          >
            {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          </button>
        ) : (
          <span className="trace-caret-space" />
        )}
        <span className="trace-service-dot" style={{ backgroundColor: color }} aria-hidden="true" />
        <span className="trace-service" title={span.service}>
          {shortService(span.service)}
        </span>
        <span className="trace-name" title={span.name}>
          {span.name}
        </span>
        {error && <AlertCircle size={12} className="trace-error-icon" aria-label="Error" />}
        {collapsed && row.children > 0 && <span className="trace-hidden-count">+{row.children}</span>}
      </span>
      <span className="trace-lane">
        <span
          className="trace-bar"
          style={{ left: `${p.left}%`, width: `max(${p.width}%, 2px)`, backgroundColor: error ? '#EF4444' : color }}
        >
          {span.duration_ms > 0 && row.selfMs < span.duration_ms && (
            <span className="trace-bar-children" style={{ width: `${100 - (row.selfMs / span.duration_ms) * 100}%` }} />
          )}
          {span.events.map((event, i) => (
            <span
              key={i}
              className="trace-bar-event"
              style={{ left: `${span.duration_ms ? (event.offset_ms / span.duration_ms) * 100 : 0}%` }}
              title={event.name}
            />
          ))}
        </span>
        <span
          className={`trace-bar-label trace-bar-label-${side}`}
          style={
            side === 'right'
              ? { left: `calc(${p.left + p.width}% + 6px)` }
              : side === 'left'
                ? { right: `calc(${100 - p.left}% + 6px)` }
                : { right: `calc(${100 - p.left - p.width}% + 6px)` }
          }
        >
          {formatSpanMs(span.duration_ms)}
        </span>
      </span>
    </div>
  );
}

function groupSummary(group: SpanGroup): string {
  const calls = group.spans.length;
  const longest = Math.max(...group.spans.map((s) => s.duration_ms));
  return [
    `${calls} calls to ${group.name}`,
    `${formatSpanMs(group.total_ms)} in total, ${formatSpanMs(group.total_ms / calls)} on average, ${formatSpanMs(longest)} at most`,
    group.every_ms !== null ? `one every ${formatSpanMs(group.every_ms)}` : null,
    `from +${formatSpanMs(group.start_ms)} to +${formatSpanMs(group.end_ms)}`,
    group.errors ? `${group.errors} failed` : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

/** Repeated calls as one row: count and totals by the name, their range with a tick per call in the lane. */
function GroupRow({
  group,
  depth,
  open,
  window,
  onToggle,
  onZoom,
}: {
  group: SpanGroup;
  depth: number;
  open: boolean;
  window: [number, number];
  onToggle: () => void;
  onZoom: () => void;
}) {
  const color = serviceColor(group.service);
  const range = placement(group.start_ms, group.end_ms - group.start_ms, window);
  return (
    <div
      role="treeitem"
      aria-selected={false}
      aria-expanded={open}
      aria-level={depth + 1}
      tabIndex={-1}
      data-group={group.key}
      className={`trace-row trace-group-row${group.errors ? ' trace-row-error' : ''}`}
      style={{ height: ROW_HEIGHT }}
      title={groupSummary(group)}
      onClick={onToggle}
      onDoubleClick={onZoom}
    >
      <span className="trace-label" style={{ paddingLeft: 8 + depth * 14 }}>
        <button
          type="button"
          className="trace-caret"
          aria-label={open ? 'Fold calls' : 'Unfold calls'}
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>
        <span className="trace-service-dot" style={{ backgroundColor: color }} aria-hidden="true" />
        <span className="trace-service" title={group.service}>
          {shortService(group.service)}
        </span>
        <span className="trace-name">{group.name}</span>
        <span className="trace-group-count">{group.spans.length}×</span>
        {group.errors > 0 && (
          <span className="trace-group-errors">
            <AlertCircle size={11} aria-hidden="true" /> {group.errors}
          </span>
        )}
        <span className="trace-group-stats">
          {formatSpanMs(group.total_ms)} total{group.every_ms !== null ? ` · every ${formatSpanMs(group.every_ms)}` : ''}
        </span>
      </span>
      <span className="trace-lane">
        <span
          className="trace-group-range"
          style={{ left: `${range.left}%`, width: `max(${range.width}%, 2px)`, borderColor: color }}
        />
        {group.spans.slice(0, GROUP_TICKS).map((span) => {
          const p = placement(span.start_ms, span.duration_ms, window);
          return (
            <span
              key={span.span_id}
              className="trace-group-tick"
              style={{ left: `${p.left}%`, width: `max(${p.width}%, 2px)`, backgroundColor: span.status === 'error' ? '#EF4444' : color }}
            />
          );
        })}
      </span>
    </div>
  );
}

export function Waterfall({
  trace,
  selected,
  onSelect,
  height,
}: {
  trace: Trace;
  selected: string | null;
  onSelect: (spanId: string) => void;
  /** Fixed height (embedded); otherwise fills its container. */
  height?: number;
}) {
  const tree = useMemo(() => buildTree(trace), [trace]);
  const rows = useMemo(() => flattenTree(tree), [tree]);
  const childCount = useMemo(() => new Map(rows.map((r) => [r.span.span_id, r.children])), [rows]);
  const total = Math.max(trace.duration_ms, 1e-6);
  const [window, setWindow] = useState<[number, number]>([0, total]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [grouping, setGrouping] = useState(true);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState('');
  const [scrollTop, setScrollTop] = useState(0);
  const [viewport, setViewport] = useState(600);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setWindow([0, total]);
    setCollapsed(new Set());
    setOpenGroups(new Set());
  }, [trace.trace_id, total]);

  // A span selected from elsewhere (a deep link, its parent, a key) is made visible.
  useEffect(() => {
    if (!selected) return;
    const path = pathTo(trace, selected);
    setCollapsed((current) =>
      path.ancestors.some((id) => current.has(id)) ? new Set([...current].filter((id) => !path.ancestors.includes(id))) : current,
    );
    setOpenGroups((current) =>
      path.groups.every((key) => current.has(key)) ? current : new Set([...current, ...path.groups]),
    );
  }, [selected, trace]);

  useEffect(() => {
    const node = scroller.current;
    if (!node || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => setViewport(node.clientHeight || 600));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const matches = useMemo(() => matchingSpans(rows, filter), [rows, filter]);
  // Filtering lists every matching span (and its ancestors), ignoring collapse and groups.
  const shown: DisplayRow[] = useMemo(
    () =>
      matches
        ? layoutRows(tree, { collapsed: new Set(), openGroups, grouping: false }).filter(
            (r) => r.kind === 'span' && matches.has(r.row.span.span_id),
          )
        : layoutRows(tree, { collapsed, openGroups, grouping }),
    [tree, collapsed, openGroups, grouping, matches],
  );
  const groups = shown.filter((r) => r.kind === 'group').length;

  const virtual = shown.length > VIRTUAL_FROM;
  const first = virtual ? Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN) : 0;
  const last = virtual ? Math.min(shown.length, Math.ceil((scrollTop + viewport) / ROW_HEIGHT) + OVERSCAN) : shown.length;
  const zoomed = window[0] > 0 || window[1] < total;

  const flip = (setter: typeof setCollapsed, id: string) =>
    setter((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggle = (id: string) => flip(setCollapsed, id);
  // Unfolded, each call shows as one row (open the ones you want); folding again forgets that.
  const toggleGroup = (group: SpanGroup) => {
    const members = group.spans.filter((s) => (childCount.get(s.span_id) ?? 0) > 0).map((s) => s.span_id);
    const unfolding = !openGroups.has(group.key);
    setCollapsed((current) =>
      unfolding ? new Set([...current, ...members]) : new Set([...current].filter((id) => !members.includes(id))),
    );
    flip(setOpenGroups, group.key);
  };
  const zoomTo = (start: number, end: number) => {
    const pad = Math.max((end - start) * 0.05, total / 2000);
    setWindow([Math.max(0, start - pad), Math.min(total, end + pad)]);
  };

  // Keyboard: ↑/↓ move between spans, ←/→ collapse/expand the selected span.
  const onKeyDown = (event: React.KeyboardEvent) => {
    const index = shown.findIndex((r) => r.kind === 'span' && r.row.span.span_id === selected);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      let at = index < 0 ? (step > 0 ? -1 : shown.length) : index;
      do at += step;
      while (at >= 0 && at < shown.length && shown[at].kind !== 'span');
      const next = shown[at];
      if (next?.kind === 'span') {
        onSelect(next.row.span.span_id);
        const top = at * ROW_HEIGHT;
        const node = scroller.current;
        if (node && (top < node.scrollTop || top > node.scrollTop + node.clientHeight - ROW_HEIGHT)) {
          node.scrollTop = top - node.clientHeight / 2;
        }
      }
    } else if ((event.key === 'ArrowLeft' || event.key === 'ArrowRight') && index >= 0) {
      const current = shown[index];
      if (current.kind !== 'span') return;
      const id = current.row.span.span_id;
      if ((event.key === 'ArrowLeft') !== collapsed.has(id) && current.row.children) toggle(id);
    }
  };

  return (
    <div className="trace-waterfall" style={height ? { height } : undefined}>
      <div className="trace-toolbar">
        <label className="data-search trace-filter">
          <Search size={13} aria-hidden="true" />
          <input
            className="data-search-input"
            placeholder="Filter spans (name, service, attribute)"
            aria-label="Filter spans"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
        <span className="data-muted trace-count">
          {matches ? `${matches.size} of ${rows.length} spans` : `${rows.length} spans`}
          {!matches && groups > 0 ? ` · ${groups} folded` : ''}
          {trace.truncated ? ' (truncated)' : ''}
        </span>
        <span className="data-spacer" />
        {zoomed && (
          <button type="button" className="data-text-button" onClick={() => setWindow([0, total])}>
            <ZoomOut size={13} aria-hidden="true" /> Reset zoom
          </button>
        )}
        <Hint label={grouping ? 'Show repeated calls one by one' : 'Fold repeated calls into one row'}>
          <button
            type="button"
            className="data-icon-button"
            aria-label="Fold repeated calls"
            aria-pressed={grouping}
            onClick={() => setGrouping((on) => !on)}
          >
            <Layers size={14} aria-hidden="true" />
          </button>
        </Hint>
        <Hint label="Expand all">
          <button type="button" className="data-icon-button" aria-label="Expand all" onClick={() => setCollapsed(new Set())}>
            <ChevronsUpDown size={14} aria-hidden="true" />
          </button>
        </Hint>
        <Hint label="Collapse all (then open one level at a time)">
          <button
            type="button"
            className="data-icon-button"
            aria-label="Collapse all"
            onClick={() => {
              setCollapsed(new Set(rows.filter((r) => r.children).map((r) => r.span.span_id)));
              setOpenGroups(new Set());
            }}
          >
            <ChevronsDownUp size={14} aria-hidden="true" />
          </button>
        </Hint>
      </div>
      <Minimap rows={rows} total={total} window={window} onZoom={setWindow} />
      <div className="trace-head">
        <span className="trace-head-label">Service · operation</span>
        <Ruler window={window} />
      </div>
      <div
        ref={scroller}
        className="trace-rows"
        role="tree"
        aria-label="Spans"
        tabIndex={0}
        onKeyDown={onKeyDown}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        <div style={{ height: virtual ? shown.length * ROW_HEIGHT : undefined, position: 'relative' }}>
          <div style={virtual ? { transform: `translateY(${first * ROW_HEIGHT}px)` } : undefined}>
            {shown.slice(first, last).map((item) =>
              item.kind === 'group' ? (
                <GroupRow
                  key={item.group.key}
                  group={item.group}
                  depth={item.depth}
                  open={item.open}
                  window={window}
                  onToggle={() => toggleGroup(item.group)}
                  onZoom={() => zoomTo(item.group.start_ms, item.group.end_ms)}
                />
              ) : (
                <SpanRow
                  key={item.row.span.span_id}
                  row={item.row}
                  depth={item.depth}
                  window={window}
                  selected={selected === item.row.span.span_id}
                  collapsed={collapsed.has(item.row.span.span_id)}
                  onSelect={() => onSelect(item.row.span.span_id)}
                  onToggle={() => toggle(item.row.span.span_id)}
                  onZoom={() => zoomTo(item.row.span.start_ms, item.row.span.start_ms + item.row.span.duration_ms)}
                />
              ),
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
