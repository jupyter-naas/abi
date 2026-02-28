import { NextResponse } from 'next/server';

let cache: { data: unknown; at: number } | null = null;
const CACHE_TTL = 60 * 60 * 1000; // 1 hour

export async function GET() {
  if (cache && Date.now() - cache.at < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  try {
    const url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=TLE';
    const res = await fetch(url, {
      headers: { 'User-Agent': 'WorldView/1.0' },
      next: { revalidate: 3600 },
    });

    if (!res.ok) throw new Error(`CelesTrak returned ${res.status}`);

    const text = await res.text();
    const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);

    const satellites = [];
    for (let i = 0; i + 2 < lines.length; i += 3) {
      const name = lines[i].trim();
      const line1 = lines[i + 1];
      const line2 = lines[i + 2];
      if (line1.startsWith('1 ') && line2.startsWith('2 ')) {
        satellites.push({ name, line1, line2 });
      }
    }

    cache = { data: satellites, at: Date.now() };
    return NextResponse.json(satellites);
  } catch (err) {
    console.error('[satellites]', err);
    return NextResponse.json(cache?.data ?? [], { status: 200 });
  }
}
