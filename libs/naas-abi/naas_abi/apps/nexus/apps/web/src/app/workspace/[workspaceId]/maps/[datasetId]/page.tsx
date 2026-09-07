'use client';

import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { getMapsCustomDataset } from '@/lib/maps-custom-datasets';
import { getMapsDataset, isMapsDatasetId } from '../lib/datasets';
import { MapsAis } from '../components/maps-ais';
import { MapsConflict } from '../components/maps-conflict';
import { MapsCustomFeed } from '../components/maps-custom-feed';
import { MapsEarthquakes } from '../components/maps-earthquakes';
import { MapsEonetAll } from '../components/maps-eonet-all';
import { MapsFlights } from '../components/maps-flights';
import { MapsGdacs } from '../components/maps-gdacs';
import { MapsGulfStrikes } from '../components/maps-gulf-strikes';
import { MapsIss } from '../components/maps-iss';
import { MapsNaturalEarth } from '../components/maps-natural-earth';
import { MapsNews } from '../components/maps-news';
import { MapsNwsAlerts } from '../components/maps-nws-alerts';
import { MapsOpenaq } from '../components/maps-openaq';
import { MapsOpenStreetMap } from '../components/maps-openstreetmap';
import { MapsPresence } from '../components/maps-presence';
import { MapsTemperature } from '../components/maps-temperature';
import { MapsTropicalStorms } from '../components/maps-tropical-storms';
import { MapsVolcanoes } from '../components/maps-volcanoes';
import { MapsWildfires } from '../components/maps-wildfires';
import '../components/maps-components.css';

export default function MapsDatasetPage() {
  const params = useParams();
  const rawId = typeof params?.datasetId === 'string' ? params.datasetId : '';
  const dataset = getMapsDataset(rawId);
  const customDataset = getMapsCustomDataset(rawId);

  if (!dataset || !isMapsDatasetId(rawId)) {
    return (
      <div className="maps-root">
        <div className="maps-header-gap">
          <Header title="Maps" subtitle="Unknown dataset" />
        </div>
        <div className="maps-empty">
          <h3>Dataset not found</h3>
          <p>
            Open the Maps library and pick a Public or Private dataset.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="maps-root">
      <div className="maps-header-gap">
        <Header title="Maps" subtitle={dataset.title} />
      </div>
      <div className="maps-body">
        {dataset.id === 'openstreetmap' ? <MapsOpenStreetMap /> : null}
        {dataset.id === 'earthquakes' ? <MapsEarthquakes /> : null}
        {dataset.id === 'wildfires' ? <MapsWildfires /> : null}
        {dataset.id === 'temperature' ? <MapsTemperature /> : null}
        {dataset.id === 'natural-earth' ? <MapsNaturalEarth /> : null}
        {dataset.id === 'gdacs' ? <MapsGdacs /> : null}
        {dataset.id === 'eonet-all' ? <MapsEonetAll /> : null}
        {dataset.id === 'openaq' ? <MapsOpenaq /> : null}
        {dataset.id === 'nws-alerts' ? <MapsNwsAlerts /> : null}
        {dataset.id === 'tropical-storms' ? <MapsTropicalStorms /> : null}
        {dataset.id === 'volcanoes' ? <MapsVolcanoes /> : null}
        {dataset.id === 'flights' ? <MapsFlights /> : null}
        {dataset.id === 'conflict' ? <MapsConflict /> : null}
        {dataset.id === 'gulf-strikes' ? <MapsGulfStrikes /> : null}
        {dataset.id === 'news' ? <MapsNews /> : null}
        {dataset.id === 'ais' ? <MapsAis /> : null}
        {dataset.id === 'iss' ? <MapsIss /> : null}
        {dataset.id === 'presence' ? <MapsPresence /> : null}
        {customDataset ? <MapsCustomFeed dataset={customDataset} /> : null}
      </div>
    </div>
  );
}
