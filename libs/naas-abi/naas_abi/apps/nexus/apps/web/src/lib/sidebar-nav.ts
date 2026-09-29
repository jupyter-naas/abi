export const DEFAULT_NAV_ORDER = [
  'home',
  'apps',
  'files',
  'chat',
  'search',
  'maps',
  'ontology',
  'graph',
  'datasets',
  'slides',
  'documents',
  'sheets',
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
    const catalogIndex = catalog.indexOf(id);
    next.splice(Math.min(catalogIndex, next.length), 0, id);
    seen.add(id);
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

/** Icon-rail spacing. Loose is the normal gap; smaller steps pack before anything is hidden. */
export const DOCK_NAV_GAPS = [4, 2, 0] as const;

export type DockNavLayout = {
  gap: number;
  /** How many catalog icons stay on the rail. The rest go in the More list. */
  visibleCount: number;
  overflow: boolean;
  /** Rail is shorter than one icon: scroll full-size icons instead of hiding them. */
  scroll: boolean;
};

/**
 * Fit dock icons without shrinking them.
 * Use the loosest gap that fits. If none do, reserve one slot for a More list.
 * If even that button does not fit, scroll the full-size icons.
 */
export function layoutDockNav(
  available: number,
  count: number,
  itemSize: number,
  padding = 24,
): DockNavLayout {
  const showAll = (gap: number): DockNavLayout => ({
    gap,
    visibleCount: count,
    overflow: false,
    scroll: false,
  });
  if (count <= 0) return showAll(DOCK_NAV_GAPS[0]);
  if (!Number.isFinite(available) || available <= 0 || itemSize <= 0) return showAll(DOCK_NAV_GAPS[0]);

  const fits = (gap: number, n: number) => {
    if (n <= 0) return true;
    const used = n * itemSize + (n - 1) * gap + padding;
    return used <= available + 0.5;
  };

  for (const gap of DOCK_NAV_GAPS) {
    if (fits(gap, count)) return showAll(gap);
  }

  for (let visible = count - 1; visible >= 0; visible--) {
    if (fits(DOCK_NAV_GAPS[DOCK_NAV_GAPS.length - 1], visible + 1)) {
      return { gap: 0, visibleCount: visible, overflow: true, scroll: false };
    }
  }

  return { gap: 0, visibleCount: count, overflow: false, scroll: true };
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
