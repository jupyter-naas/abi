import { describe, expect, it } from 'vitest';

import {
  clampDockWidth,
  clampFeatureColumnWidth,
  DOCK_WIDTH_DEFAULT,
  DOCK_WIDTH_MAX,
  DOCK_WIDTH_MIN,
  dockShowsLabels,
  FEATURE_COLUMN_WIDTH_DEFAULT,
} from './shell-columns';

describe('clampDockWidth', () => {
  it('defaults sit at the same width as the feature column', () => {
    expect(DOCK_WIDTH_DEFAULT).toBe(FEATURE_COLUMN_WIDTH_DEFAULT);
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

  it('shows labels at the default width', () => {
    expect(dockShowsLabels(DOCK_WIDTH_DEFAULT)).toBe(true);
  });
});

describe('clampFeatureColumnWidth', () => {
  it('keeps the column between 200 and 480', () => {
    expect(clampFeatureColumnWidth(50)).toBe(200);
    expect(clampFeatureColumnWidth(800)).toBe(480);
  });
});
