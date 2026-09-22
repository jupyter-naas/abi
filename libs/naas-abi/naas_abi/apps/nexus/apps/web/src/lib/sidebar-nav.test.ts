import { describe, expect, it } from 'vitest';

import {
  DEFAULT_NAV_ORDER,
  insertIndexFromPoint,
  layoutDockNav,
  mergeNavOrder,
  moveNavItem,
  shiftForReorder,
  type NavSectionId,
} from './sidebar-nav';

describe('mergeNavOrder', () => {
  it('returns the catalog when nothing is persisted', () => {
    expect(mergeNavOrder(undefined)).toEqual([...DEFAULT_NAV_ORDER]);
  });

  it('keeps a custom order and inserts new catalog ids at catalog position', () => {
    const persisted: NavSectionId[] = ['files', 'apps', 'chat'];
    const merged = mergeNavOrder(persisted);
    expect(merged[0]).toBe('home');
    expect(merged.slice(1, 4)).toEqual(['files', 'apps', 'chat']);
    expect(merged).toContain('marketplace');
    expect(merged).not.toContain('lab');
    expect(new Set(merged)).toEqual(new Set(DEFAULT_NAV_ORDER));
  });

  it('drops unknown and duplicate ids, including retired lab', () => {
    const persisted = ['apps', 'apps', 'not-a-section', 'lab'];
    const merged = mergeNavOrder(persisted);
    expect(merged.filter((id) => id === 'apps')).toHaveLength(1);
    expect(merged[0]).toBe('home');
    expect(merged[1]).toBe('apps');
    expect(merged).not.toContain('lab');
  });
});

describe('moveNavItem', () => {
  const order: NavSectionId[] = ['apps', 'slides', 'files'];

  it('moves the first item to the end', () => {
    expect(moveNavItem(order, 'apps', 3)).toEqual(['slides', 'files', 'apps']);
  });

  it('moves the last item to the front', () => {
    expect(moveNavItem(order, 'files', 0)).toEqual(['files', 'apps', 'slides']);
  });

  it('is a no-op when the slot is the item itself', () => {
    expect(moveNavItem(order, 'slides', 1)).toEqual(order);
    expect(moveNavItem(order, 'slides', 2)).toEqual(order);
  });

  it('ignores ids that are not in the list', () => {
    expect(moveNavItem(order, 'chat', 0)).toEqual(order);
  });
});

describe('insertIndexFromPoint', () => {
  const origins = [0, 40, 80];
  const sizes = [40, 40, 40];

  it('hits the first slot before the first midpoint', () => {
    expect(insertIndexFromPoint(origins, sizes, 10)).toBe(0);
  });

  it('hits the next slot after a midpoint', () => {
    expect(insertIndexFromPoint(origins, sizes, 21)).toBe(1);
  });

  it('hits the end past the last midpoint', () => {
    expect(insertIndexFromPoint(origins, sizes, 110)).toBe(3);
  });
});

describe('shiftForReorder', () => {
  it('slides items up when dragging down', () => {
    expect(shiftForReorder(0, 1, 3)).toBe(0);
    expect(shiftForReorder(1, 1, 3)).toBe(0);
    expect(shiftForReorder(2, 1, 3)).toBe(-1);
    expect(shiftForReorder(3, 1, 3)).toBe(0);
  });

  it('slides items down when dragging up', () => {
    expect(shiftForReorder(0, 3, 0)).toBe(1);
    expect(shiftForReorder(1, 3, 0)).toBe(1);
    expect(shiftForReorder(2, 3, 0)).toBe(1);
    expect(shiftForReorder(3, 3, 0)).toBe(0);
  });

  it('does not slide on a no-op drop', () => {
    expect(shiftForReorder(0, 1, 1)).toBe(0);
    expect(shiftForReorder(2, 1, 2)).toBe(0);
  });
});

describe('layoutDockNav', () => {
  const item = 40;
  const pad = 24;
  const count = 13;

  it('keeps the loose gap when every icon fits', () => {
    expect(layoutDockNav(800, count, item, pad)).toEqual({
      gap: 4,
      visibleCount: count,
      overflow: false,
      scroll: false,
    });
  });

  it('packs the gap before hiding any icon', () => {
    // Loose needs 592px. Gap 2 needs 568. Packed needs 544.
    expect(layoutDockNav(570, count, item, pad).gap).toBe(2);
    expect(layoutDockNav(570, count, item, pad).overflow).toBe(false);
    expect(layoutDockNav(550, count, item, pad)).toMatchObject({
      gap: 0,
      visibleCount: count,
      overflow: false,
    });
  });

  it('moves the icons that do not fit into a More slot', () => {
    // 500px holds 11 packed slots. One is More, so 10 stay on the rail.
    expect(layoutDockNav(500, count, item, pad)).toEqual({
      gap: 0,
      visibleCount: 10,
      overflow: true,
      scroll: false,
    });
  });

  it('scrolls full-size icons when the rail is shorter than one button', () => {
    expect(layoutDockNav(50, count, item, pad)).toMatchObject({
      visibleCount: count,
      overflow: false,
      scroll: true,
    });
  });

  it('shows everything before the rail has been measured', () => {
    expect(layoutDockNav(Number.POSITIVE_INFINITY, count, item, pad).visibleCount).toBe(count);
    expect(layoutDockNav(0, 0, item, pad).visibleCount).toBe(0);
  });
});
