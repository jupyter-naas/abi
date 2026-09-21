import { NextRequest } from 'next/server';

import { mapsJson } from '../_lib';
import { lookupPlaceCard, parsePlaceQuery } from './place';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const query = parsePlaceQuery(new URL(req.url).searchParams);
  if (!query) {
    return mapsJson({ error: 'lat and lng are required' }, { status: 400 });
  }
  const card = await lookupPlaceCard(query);
  return mapsJson(card, { cacheSeconds: 300 });
}
