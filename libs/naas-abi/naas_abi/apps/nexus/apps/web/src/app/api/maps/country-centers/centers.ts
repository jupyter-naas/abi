/** One country: English name, its other names (own names first), label point, continent. */
export interface CountryCenterRow {
  name: string;
  names: string[];
  lat: number;
  lng: number;
  continent: string | null;
}

// Own names, then the ~25 translations, then codes. Never SOVEREIGNT / GEOUNIT:
// "Fr. S. Antarctic Lands" is sovereign France and would steal France's name.
const PRIMARY = ['NAME', 'NAME_LONG', 'ADMIN', 'NAME_EN', 'NAME_SORT', 'NAME_ALT', 'NAME_CIAWF', 'FORMAL_EN'];
const CODES = ['ISO_A2', 'ISO_A2_EH', 'ISO_A3', 'ISO_A3_EH'];
const TRANSLATION = /^NAME_[A-Z]{2,3}$/;

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() && value !== '-99' ? value.trim() : null;
}

export function compactCountryCenters(collection: unknown): CountryCenterRow[] {
  const features = (collection as { features?: unknown[] })?.features;
  if (!Array.isArray(features)) return [];
  const rows: CountryCenterRow[] = [];
  for (const feature of features) {
    const props = ((feature as { properties?: Record<string, unknown> })?.properties ?? {});
    const name = text(props.NAME);
    const lng = Number(props.LABEL_X);
    const lat = Number(props.LABEL_Y);
    if (!name || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const names: string[] = [];
    const add = (value: unknown) => {
      const v = text(value);
      if (v && !names.includes(v)) names.push(v);
    };
    PRIMARY.forEach((key) => add(props[key]));
    Object.keys(props).filter((key) => TRANSLATION.test(key) && !PRIMARY.includes(key)).sort().forEach((key) => add(props[key]));
    CODES.forEach((key) => add(props[key]));
    const continent = text(props.CONTINENT);
    rows.push({ name, names, lat, lng, continent: continent && !continent.startsWith('Seven seas') ? continent : null });
  }
  return rows;
}
