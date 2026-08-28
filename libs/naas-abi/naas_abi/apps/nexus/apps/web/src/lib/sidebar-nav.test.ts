import { describe, expect, it } from 'vitest';

import {
  DEFAULT_NAV_ORDER,
  insertIndexFromPoint,
  mergeNavOrder,
  moveNavItem,
  shiftForReorder,
  type NavSectionId,
} from './sidebar-nav';

describe('mergeNavOrder', () => {
  it('returns the catalog when nothing is persisted', () => {
    expect(mergeNavOrder(undefined)).toEqual([...DEFAULT_NAV_ORDER]);
  });

  it('keeps a custom order and appends new catalog ids', () => {
    const persisted: NavSectionId[] = ['files', 'apps', 'lab', 'chat'];
    const merged = mergeNavOrder(persisted);
    expect(merged.slice(0, 4)).toEqual(['files', 'apps', 'lab', 'chat']);
    expect(merged).toContain('marketplace');
    expect(new Set(merged)).toEqual(new Set(DEFAULT_NAV_ORDER));
  });

  it('drops unknown and duplicate ids', () => {
    const persisted = ['apps', 'apps', 'not-a-section', 'lab'];
    const merged = mergeNavOrder(persisted);
    expect(merged.filter((id) => id === 'apps')).toHaveLength(1);
    expect(merged[0]).toBe('apps');
    expect(merged[1]).toBe('lab');
  });
});

describe('moveNavItem', () => {
  const order: NavSectionId[] = ['apps', 'lab', 'files'];

  it('moves the first item to the end', () => {
    expect(moveNavItem(order, 'apps', 3)).toEqual(['lab', 'files', 'apps']);
  });

  it('moves the last item to the front', () => {
    expect(moveNavItem(order, 'files', 0)).toEqual(['files', 'apps', 'lab']);
  });

  it('is a no-op when the slot is the item itself', () => {
    expect(moveNavItem(order, 'lab', 1)).toEqual(order);
    expect(moveNavItem(order, 'lab', 2)).toEqual(order);
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
