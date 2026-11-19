import snapshot from './abi-architecture.json';

export const architecture = snapshot;
export type Component = (typeof snapshot.components)[number];
export type Layer = (typeof snapshot.layers)[number];
export const PLANE_WIDTH = 12;
export const PLANE_DEPTH = 11;

/** Fits both plane dimensions; aspect changes must never crop the focused layer. */
export function focusDistance(width: number, height: number, expanded: boolean) {
  const aspect = Math.max(1, width) / Math.max(1, height);
  const scale = expanded ? 1.2 : 1;
  return Math.max(PLANE_DEPTH, PLANE_WIDTH / aspect) * scale / (2 * Math.tan(Math.PI / 9)) * 1.18 + 1;
}
export function componentPosition(index: number, count: number, expanded: boolean) {
  const columns = 3;
  const rows = Math.ceil(count / columns);
  const spread = expanded ? 1.2 : 1;
  return { x: ((index % columns) - 1) * 3.7 * spread, z: (Math.floor(index / columns) - (rows - 1) / 2) * 1.8 * spread };
}
