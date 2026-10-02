import { describe, expect, it } from 'vitest';
import { pollingTrace, span, trace } from './traces-fixtures';
import {
  GROUP_MIN,
  buildRows,
  buildTree,
  formatSpanMs,
  groupAttributes,
  isTraceId,
  labelSide,
  layoutRows,
  matchingSpans,
  pathTo,
  placement,
  selfTime,
  serviceColor,
  shortService,
  ticks,
} from './traces-model';

describe('buildRows', () => {
  it('orders spans depth-first by start with depth, children and self time', () => {
    const rows = buildRows(trace());

    expect(rows.map((r) => [r.span.span_id, r.depth, r.children])).toEqual([
      ['a', 0, 1],
      ['b', 1, 2],
      ['c', 2, 0],
      ['d', 2, 0],
    ]);
    expect(rows[0].selfMs).toBe(20);
    expect(rows[1].selfMs).toBe(30);
  });

  it('makes spans with a missing parent roots and survives cycles', () => {
    const rows = buildRows(
      trace({
        spans: [
          span({ span_id: 'x', parent_id: 'gone', start_ms: 5 }),
          span({ span_id: 'y', parent_id: 'y' }),
          span({ span_id: 'p', parent_id: 'q' }),
          span({ span_id: 'q', parent_id: 'p' }),
        ],
      }),
    );

    expect(rows.map((r) => [r.span.span_id, r.depth])).toEqual([
      ['y', 0],
      ['x', 0],
      ['p', 0],
      ['q', 1],
    ]);
  });
});

describe('selfTime', () => {
  it('subtracts the union of children clipped to the span', () => {
    const parent = span({ span_id: 'p', start_ms: 0, duration_ms: 100 });
    const kids = [
      span({ span_id: '1', start_ms: 10, duration_ms: 30 }),
      span({ span_id: '2', start_ms: 20, duration_ms: 30 }),
      span({ span_id: '3', start_ms: 90, duration_ms: 50 }),
    ];

    expect(selfTime(parent, kids)).toBe(50);
    expect(selfTime(parent, [])).toBe(100);
  });
});

const ids = (rows: ReturnType<typeof layoutRows>) =>
  rows.map((r) => (r.kind === 'span' ? `${r.row.span.span_id}@${r.depth}` : `${r.group.spans.length}x ${r.group.name}@${r.depth}`));
const none = new Set<string>();

describe('layoutRows', () => {
  it('hides the subtree under collapsed spans', () => {
    const tree = buildTree(trace());

    expect(ids(layoutRows(tree, { collapsed: new Set(['b']), openGroups: none, grouping: true }))).toEqual(['a@0', 'b@1']);
    expect(layoutRows(tree, { collapsed: none, openGroups: none, grouping: true })).toHaveLength(4);
  });

  it(`folds ${GROUP_MIN} or more same-named siblings into one row where the first starts`, () => {
    const rows = layoutRows(buildTree(pollingTrace()), { collapsed: none, openGroups: none, grouping: true });

    expect(ids(rows)).toEqual(['r@0', 's@1', '6x agent/status@1']);
    const group = rows[2].kind === 'group' ? rows[2].group : null;
    expect(group).toMatchObject({ key: 'r|nexus-api|agent/status', start_ms: 50, end_ms: 560, total_ms: 60, errors: 1, every_ms: 100 });
  });

  it('lists an open group one level deeper, each span with its subtree', () => {
    const rows = layoutRows(buildTree(pollingTrace()), {
      collapsed: new Set(['p1']),
      openGroups: new Set(['r|nexus-api|agent/status']),
      grouping: true,
    });

    expect(ids(rows).slice(2, 7)).toEqual(['6x agent/status@1', 'p0@2', 'g0@3', 'p1@2', 'p2@2']);
  });

  it('shows every span without grouping', () => {
    expect(layoutRows(buildTree(pollingTrace()), { collapsed: none, openGroups: none, grouping: false })).toHaveLength(14);
  });
});

describe('pathTo', () => {
  it('names the ancestors and groups to open to show a span', () => {
    expect(pathTo(pollingTrace(), 'g3')).toEqual({
      ancestors: ['p3', 'r'],
      groups: ['p3|document|document/get', 'r|nexus-api|agent/status', '|nexus-api|POST /api/chat/stream'],
    });
    expect(pathTo(pollingTrace(), 'missing')).toEqual({ ancestors: [], groups: [] });
  });
});

describe('matchingSpans', () => {

  it('matches name, service and attributes and keeps ancestors', () => {
    const rows = buildRows(trace());

    expect(matchingSpans(rows, '  ')).toBeNull();
    expect([...(matchingSpans(rows, 'VECTOR') ?? [])].sort()).toEqual(['a', 'b', 'd']);
    expect([...(matchingSpans(rows, 'rpc.method=get') ?? [])].sort()).toEqual(['a', 'b', 'c']);
    expect(matchingSpans(rows, 'nothing')?.size).toBe(0);
  });
});

describe('formatting and layout', () => {
  it('formats durations from microseconds to seconds', () => {
    expect(formatSpanMs(0.82)).toBe('820 µs');
    expect(formatSpanMs(4.213)).toBe('4.21 ms');
    expect(formatSpanMs(42.04)).toBe('42.0 ms');
    expect(formatSpanMs(420)).toBe('420 ms');
    expect(formatSpanMs(1300)).toBe('1.30 s');
    expect(formatSpanMs(42_000)).toBe('42.0 s');
  });

  it('puts ruler ticks on round steps inside the window', () => {
    expect(ticks(0, 100)).toEqual([0, 20, 40, 60, 80, 100]);
    expect(ticks(13, 37)).toEqual([15, 20, 25, 30, 35]);
  });

  it('places bars in the window and clamps what falls outside', () => {
    expect(placement(25, 50, [0, 100])).toEqual({ left: 25, width: 50 });
    expect(placement(0, 100, [50, 100])).toEqual({ left: 0, width: 100 });
    expect(placement(10, 5, [50, 100])).toEqual({ left: 0, width: 0 });
  });

  it('puts duration labels where they fit', () => {
    expect(labelSide({ left: 10, width: 30 })).toBe('right');
    expect(labelSide({ left: 40, width: 50 })).toBe('left');
    expect(labelSide({ left: 2, width: 95 })).toBe('inside');
  });

  it('shortens module ids to their last segment', () => {
    expect(shortService('operations.projects.nats_probe.probe')).toBe('probe');
    expect(shortService('zen-engine')).toBe('zen-engine');
    expect(shortService('odd.')).toBe('odd.');
  });

  it('gives each service a stable color', () => {
    expect(serviceColor('document')).toBe(serviceColor('document'));
    expect(serviceColor('document')).toMatch(/^#[0-9A-F]{6}$/);
  });

  it('groups attributes by namespace in a stable order', () => {
    const groups = groupAttributes({ 'zz.custom': 1, 'http.method': 'GET', 'abi.job': 'digest', 'url.path': '/x' });

    expect(groups.map((g) => g.label)).toEqual(['ABI', 'HTTP', 'Other']);
    expect(groups[1].entries.map(([k]) => k)).toEqual(['http.method', 'url.path']);
  });

  it('recognizes trace ids', () => {
    expect(isTraceId(' 4BF92F3577B34DA6A3CE929D0E0E4736 ')).toBe(true);
    expect(isTraceId('4bf92f35')).toBe(false);
  });
});
