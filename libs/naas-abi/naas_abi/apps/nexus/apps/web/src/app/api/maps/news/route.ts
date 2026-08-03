import { mapsJson, mapsUpstreamGet } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type NewsRegion = {
  id: string;
  label: string;
  lat: number;
  lng: number;
  keys: string[];
};

/** Light keyword → region geocode for RSS map pins (Maps-owned, not WSR). */
const NEWS_REGIONS: NewsRegion[] = [
  { id: 'us', label: 'United States', lat: 38.9, lng: -77.0, keys: ['united states', 'washington', 'white house', 'u.s.', 'usa'] },
  { id: 'ukraine', label: 'Ukraine', lat: 50.45, lng: 30.52, keys: ['ukraine', 'kyiv', 'kiev', 'zelensky'] },
  { id: 'russia', label: 'Russia', lat: 55.75, lng: 37.62, keys: ['russia', 'moscow', 'kremlin', 'putin'] },
  { id: 'israel', label: 'Israel / Gaza', lat: 31.5, lng: 34.75, keys: ['israel', 'israeli', 'gaza', 'hamas', 'tel aviv', 'jerusalem'] },
  { id: 'iran', label: 'Iran', lat: 35.7, lng: 51.4, keys: ['iran', 'iranian', 'tehran', 'irgc'] },
  { id: 'lebanon', label: 'Lebanon', lat: 33.89, lng: 35.5, keys: ['lebanon', 'beirut', 'hezbollah'] },
  { id: 'syria', label: 'Syria', lat: 33.51, lng: 36.29, keys: ['syria', 'damascus'] },
  { id: 'iraq', label: 'Iraq', lat: 33.34, lng: 44.39, keys: ['iraq', 'baghdad'] },
  { id: 'china', label: 'China / Taiwan', lat: 31.2, lng: 121.5, keys: ['china', 'chinese', 'beijing', 'taiwan', 'taiwanese'] },
  { id: 'korea', label: 'Korean Peninsula', lat: 37.57, lng: 126.98, keys: ['north korea', 'south korea', 'seoul', 'pyongyang', 'kim jong'] },
  { id: 'india', label: 'India', lat: 28.61, lng: 77.21, keys: ['india', 'indian', 'delhi', 'mumbai'] },
  { id: 'africa', label: 'Africa', lat: 6.5, lng: 3.4, keys: ['africa', 'sudan', 'sahel', 'nigeria', 'ethiopia', 'congo'] },
  { id: 'eu', label: 'Europe', lat: 50.11, lng: 8.68, keys: ['europe', 'eu ', 'nato', 'brussels', 'france', 'germany', 'uk ', 'britain'] },
  { id: 'latam', label: 'Latin America', lat: -15.8, lng: -47.9, keys: ['brazil', 'mexico', 'venezuela', 'argentina', 'latin america'] },
  { id: 'me', label: 'Middle East', lat: 29.3, lng: 47.5, keys: ['middle east', 'saudi', 'yemen', 'qatar', 'persian gulf', 'hormuz'] },
];

const FEEDS: Array<{ url: string; source: string }> = [
  { url: 'http://feeds.bbci.co.uk/news/world/rss.xml', source: 'BBC' },
  { url: 'https://www.aljazeera.com/xml/rss/all.xml', source: 'Al Jazeera' },
  { url: 'https://feeds.reuters.com/reuters/worldNews', source: 'Reuters' },
];

const ITEM_RE = /<item>([\s\S]*?)<\/item>/gi;
const TITLE_RE = /<title>([\s\S]*?)<\/title>/i;
const LINK_RE = /<link>([\s\S]*?)<\/link>/i;
const CDATA_RE = /<!\[CDATA\[([\s\S]*?)\]\]>/;

function stripTags(value: string): string {
  const cdata = CDATA_RE.exec(value);
  const raw = cdata ? cdata[1] : value;
  return raw.replace(/<[^>]+>/g, '').trim();
}

function matchRegion(title: string): NewsRegion | null {
  const lower = title.toLowerCase();
  for (const region of NEWS_REGIONS) {
    if (region.keys.some((k) => lower.includes(k))) return region;
  }
  return null;
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
    region: NewsRegion;
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
      region: NewsRegion;
    }> = [];
    let match: RegExpExecArray | null;
    const re = new RegExp(ITEM_RE);
    while ((match = re.exec(xml)) !== null && items.length < 40) {
      const block = match[1];
      const titleRaw = TITLE_RE.exec(block)?.[1] ?? '';
      const title = stripTags(titleRaw);
      if (!title) continue;
      const region = matchRegion(title);
      if (!region) continue;
      const link = stripTags(LINK_RE.exec(block)?.[1] ?? '');
      items.push({
        id: `${source}-${region.id}-${items.length}-${title.slice(0, 24)}`,
        title,
        source,
        url: link,
        region,
      });
    }
    return items;
  } catch {
    return [];
  }
}

/** RSS proxy → region-geocoded news pins for the Maps canvas. */
export async function GET() {
  try {
    const batches = await Promise.all(
      FEEDS.map((f) => parseFeed(f.url, f.source)),
    );
    const items = batches.flat().slice(0, 80);

    // Jitter pins slightly so multiple stories in one region don't stack exactly.
    const regionCounts = new Map<string, number>();
    const pins = items.map((item) => {
      const n = regionCounts.get(item.region.id) ?? 0;
      regionCounts.set(item.region.id, n + 1);
      const jitterLat = ((n % 5) - 2) * 0.35;
      const jitterLng = (Math.floor(n / 5) - 1) * 0.45;
      return {
        id: item.id,
        lat: item.region.lat + jitterLat,
        lng: item.region.lng + jitterLng,
        label: item.title.slice(0, 120),
        detail: `${item.source} · ${item.region.label}`,
        color: '#0f766e',
        size: 8,
        href: item.url || undefined,
      };
    });

    return mapsJson({
      pins,
      count: pins.length,
      empty: pins.length === 0,
      source: 'BBC / Al Jazeera / Reuters RSS',
    });
  } catch (err) {
    return mapsJson(
      {
        error: err instanceof Error ? err.message : 'News fetch failed',
        pins: [],
        count: 0,
        empty: true,
      },
      { status: 502 },
    );
  }
}
