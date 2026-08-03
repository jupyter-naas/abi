import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type GulfRegion = {
  id: string;
  label: string;
  lat: number;
  lng: number;
  keys: string[];
};

/**
 * Dense Gulf / Iran / Israel theater geocodes for strike headlines.
 * Maps-owned; does not import WSR. Prefer specific sites before country defaults.
 */
const GULF_REGIONS: GulfRegion[] = [
  { id: 'natanz', label: 'Natanz', lat: 33.724, lng: 51.727, keys: ['natanz'] },
  { id: 'fordow', label: 'Fordow', lat: 34.884, lng: 50.997, keys: ['fordow', 'fordu'] },
  { id: 'isfahan', label: 'Isfahan', lat: 32.607, lng: 51.649, keys: ['isfahan', 'esfahan'] },
  { id: 'bushehr', label: 'Bushehr', lat: 28.829, lng: 50.888, keys: ['bushehr'] },
  { id: 'bandar-abbas', label: 'Bandar Abbas', lat: 27.186, lng: 56.28, keys: ['bandar abbas', 'bandar-abbas'] },
  { id: 'tehran', label: 'Tehran', lat: 35.689, lng: 51.389, keys: ['tehran'] },
  { id: 'shiraz', label: 'Shiraz', lat: 29.592, lng: 52.584, keys: ['shiraz'] },
  { id: 'tabriz', label: 'Tabriz', lat: 38.08, lng: 46.291, keys: ['tabriz'] },
  { id: 'kharg', label: 'Kharg Island', lat: 29.25, lng: 50.32, keys: ['kharg'] },
  { id: 'hormuz', label: 'Strait of Hormuz', lat: 26.594, lng: 56.451, keys: ['hormuz', 'strait of hormuz'] },
  { id: 'tel-aviv', label: 'Tel Aviv', lat: 32.085, lng: 34.782, keys: ['tel aviv', 'tel-aviv', 'kirya'] },
  { id: 'haifa', label: 'Haifa', lat: 32.794, lng: 34.99, keys: ['haifa'] },
  { id: 'jerusalem', label: 'Jerusalem', lat: 31.768, lng: 35.213, keys: ['jerusalem'] },
  { id: 'dimona', label: 'Dimona', lat: 30.973, lng: 35.143, keys: ['dimona'] },
  { id: 'nevatim', label: 'Nevatim', lat: 31.208, lng: 35.012, keys: ['nevatim'] },
  { id: 'dubai', label: 'Dubai', lat: 25.204, lng: 55.271, keys: ['dubai'] },
  { id: 'abu-dhabi', label: 'Abu Dhabi', lat: 24.453, lng: 54.377, keys: ['abu dhabi', 'abu-dhabi'] },
  { id: 'dhafra', label: 'Al Dhafra', lat: 24.248, lng: 54.548, keys: ['al dhafra', 'dhafra'] },
  { id: 'jebel-ali', label: 'Jebel Ali', lat: 25.01, lng: 55.06, keys: ['jebel ali'] },
  { id: 'doha', label: 'Doha / Al Udeid', lat: 25.117, lng: 51.314, keys: ['doha', 'al udeid', 'udeid', 'qatar'] },
  { id: 'kuwait', label: 'Kuwait', lat: 29.347, lng: 47.521, keys: ['kuwait', 'ali al salem', 'camp arifjan', 'buehring'] },
  { id: 'bahrain', label: 'Bahrain', lat: 26.228, lng: 50.586, keys: ['bahrain', 'manama', 'fifth fleet', '5th fleet'] },
  { id: 'riyadh', label: 'Riyadh', lat: 24.713, lng: 46.675, keys: ['riyadh', 'saudi arabia', 'saudi'] },
  { id: 'jeddah', label: 'Jeddah / Red Sea', lat: 21.485, lng: 39.192, keys: ['jeddah', 'red sea'] },
  { id: 'sanaa', label: 'Yemen / Houthi', lat: 15.369, lng: 44.191, keys: ['yemen', 'houthi', 'sanaa', "sana'a", 'houthis'] },
  { id: 'beirut', label: 'Beirut', lat: 33.888, lng: 35.495, keys: ['beirut', 'lebanon', 'hezbollah'] },
  { id: 'damascus', label: 'Damascus', lat: 33.51, lng: 36.291, keys: ['damascus', 'syria'] },
  { id: 'baghdad', label: 'Baghdad', lat: 33.338, lng: 44.394, keys: ['baghdad', 'iraq'] },
  { id: 'amman', label: 'Amman', lat: 31.953, lng: 35.91, keys: ['amman', 'jordan'] },
  { id: 'muscat', label: 'Muscat / Oman', lat: 23.588, lng: 58.382, keys: ['muscat', 'oman'] },
  { id: 'gulf', label: 'Persian Gulf', lat: 26.5, lng: 52.0, keys: ['persian gulf', 'arabian gulf', 'gulf'] },
  { id: 'iran', label: 'Iran', lat: 32.4, lng: 53.7, keys: ['iran', 'iranian', 'irgc'] },
  { id: 'israel', label: 'Israel', lat: 31.5, lng: 34.75, keys: ['israel', 'israeli', 'idf', 'iron dome'] },
  { id: 'uae', label: 'UAE', lat: 24.3, lng: 54.5, keys: ['uae', 'united arab emirates', 'emirates'] },
];

