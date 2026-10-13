'use client';

import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { getMapsCustomDataset } from '@/lib/maps-custom-datasets';
import { useGraphMapLayers } from '../lib/use-graph-map-layers';
import { MapsGraphFeed } from '../components/maps-graph-feed';
import { MapsAllLayers } from '../components/maps-all-layouts';
import { MapsLayoutFeed } from '../components/maps-layout-feed';
import { MapsMenuBar } from '../components/maps-menu-bar';
import { ALL_LAYERS_ID } from '../lib/layouts';
import { mapsSettingsPath } from '../lib/maps-route';
import { useMapLayers } from '../lib/use-map-layouts';
import { getMapsDataset } from '../lib/datasets';
import { MapsAis } from '../components/maps-ais';
import { MapsConflict } from '../components/maps-conflict';
import { MapsCustomFeed } from '../components/maps-custom-feed';
import { MapsEarthquakes } from '../components/maps-earthquakes';
import { MapsEonetAll } from '../components/maps-eonet-all';
import { MapsFlights } from '../components/maps-flights';
import { MapsGdacs } from '../components/maps-gdacs';
import { MapsGulfStrikes } from '../components/maps-gulf-strikes';
import { MapsIss } from '../components/maps-iss';
import { MapsNews } from '../components/maps-news';
import { MapsNwsAlerts } from '../components/maps-nws-alerts';
import { MapsOpenaq } from '../components/maps-openaq';
import { MapsPresence } from '../components/maps-presence';
import { MapsTemperature } from '../components/maps-temperature';
import { MapsTropicalStorms } from '../components/maps-tropical-storms';
import { MapsVolcanoes } from '../components/maps-volcanoes';
import { MapsWildfires } from '../components/maps-wildfires';
import '../components/maps-components.css';

export default function MapsDatasetPage() {
  const params = useParams();
  const rawId = typeof params?.datasetId === 'string' ? params.datasetId : '';
  const graphLayers = useGraphMapLayers();
  const graphDataset = graphLayers.layers.find(d => d.id === rawId);
  const dataset = getMapsDataset(rawId) ?? graphDataset;
  const customDataset = getMapsCustomDataset(rawId);
  const layers = useMapLayers();
  const workspaceLayer = layers.entries.find((e) => e.id === rawId && e.kind === 'workspace');
  const hidden = layers.hidden.includes(rawId);
  const menu = <MapsMenuBar workspaceId={layers.workspaceId} canEdit={layers.canEdit} />;

  if (rawId === ALL_LAYERS_ID) {
    return (
      <div className="maps-root">
        <div className="maps-header-gap">
          <Header title="Maps" subtitle="All layers" nav={menu} />
        </div>
        <div className="maps-body">
          <MapsAllLayers />
        </div>
      </div>
    );
  }

  if (hidden || (!dataset && !workspaceLayer)) {
    if (!hidden && (graphLayers.loading || layers.loading)) return <div className="maps-empty">Loading map layers…</div>;
    return (
      <div className="maps-root">
        <div className="maps-header-gap">
          <Header title="Maps" subtitle={hidden ? 'Hidden layer' : 'Unknown layer'} nav={menu} />
        </div>
        <div className="maps-empty">
          <h3>{hidden ? 'This layer is hidden in this workspace' : 'Layer not found'}</h3>
          <p>
            {hidden ? (
              <>A workspace admin hid it in <a className="underline" href={mapsSettingsPath(layers.workspaceId)}>Settings → Maps</a>.</>
            ) : (
              'Pick a layer in the Maps sidebar, or open All layers.'
            )}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="maps-root">
      <div className="maps-header-gap">
        <Header title="Maps" subtitle={(dataset ?? workspaceLayer)?.title} nav={menu} />
      </div>
      <div className="maps-body">
        {!dataset && workspaceLayer ? <MapsLayoutFeed layout={workspaceLayer} /> : null}
        {dataset?.id === 'earthquakes' ? <MapsEarthquakes /> : null}
        {dataset?.id === 'wildfires' ? <MapsWildfires /> : null}
        {dataset?.id === 'temperature' ? <MapsTemperature /> : null}
        {dataset?.id === 'gdacs' ? <MapsGdacs /> : null}
        {dataset?.id === 'eonet-all' ? <MapsEonetAll /> : null}
        {dataset?.id === 'openaq' ? <MapsOpenaq /> : null}
        {dataset?.id === 'nws-alerts' ? <MapsNwsAlerts /> : null}
        {dataset?.id === 'tropical-storms' ? <MapsTropicalStorms /> : null}
        {dataset?.id === 'volcanoes' ? <MapsVolcanoes /> : null}
        {dataset?.id === 'flights' ? <MapsFlights /> : null}
        {dataset?.id === 'conflict' ? <MapsConflict /> : null}
        {dataset?.id === 'gulf-strikes' ? <MapsGulfStrikes /> : null}
        {dataset?.id === 'news' ? <MapsNews /> : null}
        {dataset?.id === 'ais' ? <MapsAis /> : null}
        {dataset?.id === 'iss' ? <MapsIss /> : null}
        {dataset?.id === 'presence' ? <MapsPresence /> : null}
        {customDataset ? <MapsCustomFeed key={customDataset.id} dataset={customDataset} /> : null}
        {graphDataset ? <MapsGraphFeed dataset={graphDataset} /> : null}
      </div>
    </div>
  );
}
