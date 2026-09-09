/**
 * Many processes in one graph, filtered the way the Personnel Cockpit filters
 * its own (`GraphPage.js`: process type/instance, class type/instance, date
 * slicer). One event alone has nothing to filter; the feed's loaded window
 * does, and shared participants, sites and tools are what make it a graph
 * rather than a row of stars.
 */

import {
  UNKNOWN,
  buildEventGraphPayload,
  deriveProcessNaming,
  eventTimestamp,
  formatEventClock,
  formatEventDate,
  type BfoBucketType,
  type EventGraphField,
  type EventGraphNode,
  type PlatformEvent,
} from './bfo-event-projection';

export interface ModelNode {
  id: string;
  bucket: BfoBucketType;
  label: string;
  known: boolean;
  fields: EventGraphField[];
  isProcess: boolean;
  /** Filter grouping: the event class for a process, the bucket otherwise. */
  typeLabel: string;
  /** Which processes reference this node. One entry unless the node is shared. */
  processIds: string[];
}

export interface ModelEdge {
  fromId: string;
  toId: string;
  label: string;
  dashed: boolean;
}

export interface FilterInstance {
  id: string;
  label: string;
  type: string;
  bucket: BfoBucketType;
}

export interface FilterGroup {
  label: string;
  bucket: BfoBucketType;
  instances: FilterInstance[];
}

export interface GraphFilters {
  hiddenProcessTypes: Set<string>;
  hiddenProcessInstances: Set<string>;
  hiddenClassTypes: Set<string>;
  hiddenClassInstances: Set<string>;
  /** ISO bounds from the temporal slicer, inclusive. */
  dateStart: string | null;
  dateEnd: string | null;
}

export interface EventGraphModel {
  nodes: ModelNode[];
  edges: ModelEdge[];
  focusId: string | null;
  /** Options for the Processes filter, before process filtering is applied. */
  processGroups: FilterGroup[];
  processInstances: FilterInstance[];
  /** Options for the Classes filter, before class filtering is applied. */
  classGroups: FilterGroup[];
  classInstances: FilterInstance[];
  /** Full temporal extent of the loaded window, for the slicer's track. */
  temporalRange: { start: string; end: string } | null;
  /** Processes matching every filter, before the count cap. */
  matchedProcessCount: number;
}

export function emptyFilters(): GraphFilters {
  return {
    hiddenProcessTypes: new Set(),
    hiddenProcessInstances: new Set(),
    hiddenClassTypes: new Set(),
    hiddenClassInstances: new Set(),
    dateStart: null,
    dateEnd: null,
  };
}

/** Label shown for a process in the feed, the search box and the filter list. */
export function processLabel(event: PlatformEvent): string {
  const naming = deriveProcessNaming(event);
  return naming.object === UNKNOWN ? naming.verb : `${naming.verb} · ${naming.object}`;
}

export function processTypeLabel(event: PlatformEvent): string {
  return deriveProcessNaming(event).className;
}

function nodeKey(event: PlatformEvent, node: EventGraphNode): string {
  return node.shared ? `${node.bucket}::${node.label}` : `${event._uri}::${node.bucket}::${node.label}`;
}

function withinRange(event: PlatformEvent, start: string | null, end: string | null): boolean {
  const at = eventTimestamp(event);
  if (!at) return true;
  const time = new Date(at).getTime();
  if (Number.isNaN(time)) return true;
  if (start && time < new Date(start).getTime()) return false;
  if (end && time > new Date(end).getTime()) return false;
  return true;
}

