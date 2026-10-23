const LAYER_COLOR_PALETTE = [
  '#2563eb',
  '#dc2626',
  '#059669',
  '#7c3aed',
  '#ea580c',
  '#0891b2',
  '#ca8a04',
  '#db2777',
  '#4f46e5',
  '#0d9488',
] as const;

/** Stable pin / legend colors for built-in public feeds on the combined map. */
const BUILTIN_LAYER_COLORS: Record<string, string> = {
  earthquakes: '#ea580c',
  wildfires: '#dc2626',
  temperature: '#2563eb',
  gdacs: '#b91c1c',
  'eonet-all': '#7c3aed',
  openaq: '#64748b',
  'nws-alerts': '#f59e0b',
  'tropical-storms': '#2563eb',
  volcanoes: '#7c3aed',
  flights: '#0ea5e9',
  conflict: '#dc2626',
  'gulf-strikes': '#991b1b',
  news: '#6366f1',
  ais: '#0284c7',
  iss: '#22c55e',
};

function hashLayerColor(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i += 1) {
    h = (Math.imul(31, h) + id.charCodeAt(i)) | 0;
  }
  return LAYER_COLOR_PALETTE[Math.abs(h) % LAYER_COLOR_PALETTE.length] ?? LAYER_COLOR_PALETTE[0];
}

function isHexColor(value: string | undefined): value is string {
  return typeof value === 'string' && /^#[0-9a-f]{3,8}$/i.test(value);
}

/** Color used for pins and the All layers legend swatch. */
export function layerPinColor(entry: { id: string; color?: string }): string {
  if (isHexColor(entry.color)) return entry.color;
  return BUILTIN_LAYER_COLORS[entry.id] ?? hashLayerColor(entry.id);
}

/** One hex when every pin that has a color shares it. */
export function sharedPinColor(pins: readonly { color?: string }[]): string | undefined {
  const hexes = pins.map((pin) => pin.color).filter(isHexColor);
  if (!hexes.length) return undefined;
  const first = hexes[0];
  return hexes.every((color) => color.toLowerCase() === first.toLowerCase()) ? first : undefined;
}

/**
 * Paint color for dots and clusters: the layer hex (catalog or Settings), else
 * a shared pin hex, else the built-in / hash fallback.
 */
export function layerPaintColor(
  entry: { id: string; color?: string },
  pins: readonly { color?: string }[] = [],
): string {
  if (isHexColor(entry.color)) return entry.color;
  return sharedPinColor(pins) ?? layerPinColor(entry);
}
