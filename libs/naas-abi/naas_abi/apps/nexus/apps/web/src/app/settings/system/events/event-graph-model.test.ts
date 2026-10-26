import { describe, expect, it } from 'vitest';
import type { PlatformEvent } from './bfo-event-projection';
import {
  buildEventGraphModel,
  emptyFilters,
  filterSummary,
  processLabel,
  processTypeLabel,
} from './event-graph-model';
import { coerceGraphParams, defaultGraphParams } from './event-graph-params';

function event(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'evt-1',
    _class_uri: 'http://ontology.naas.ai/abi/agent/AgentToolCalled',
    _seq: 1,
    _stored_at: '2026-07-31T12:00:00Z',
    created_at: '2026-07-31T12:00:00Z',
    _site: 'nexus.localhost',
    user_id: 'alice',
    tool_name: 'search_web',
    ...overrides,
  };
}

const later = (n: number, overrides: Partial<PlatformEvent> = {}) =>
  event({
    _uri: `evt-${n}`,
    _seq: n,
    created_at: `2026-07-31T12:0${n}:00Z`,
    _stored_at: `2026-07-31T12:0${n}:00Z`,
    ...overrides,
  });

describe('buildEventGraphModel', () => {
  it('merges shared participants and keeps per-process records apart', () => {
    const model = buildEventGraphModel([later(1), later(2)], emptyFilters(), {
      focusUri: null,
      processCount: 8,
    });
    const alice = model.nodes.filter((node) => node.label === 'alice');
    expect(alice).toHaveLength(1);
    expect(alice[0].processIds).toHaveLength(2);
    // The log record is borne by its own process and is never merged.
    expect(model.nodes.filter((node) => node.bucket === 'GDC' && node.label.startsWith('event-log'))).toHaveLength(2);
  });

  it('offers every event class as a process filter group', () => {
    const model = buildEventGraphModel(
      [later(1), later(2, { _class_uri: 'http://ontology.naas.ai/abi/agent/AgentRouted', routed_to: 'Bob' })],
      emptyFilters(),
      { focusUri: null, processCount: 8 },
    );
    expect(model.processGroups.map((group) => group.label).sort()).toEqual([
      'AgentRouted',
      'AgentToolCalled',
    ]);
  });

  it('drops processes whose type is hidden', () => {
    const filters = { ...emptyFilters(), hiddenProcessTypes: new Set(['AgentToolCalled']) };
    const model = buildEventGraphModel([later(1), later(2)], filters, {
      focusUri: null,
      processCount: 8,
    });
    expect(model.matchedProcessCount).toBe(0);
    expect(model.nodes.filter((node) => node.isProcess)).toHaveLength(0);
  });

  it('drops a single hidden process instance but keeps its siblings', () => {
    const filters = { ...emptyFilters(), hiddenProcessInstances: new Set(['evt-1']) };
    const model = buildEventGraphModel([later(1), later(2)], filters, {
      focusUri: null,
      processCount: 8,
    });
    expect(model.nodes.filter((node) => node.isProcess).map((node) => node.id)).toEqual(['evt-2']);
  });

  it('hides a whole bucket when its class type is unchecked', () => {
    const filters = { ...emptyFilters(), hiddenClassTypes: new Set(['Site']) };
    const model = buildEventGraphModel([later(1)], filters, { focusUri: null, processCount: 8 });
    expect(model.nodes.some((node) => node.bucket === 'Site')).toBe(false);
    // The option list still offers it, so it can be switched back on.
    expect(model.classGroups.some((group) => group.label === 'Site')).toBe(true);
    expect(model.edges.every((edge) => edge.fromId !== 'Site::nexus.localhost')).toBe(true);
  });

  it('keeps only what the temporal slicer admits', () => {
    const filters = { ...emptyFilters(), dateStart: '2026-07-31T12:02:00Z' };
    const model = buildEventGraphModel([later(1), later(2), later(3)], filters, {
      focusUri: null,
      processCount: 8,
    });
    expect(model.matchedProcessCount).toBe(2);
  });

  it('reports the loaded window as the slicer track', () => {
    const model = buildEventGraphModel([later(1), later(3)], emptyFilters(), {
      focusUri: null,
      processCount: 8,
    });
    expect(model.temporalRange?.start).toBe('2026-07-31T12:01:00.000Z');
    expect(model.temporalRange?.end).toBe('2026-07-31T12:03:00.000Z');
  });

  it('caps how many processes are drawn but still reports what matched', () => {
    const model = buildEventGraphModel([later(1), later(2), later(3)], emptyFilters(), {
      focusUri: null,
      processCount: 2,
    });
    expect(model.matchedProcessCount).toBe(3);
    expect(model.nodes.filter((node) => node.isProcess)).toHaveLength(2);
  });

  it('keeps the focus in view even when it falls past the cap', () => {
    const model = buildEventGraphModel([later(1), later(2), later(3)], emptyFilters(), {
      focusUri: 'evt-3',
      processCount: 1,
    });
    expect(model.focusId).toBe('evt-3');
    expect(model.nodes.some((node) => node.id === 'evt-3')).toBe(true);
    expect(model.focusFiltered).toBe(false);
  });

  // Clicking a row in the feed is an explicit "draw this one". Resolving the
  // focus out of the filtered set instead silently re-pointed it at the newest
  // matching process, so the centre stopped being what was clicked.
  it('keeps the clicked process as the focus when a type filter excludes it', () => {
    const filters = emptyFilters();
    filters.hiddenProcessTypes.add('AgentToolCalled');
    const model = buildEventGraphModel([later(1), later(2)], filters, {
      focusUri: 'evt-1',
      processCount: 8,
    });
    expect(model.focusId).toBe('evt-1');
    expect(model.focusFiltered).toBe(true);
  });

  it('keeps the clicked process as the focus when the date slicer excludes it', () => {
    const filters = emptyFilters();
    filters.dateStart = '2026-07-31T12:02:00Z';
    const model = buildEventGraphModel([later(1), later(2)], filters, {
      focusUri: 'evt-1',
      processCount: 8,
    });
    expect(model.focusId).toBe('evt-1');
    expect(model.focusFiltered).toBe(true);
    expect(model.matchedProcessCount).toBe(1);
  });

  it('draws the focus alone rather than nothing when every filter excludes it', () => {
    const filters = emptyFilters();
    filters.dateStart = '2027-01-01T00:00:00Z';
    const model = buildEventGraphModel([later(1), later(2)], filters, {
      focusUri: 'evt-1',
      processCount: 8,
    });
    expect(model.focusId).toBe('evt-1');
    expect(model.nodes.filter((node) => node.isProcess)).toHaveLength(1);
  });

  // The store hands the list newest-first, so the head of the window is the
  // newest event.
  it('falls back to the head of the window only when nothing is selected', () => {
    const model = buildEventGraphModel([later(2), later(1)], emptyFilters(), {
      focusUri: null,
      processCount: 8,
    });
    expect(model.focusId).toBe('evt-2');
    expect(model.focusFiltered).toBe(false);
  });

  it('captions a process with its clock so same-class processes stay apart', () => {
    const model = buildEventGraphModel([later(1), later(2)], emptyFilters(), {
      focusUri: null,
      processCount: 8,
    });
    const captions = model.nodes.filter((node) => node.isProcess).map((node) => node.caption);
    expect(new Set(captions).size).toBe(2);
  });
});