/** Headline must look like a military strike / aerial attack event. */
const STRIKE_KEYS = [
  'missile',
  'ballistic',
  'cruise missile',
  'drone',
  'shahed',
  'airstrike',
  'air strike',
  'air-strike',
  'struck',
  'strikes',
  'strike on',
  'strike hits',
  'rocket',
  'barrage',
  'explosion',
  'explosions',
  'intercept',
  'interception',
  'air defense',
  'air defence',
  'bunker',
  'bomber',
  'fighter jet',
  'centcom',
  'irgc',
  'hezbollah rocket',
  'houthi',
  'warship',
  'carrier',
  'naval strike',
  'drone attack',
  'missile attack',
];

const FEEDS: Array<{ url: string; source: string }> = [
  { url: 'http://feeds.bbci.co.uk/news/world/middle_east/rss.xml', source: 'BBC' },
  { url: 'http://feeds.bbci.co.uk/news/world/rss.xml', source: 'BBC World' },
  { url: 'https://www.aljazeera.com/xml/rss/all.xml', source: 'Al Jazeera' },
  { url: 'https://feeds.reuters.com/reuters/worldNews', source: 'Reuters' },
];

const ITEM_RE = /<item>([\s\S]*?)<\/item>/gi;
const TITLE_RE = /<title>([\s\S]*?)<\/title>/i;
const LINK_RE = /<link>([\s\S]*?)<\/link>/i;
const DESC_RE = /<description>([\s\S]*?)<\/description>/i;
const CDATA_RE = /<!\[CDATA\[([\s\S]*?)\]\]>/;

function stripTags(value: string): string {
  const cdata = CDATA_RE.exec(value);
  const raw = cdata ? cdata[1] : value;
  return raw.replace(/<[^>]+>/g, '').trim();
}

function isStrikeHeadline(text: string): boolean {
  const lower = text.toLowerCase();
  return STRIKE_KEYS.some((k) => lower.includes(k));
}

function matchRegion(text: string): GulfRegion | null {
  const lower = text.toLowerCase();
  for (const region of GULF_REGIONS) {
    if (region.keys.some((k) => lower.includes(k))) return region;
  }
  return null;
}

function pinColor(text: string): string {
  const lower = text.toLowerCase();
  if (/(ballistic|bunker|nuclear|mass casualt|killed|dead)/i.test(lower)) {
    return '#dc2626';
  }
  if (/(missile|airstrike|air strike|explosion|barrage|rocket)/i.test(lower)) {
    return '#ea580c';
  }
  return '#ca8a04';
}

async function parseFeed(
  url: string,
  source: string,
): Promise<
  Array<{
    id: string;
    title: string;
    source: string;
    url: string;
    region: GulfRegion;
    color: string;
  }>
> {
  try {
    const res = await mapsUpstreamGet(url, { timeoutMs: 12000 });
    if (!res.ok) return [];
    const xml = await res.text();
    const items: Array<{
      id: string;
      title: string;
      source: string;
      url: string;
      region: GulfRegion;
      color: string;
    }> = [];
    let match: RegExpExecArray | null;
    const re = new RegExp(ITEM_RE);
    while ((match = re.exec(xml)) !== null && items.length < 50) {
      const block = match[1];
      const title = stripTags(TITLE_RE.exec(block)?.[1] ?? '');
      if (!title) continue;
      const desc = stripTags(DESC_RE.exec(block)?.[1] ?? '');
      const haystack = `${title} ${desc}`;
      if (!isStrikeHeadline(haystack)) continue;
      const region = matchRegion(haystack);
      if (!region) continue;
      const link = stripTags(LINK_RE.exec(block)?.[1] ?? '');
      items.push({
        id: `${source}-${region.id}-${items.length}-${title.slice(0, 24)}`,
        title,
        source,
        url: link,
        region,
        color: pinColor(haystack),
      });
    }
    return items;
  } catch {
    return [];
  }
}

/** RSS proxy → Gulf/Iran/Israel strike geopin layer for the Maps canvas. */
export async function GET() {
  try {
    const batches = await Promise.all(
      FEEDS.map((f) => parseFeed(f.url, f.source)),
    );
    const seen = new Set<string>();
    const items = batches
      .flat()
      .filter((item) => {
        const key = item.title.toLowerCase().replace(/\s+/g, ' ').slice(0, 120);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 80);

    const regionCounts = new Map<string, number>();
    const pins = items.map((item) => {
      const n = regionCounts.get(item.region.id) ?? 0;
      regionCounts.set(item.region.id, n + 1);
      const jitterLat = ((n % 5) - 2) * 0.22;
      const jitterLng = (Math.floor(n / 5) - 1) * 0.28;
      return {
        id: item.id,
        lat: item.region.lat + jitterLat,
        lng: item.region.lng + jitterLng,
        label: item.title.slice(0, 140),
        detail: `${item.source} · ${item.region.label}`,
        color: item.color,
        size: 9,
        href: item.url || undefined,
      };
    });

    return mapsJson({
      pins,
      count: pins.length,
      empty: pins.length === 0,
      source: 'BBC / Al Jazeera / Reuters RSS (Gulf strike filter)',
      theater: 'Persian Gulf / Iran / Israel',
    });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'Gulf strikes fetch failed',
        pins: [],
        count: 0,
        empty: true,
      },
      { status: 502 },
    );
  }
}
