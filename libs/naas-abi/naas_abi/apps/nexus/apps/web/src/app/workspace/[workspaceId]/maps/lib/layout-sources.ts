import { getApiUrl } from '@/lib/config';
import { useAuthStore } from '@/stores/auth';
import { fetchFeed as aisPins } from '../components/maps-ais';
import { fetchPins as conflictPins } from '../components/maps-conflict';
import { fetchPins as earthquakePins } from '../components/maps-earthquakes';
import { fetchPins as eonetPins } from '../components/maps-eonet-all';
import { fetchFeed as flightsPins } from '../components/maps-flights';
import { fetchPins as gdacsPins } from '../components/maps-gdacs';
import { fetchPins as gulfStrikesPins } from '../components/maps-gulf-strikes';
import { fetchPins as issPins } from '../components/maps-iss';
import { fetchPins as newsPins } from '../components/maps-news';
import { fetchPins as nwsAlertsPins } from '../components/maps-nws-alerts';
import { fetchPins as openaqPins } from '../components/maps-openaq';
import { fetchPins as presencePins } from '../components/maps-presence';
import { fetchPins as temperaturePins } from '../components/maps-temperature';
import { fetchPins as tropicalStormsPins } from '../components/maps-tropical-storms';
import { fetchPins as volcanoesPins } from '../components/maps-volcanoes';
import { fetchPins as wildfirePins } from '../components/maps-wildfires';
import { mapsCustomFeedUrl } from './datasets';
import type { LayoutEntry } from './layouts';
import { layoutsApi } from './layouts-api';
import { fetchMapsFeedPins, normalizeFeedLoad, type MapsFeedResult } from './maps-feed';
import type { MapsFeedView } from './maps-view';

/**
 * Where each combinable layout's pins come from, for the All layouts map.
 * Built-in feeds reuse the exact fetchers of their own canvases.
 */
type Fetcher = (signal: AbortSignal, view?: MapsFeedView) => Promise<unknown>;

const BUILTIN_FETCHERS: Record<string, Fetcher> = {
  ais: aisPins,
  conflict: conflictPins,
  earthquakes: earthquakePins,
  'eonet-all': eonetPins,
  flights: flightsPins,
  gdacs: gdacsPins,
  'gulf-strikes': gulfStrikesPins,
  iss: issPins,
  news: newsPins,
  'nws-alerts': nwsAlertsPins,
  openaq: openaqPins,
  presence: presencePins,
  temperature: temperaturePins,
  'tropical-storms': tropicalStormsPins,
  volcanoes: volcanoesPins,
  wildfires: wildfirePins,
};

function authHeader(): HeadersInit {
  const token = useAuthStore.getState().token;
  if (!token) throw new Error('Not authenticated');
  return { Authorization: `Bearer ${token}` };
}

export function layoutPinSource(
  entry: LayoutEntry,
  workspaceId: string,
): ((signal: AbortSignal, view?: MapsFeedView) => Promise<MapsFeedResult>) | null {
  if (!entry.combinable) return null;
  if (entry.kind === 'workspace') {
    return (signal) => fetchMapsFeedPins(layoutsApi.feedUrl(workspaceId, entry.id), signal, authHeader());
  }
  if (entry.kind === 'graph') {
    const url = `${getApiUrl()}/api/maps/layers/${encodeURIComponent(entry.id)}?workspace_id=${encodeURIComponent(workspaceId)}`;
    return (signal) => fetchMapsFeedPins(url, signal, authHeader());
  }
  const builtin = BUILTIN_FETCHERS[entry.id];
  if (builtin) return async (signal, view) => normalizeFeedLoad(await builtin(signal, view));
  // Deployment Custom dataset: the authed proxy route.
  return (signal) => fetchMapsFeedPins(mapsCustomFeedUrl(entry.id, workspaceId), signal, authHeader());
}
