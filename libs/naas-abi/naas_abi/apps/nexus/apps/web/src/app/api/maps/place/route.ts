import { mapsJson } from '../_lib';
import { lookupPlaceCard, parsePlaceQuery } from './place';
import { mapsRoute } from '../_guard';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

async function handle(req: Request) {
  const query = parsePlaceQuery(new URL(req.url).searchParams);
  if (!query) {
    return mapsJson({ error: 'lat and lng are required' }, { status: 400 });
  }
  const card = await lookupPlaceCard(query);
  return mapsJson(card, { cacheSeconds: 300 });
}

export const GET = mapsRoute('place', handle, { perMinute: 60, cacheSeconds: 300 });
