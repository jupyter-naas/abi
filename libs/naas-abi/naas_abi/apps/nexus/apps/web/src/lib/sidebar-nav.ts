export const DEFAULT_NAV_ORDER = [
  'apps',
  'lab',
  'files',
  'chat',
  'search',
  'maps',
  'ontology',
  'graph',
  'datasets',
  'slides',
  'code',
  'marketplace',
] as const;

export type NavSectionId = (typeof DEFAULT_NAV_ORDER)[number];

const DRAG_THRESHOLD_PX = 4;

export function dragThresholdPx(): number {
  return DRAG_THRESHOLD_PX;
}

export const LIFT_HOLD_MS = 150;

/**
 * How far item `index` should slide (in slot units) while dragging `from` toward `to`.
 * -1 = toward the hole, 1 = away from the hole, 0 = stay.
 */
export function shiftForReorder(index: number, from: number, to: number): number {
  if (index === from) return 0;
  if (to > from && index > from && index < to) return -1;
  if (to < from && index >= to && index < from) return 1;
  return 0;
}

/**
 * Keep a persisted order, drop unknown ids, append anything new from the catalog.
 */
export function mergeNavOrder(
  persisted: readonly string[] | undefined,
  catalog: readonly NavSectionId[] = DEFAULT_NAV_ORDER,
): NavSectionId[] {
  const allowed = new Set<string>(catalog);
  const seen = new Set<string>();
  const next: NavSectionId[] = [];
  for (const id of persisted ?? []) {
    if (!allowed.has(id) || seen.has(id)) continue;
    seen.add(id);
    next.push(id as NavSectionId);
  }
  for (const id of catalog) {
    if (seen.has(id)) continue;
    next.push(id);
  }
  return next;
}

/**
 * Move `fromId` so it lands at `insertIndex` in the pre-move list.
 * `insertIndex` is the slot among the current items (0..length), measured
 * before removal, matching pointer-over-midpoint hit testing.
 */
export function moveNavItem<T extends string>(
  order: readonly T[],
  fromId: T,
  insertIndex: number,
): T[] {
  const from = order.indexOf(fromId);
  if (from < 0) return [...order];
  const next = order.filter((id) => id !== fromId);
  const adjusted = from < insertIndex ? insertIndex - 1 : insertIndex;
  const clamped = Math.max(0, Math.min(adjusted, next.length));
  next.splice(clamped, 0, fromId);
  return next;
}

/** Slot index from a pointer on the main axis. Origins/sizes are per item, in order. */
export function insertIndexFromPoint(
  origins: readonly number[],
  sizes: readonly number[],
  point: number,
): number {
  for (let i = 0; i < origins.length; i++) {
    if (point < origins[i] + sizes[i] / 2) return i;
  }
  return origins.length;
}