export function buildEventGraphModel(
  events: PlatformEvent[],
  filters: GraphFilters,
  options: { focusUri: string | null; processCount: number },
): EventGraphModel {
  // --- Processes filter options come from the whole loaded window ---------
  const groupsByType = new Map<string, FilterGroup>();
  const processInstances: FilterInstance[] = [];
  for (const event of events) {
    const type = processTypeLabel(event);
    const instance: FilterInstance = {
      id: event._uri,
      label: processLabel(event),
      type,
      bucket: 'Process',
    };
    processInstances.push(instance);
    const group = groupsByType.get(type) ?? { label: type, bucket: 'Process' as BfoBucketType, instances: [] };
    group.instances.push(instance);
    groupsByType.set(type, group);
  }
  const processGroups = [...groupsByType.values()].sort((a, b) => a.label.localeCompare(b.label));

  const times = events
    .map((event) => eventTimestamp(event))
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value).getTime())
    .filter((value) => !Number.isNaN(value))
    .sort((a, b) => a - b);
  const temporalRange = times.length
    ? { start: new Date(times[0]).toISOString(), end: new Date(times[times.length - 1]).toISOString() }
    : null;

  // --- Narrow to the processes the filters allow --------------------------
  const matched = events.filter(
    (event) =>
      !filters.hiddenProcessTypes.has(processTypeLabel(event)) &&
      !filters.hiddenProcessInstances.has(event._uri) &&
      withinRange(event, filters.dateStart, filters.dateEnd),
  );
  // Keep the focus in view even when it falls past the count cap.
  const capped = matched.slice(0, Math.max(1, options.processCount));
  const focusEvent =
    (options.focusUri && matched.find((event) => event._uri === options.focusUri)) || capped[0] || null;
  const drawn =
    focusEvent && !capped.includes(focusEvent) ? [focusEvent, ...capped.slice(0, -1)] : capped;

  // --- Expand each process into its buckets, sharing what is shared -------
  const nodes = new Map<string, ModelNode>();
  const edges: ModelEdge[] = [];
  const classInstances: FilterInstance[] = [];
  const classGroupsByBucket = new Map<string, FilterGroup>();

  for (const event of drawn) {
    const payload = buildEventGraphPayload(event);
    const processId = event._uri;
    nodes.set(processId, {
      id: processId,
      bucket: 'Process',
      label: payload.process.label,
      known: payload.process.known,
      fields: payload.process.fields,
      isProcess: true,
      typeLabel: payload.naming.className,
      processIds: [processId],
    });

    for (const satellite of payload.satellites) {
      const id = nodeKey(event, satellite);
      const existing = nodes.get(id);
      if (existing) {
        if (!existing.processIds.includes(processId)) existing.processIds.push(processId);
      } else {
        nodes.set(id, {
          id,
          bucket: satellite.bucket,
          label: satellite.label,
          known: satellite.known,
          fields: satellite.fields,
          isProcess: false,
          typeLabel: satellite.bucket,
          processIds: [processId],
        });
        const instance: FilterInstance = {
          id,
          label: satellite.label,
          type: satellite.bucket,
          bucket: satellite.bucket,
        };
        classInstances.push(instance);
        const group =
          classGroupsByBucket.get(satellite.bucket) ??
          { label: satellite.bucket, bucket: satellite.bucket, instances: [] };
        group.instances.push(instance);
        classGroupsByBucket.set(satellite.bucket, group);
      }
      const outward = satellite.direction === 'out';
      edges.push({
        fromId: outward ? processId : id,
        toId: outward ? id : processId,
        label: satellite.predicate,
        dashed: !satellite.known,
      });
    }
  }

  const classGroups = [...classGroupsByBucket.values()];

  // --- Apply the class filter to what was built ---------------------------
  const hiddenNodeIds = new Set<string>();
  for (const node of nodes.values()) {
    if (node.isProcess) continue;
    if (filters.hiddenClassTypes.has(node.typeLabel) || filters.hiddenClassInstances.has(node.id)) {
      hiddenNodeIds.add(node.id);
    }
  }

  return {
    nodes: [...nodes.values()].filter((node) => !hiddenNodeIds.has(node.id)),
    edges: edges.filter((edge) => !hiddenNodeIds.has(edge.fromId) && !hiddenNodeIds.has(edge.toId)),
    focusId: focusEvent?._uri ?? null,
    processGroups,
    processInstances,
    classGroups,
    classInstances,
    temporalRange,
    matchedProcessCount: matched.length,
  };
}

/** "All 12" / "7 of 12" / "None", as the cockpit's filter buttons read. */
export function filterSummary(
  instances: FilterInstance[],
  hiddenTypes: Set<string>,
  hiddenInstances: Set<string>,
): string {
  if (instances.length === 0) return 'None';
  const visible = instances.filter(
    (instance) => !hiddenTypes.has(instance.type) && !hiddenInstances.has(instance.id),
  ).length;
  return visible === instances.length ? `All ${instances.length}` : `${visible} of ${instances.length}`;
}

/** `HH:MM:SS · YYYY-MM-DD` for the slicer's end labels. */
export function formatRangeBound(value: string | null): string {
  if (!value) return UNKNOWN;
  return `${formatEventDate(value)} ${formatEventClock(value)}`;
}
