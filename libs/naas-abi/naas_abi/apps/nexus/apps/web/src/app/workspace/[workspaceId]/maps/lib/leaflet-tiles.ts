// Standard OpenStreetMap tiles support interactive viewing without an API key.
// Use their normal browser caching and keep attribution visible.
export const MAPS_TILE_LIGHT = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
// Dark workspaces recolor only the maps-basemap tile layer in Maps CSS.
// Theme changes reuse these key-free tiles and preserve data overlay colors.
export const MAPS_TILE_DARK = MAPS_TILE_LIGHT;
export const MAPS_TILE_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export function isMapsDarkMode(): boolean {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}