describe('process naming helpers', () => {
  it('labels a process by verb and object', () => {
    expect(processLabel(event())).toBe('CALLED · search_web');
    expect(processTypeLabel(event())).toBe('AgentToolCalled');
  });
});

describe('filterSummary', () => {
  const instances = [
    { id: 'a', label: 'a', type: 'T', bucket: 'Process' as const },
    { id: 'b', label: 'b', type: 'T', bucket: 'Process' as const },
  ];

  it('reads All when nothing is hidden', () => {
    expect(filterSummary(instances, new Set(), new Set())).toBe('All 2');
  });

  it('counts what survives a hidden instance', () => {
    expect(filterSummary(instances, new Set(), new Set(['a']))).toBe('1 of 2');
  });

  it('counts a hidden type against every instance under it', () => {
    expect(filterSummary(instances, new Set(['T']), new Set())).toBe('0 of 2');
  });

  it('says None when there is nothing to filter', () => {
    expect(filterSummary([], new Set(), new Set())).toBe('None');
  });
});

describe('graph params', () => {
  it('applies the per-view defaults from the cockpit config', () => {
    expect(defaultGraphParams('3d').linkDistance).toBe(300);
    expect(defaultGraphParams('2d').zoom).toBe(0.75);
    expect(defaultGraphParams('2d').clusterBy).toBe('bucket');
  });

  it('clamps a stored range back into bounds and drops unknown selects', () => {
    const params = coerceGraphParams('3d', { repulsion: 99999, clusterBy: 'nonsense', legend: 1 });
    expect(params.repulsion).toBe(9000);
    expect(params.clusterBy).toBe('bucket');
    expect(params.legend).toBe(true);
  });

  it('ignores a stored blob that is not an object', () => {
    expect(coerceGraphParams('2d', 'nope')).toEqual(defaultGraphParams('2d'));
  });
});
