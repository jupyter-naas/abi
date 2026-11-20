import { describe, expect, it } from 'vitest';

import {
  clampDockWidth,
  clampFeatureColumnWidth,
  DOCK_WIDTH_DEFAULT,
  DOCK_WIDTH_MAX,
  DOCK_LABELS_MIN_WIDTH,
  DOCK_WIDTH_MIN,
  FEATURE_COLUMN_WIDTH_DEFAULT,
  dockShowsLabels,
  toggleDockWidth,
} from './shell-columns';

describe('clampDockWidth', () => {
  it('defaults to the icon-only floor', () => {
    expect(DOCK_WIDTH_DEFAULT).toBe(DOCK_WIDTH_MIN);
  });

  it('clamps to the icon-only floor and the shared ceiling', () => {
    expect(clampDockWidth(10)).toBe(DOCK_WIDTH_MIN);
    expect(clampDockWidth(900)).toBe(DOCK_WIDTH_MAX);
    expect(clampDockWidth(256.4)).toBe(256);
  });
});

describe('dockShowsLabels', () => {
  it('hides labels on a narrow icon dock', () => {
    expect(dockShowsLabels(DOCK_WIDTH_MIN)).toBe(false);
  });

  it('hides labels at the default (collapsed) width', () => {
    expect(dockShowsLabels(DOCK_WIDTH_DEFAULT)).toBe(false);
  });
});

describe('toggleDockWidth', () => {
  it('snaps a collapsed dock to the feature column width', () => {
    expect(toggleDockWidth(DOCK_WIDTH_MIN)).toBe(FEATURE_COLUMN_WIDTH_DEFAULT);
    expect(dockShowsLabels(toggleDockWidth(DOCK_WIDTH_MIN))).toBe(true);
  });

  it('snaps a labeled dock back to logos only', () => {
    expect(toggleDockWidth(DOCK_LABELS_MIN_WIDTH)).toBe(DOCK_WIDTH_MIN);
    expect(dockShowsLabels(toggleDockWidth(DOCK_LABELS_MIN_WIDTH))).toBe(false);
  });

  it('collapses a wider dock to logos, then returns to the feature column width', () => {
    expect(toggleDockWidth(DOCK_WIDTH_MAX)).toBe(DOCK_WIDTH_MIN);
    expect(toggleDockWidth(toggleDockWidth(DOCK_WIDTH_MAX))).toBe(FEATURE_COLUMN_WIDTH_DEFAULT);
  });
});

describe('clampFeatureColumnWidth', () => {
  it('keeps the column between 200 and 480', () => {
    expect(clampFeatureColumnWidth(50)).toBe(200);
    expect(clampFeatureColumnWidth(800)).toBe(480);
  });
});
