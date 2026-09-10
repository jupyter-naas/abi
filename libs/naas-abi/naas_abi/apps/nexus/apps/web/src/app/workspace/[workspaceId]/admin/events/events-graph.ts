/**
 * Events Graph: one event's JSON tree plus BFO bucket hubs for mapped columns.
 * JSON edges are object keys and array indexes. Hub edges point at the JSON
 * nodes that already fill that table column. Unknown buckets are omitted.
 */

import { BFO_BUCKET_BY_TYPE } from '@/lib/bfo-buckets';
import {
  BFO_COLUMNS,
  BFO_COLUMN_BUCKET_TYPE,
  UNKNOWN,
  projectEventToBfo,
  projectEventToBfoSources,
  type BfoColumnKey,
  type PlatformEvent,
} from './bfo-event-projection';

export const GRAPH_MAX_NODES = 250;

export type EventsGraphKind = 'root' | 'object' | 'array' | 'value' | 'bucket';
export type EventsGraphEdgeKind = 'json' | 'bucket';

export interface EventsGraphNode {
  id: string;
  kind: EventsGraphKind;
  /** Short label for the canvas. */
  label: string;
  /** Full value (or JSON) for hover title / panel. */
  title: string;
  /** JSONPath-like path from the event root (`$`, `$.key`, `$[0]`), or `bucket:<key>`. */
  path: string;
  /** Table column this JSON node supplies, or the hub's own column. */
  bucket: BfoColumnKey | null;
  /** Object key or array index that created this node. Empty on the root and hubs. */
  key: string;
}

export interface EventsGraphEdge {
  id: string;
  source: string;
  target: string;
  /** Object key, `[index]`, or the JSON key a hub maps from. */
  label: string;
  kind: EventsGraphEdgeKind;
}

export function bucketHubId(key: BfoColumnKey): string {
  return `bucket:${key}`;
}

export function bucketHubPath(key: BfoColumnKey): string {
  return bucketHubId(key);
}

/** Short hub name on the canvas. Table columns keep the longer labels. */
export const GRAPH_HUB_LABEL: Record<BfoColumnKey, string> = {
  materialEntity: 'Material',
  process: 'Process',
  site: 'Site',
  ice: 'ICE',
  quality: 'Quality',
  realizable: 'Realizable',
  temporalRegion: 'Temporal',
};

export function shortClassName(uri: string): string {
  const trimmed = uri.trim();
  if (!trimmed) return '';
  return trimmed.split(/[/#]/).filter(Boolean).pop() ?? trimmed;
}

export function bfoColumnSwatch(key: BfoColumnKey): { color: string; border: string } {
  const def = BFO_BUCKET_BY_TYPE[BFO_COLUMN_BUCKET_TYPE[key]];
  return {
    color: def?.color ?? '#6b7280',
    border: def?.border ?? '#4b5563',
  };
}

export interface EventsGraph {
  nodes: EventsGraphNode[];
  edges: EventsGraphEdge[];
  truncated: boolean;
  eventUri: string | null;
  nodeCount: number;
}

export function emptyEventsGraph(): EventsGraph {
  return { nodes: [], edges: [], truncated: false, eventUri: null, nodeCount: 0 };
}

export function jsonChildPath(parent: string, key: string | number): string {
  if (typeof key === 'number') return `${parent}[${key}]`;
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) return `${parent}.${key}`;
  return `${parent}[${JSON.stringify(key)}]`;
}

/** True when `nodePath` is `selectedPath` or an ancestor of it. */
export function pathIsOnTrail(nodePath: string, selectedPath: string | null): boolean {
  if (!selectedPath) return false;
  if (nodePath === selectedPath) return true;
  if (!selectedPath.startsWith(nodePath)) return false;
  const next = selectedPath.charAt(nodePath.length);
  return next === '.' || next === '[';
}

function isUriLike(value: string): boolean {
  return /:\/\//.test(value) || (value.includes('/') && value.length > 24);
}

function isHashLike(value: string): boolean {
  if (/^[a-f0-9]{16,}$/i.test(value)) return true;
  if (/^[0-9a-f]{8}-[0-9a-f-]{19,}$/i.test(value)) return true;
  return false;
}

export function shortJsonLabel(value: unknown): string {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : 'NaN';
  }
  if (typeof value === 'string') {
    if (isHashLike(value)) return `${value.slice(0, 8)}...`;
    if (isUriLike(value)) {
      const last = shortClassName(value) || value;
      return last.length > 32 ? `${last.slice(0, 28)}...` : last;
    }
    return value.length > 32 ? `${value.slice(0, 29)}...` : value;
  }
  if (Array.isArray(value)) return `[${value.length}]`;
  if (typeof value === 'object') return `{${Object.keys(value as object).length}}`;
  return String(value);
}

function titleOf(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean' || value === null) {
    return String(value);
  }
  try {
    const text = JSON.stringify(value);
    return text.length > 400 ? `${text.slice(0, 397)}...` : text;
  } catch {
    return shortJsonLabel(value);
  }
}

