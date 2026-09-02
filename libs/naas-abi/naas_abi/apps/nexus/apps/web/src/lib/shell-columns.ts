/** Shared widths for the dock (icon nav) and the feature column. */

export const FEATURE_COLUMN_WIDTH_DEFAULT = 256;
export const FEATURE_COLUMN_WIDTH_MIN = 200;
export const FEATURE_COLUMN_WIDTH_MAX = 480;

export const DOCK_WIDTH_DEFAULT = FEATURE_COLUMN_WIDTH_DEFAULT;
export const DOCK_WIDTH_MIN = 56;
export const DOCK_WIDTH_MAX = FEATURE_COLUMN_WIDTH_MAX;
/** Below this, the dock is icon-only. At or above, labels show. */
export const DOCK_LABELS_MIN_WIDTH = 140;

export function clampFeatureColumnWidth(width: number): number {
  return Math.max(FEATURE_COLUMN_WIDTH_MIN, Math.min(FEATURE_COLUMN_WIDTH_MAX, Math.round(width)));
}

export function clampDockWidth(width: number): number {
  return Math.max(DOCK_WIDTH_MIN, Math.min(DOCK_WIDTH_MAX, Math.round(width)));
}

export function dockShowsLabels(width: number): boolean {
  return width >= DOCK_LABELS_MIN_WIDTH;
}
