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