function kindOf(value: unknown, isRoot: boolean): EventsGraphKind {
  if (isRoot) return 'root';
  if (Array.isArray(value)) return 'array';
  if (value !== null && typeof value === 'object') return 'object';
  return 'value';
}

function rootLabel(event: PlatformEvent): string {
  const classUri = typeof event._class_uri === 'string' ? event._class_uri.trim() : '';
  if (classUri) return shortClassName(classUri) || 'event';
  if (typeof event._uri === 'string' && event._uri.trim()) return shortClassName(event._uri) || 'event';
  return 'event';
}

function nodeLabel(kind: EventsGraphKind, value: unknown, keyHint: string, event: PlatformEvent): string {
  if (kind === 'root') return rootLabel(event);
  if (kind === 'object' || kind === 'array') {
    const hint = keyHint.trim();
    return hint || shortJsonLabel(value);
  }
  return shortJsonLabel(value);
}

export function buildEventJsonGraph(
  event: PlatformEvent | null | undefined,
  { maxNodes = GRAPH_MAX_NODES }: { maxNodes?: number } = {},
): EventsGraph {
  if (!event) return emptyEventsGraph();

  const nodes: EventsGraphNode[] = [];
  const edges: EventsGraphEdge[] = [];
  let truncated = false;

  const queue: Array<{
    parentId: string | null;
    edgeLabel: string | null;
    value: unknown;
    path: string;
    keyHint: string;
  }> = [{ parentId: null, edgeLabel: null, value: event, path: '$', keyHint: '' }];

  while (queue.length) {
    const item = queue.shift();
    if (!item) break;
    if (nodes.length >= maxNodes) {
      truncated = true;
      break;
    }

    const isRoot = item.path === '$';
    const kind = kindOf(item.value, isRoot);
    const node: EventsGraphNode = {
      id: item.path,
      kind,
      label: nodeLabel(kind, item.value, item.keyHint, event),
      title: isRoot
        ? (typeof event._uri === 'string' && event._uri.trim() ? event._uri : titleOf(item.value))
        : titleOf(item.value),
      path: item.path,
      bucket: null,
      key: item.keyHint,
    };
    nodes.push(node);

    if (item.parentId && item.edgeLabel != null) {
      edges.push({
        id: `${item.parentId}->${item.path}`,
        source: item.parentId,
        target: item.path,
        label: item.edgeLabel,
        kind: 'json',
      });
    }

    if (item.value === null || typeof item.value !== 'object') continue;

    if (Array.isArray(item.value)) {
      item.value.forEach((child, index) => {
        if (child === undefined || child === null) return;
        queue.push({
          parentId: item.path,
          edgeLabel: `[${index}]`,
          value: child,
          path: jsonChildPath(item.path, index),
          keyHint: `[${index}]`,
        });
      });
      continue;
    }

    for (const [key, child] of Object.entries(item.value as Record<string, unknown>)) {
      if (child === undefined || child === null) continue;
      queue.push({
        parentId: item.path,
        edgeLabel: key,
        value: child,
        path: jsonChildPath(item.path, key),
        keyHint: key,
      });
    }
  }

  attachBucketHubs(event, nodes, edges);

  return {
    nodes,
    edges,
    truncated,
    eventUri: typeof event._uri === 'string' ? event._uri : null,
    nodeCount: nodes.length,
  };
}

function attachBucketHubs(
  event: PlatformEvent,
  nodes: EventsGraphNode[],
  edges: EventsGraphEdge[],
): void {
  const buckets = projectEventToBfo(event);
  const sources = projectEventToBfoSources(event);
  const byPath = new Map(nodes.map((node) => [node.path, node]));

  for (const col of BFO_COLUMNS) {
    const value = buckets[col.key];
    if (!value || value === UNKNOWN) continue;
    const keys = sources[col.key];
    if (!keys?.length) continue;

    const targets: Array<{ node: EventsGraphNode; key: string }> = [];
    for (const key of keys) {
      const path = jsonChildPath('$', key);
      const node = byPath.get(path);
      if (!node) continue;
      node.bucket = col.key;
      targets.push({ node, key });
    }
    if (!targets.length) continue;

    const hubId = bucketHubId(col.key);
    const hub: EventsGraphNode = {
      id: hubId,
      kind: 'bucket',
      label: GRAPH_HUB_LABEL[col.key],
      title: value,
      path: bucketHubPath(col.key),
      bucket: col.key,
      key: '',
    };
    nodes.push(hub);
    byPath.set(hub.path, hub);

    for (const target of targets) {
      edges.push({
        id: `${hubId}->${target.node.path}`,
        source: hubId,
        target: target.node.path,
        label: target.key,
        kind: 'bucket',
      });
    }
  }
}

/** Resolve which event the graph should show. */
export function eventForGraph(
  events: PlatformEvent[],
  selectedUri: string | null,
): PlatformEvent | null {
  if (selectedUri) {
    const match = events.find((event) => event._uri === selectedUri);
    if (match) return match;
  }
  return events[0] ?? null;
}
