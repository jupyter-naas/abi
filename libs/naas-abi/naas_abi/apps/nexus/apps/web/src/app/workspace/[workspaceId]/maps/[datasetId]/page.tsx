'use client';

import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { getMapsDataset, isMapsDatasetId } from '../lib/datasets';
import { MapsAis } from '../components/maps-ais';
import { MapsConflict } from '../components/maps-conflict';
import { MapsEarthquakes } from '../components/maps-earthquakes';
import { MapsEonet } from '../components/maps-eonet';
import { MapsFlights } from '../components/maps-flights';
import { MapsGdacs } from '../components/maps-gdacs';
import { MapsIss } from '../components/maps-iss';
import { MapsNaturalEarth } from '../components/maps-natural-earth';
import { MapsNews } from '../components/maps-news';
import { MapsNhc } from '../components/maps-nhc';
import { MapsNws } from '../components/maps-nws';
import { MapsOpenaq } from '../components/maps-openaq';
import { MapsOpenStreetMap } from '../components/maps-openstreetmap';
import { MapsPresence } from '../components/maps-presence';
import { MapsTemperature } from '../components/maps-temperature';
import { MapsVolcanoes } from '../components/maps-volcanoes';
import { MapsWildfires } from '../components/maps-wildfires';
import { MapsWog } from '../components/maps-wog';
import '../components/maps-components.css';

export default function MapsDatasetPage() {
  const params = useParams();
  const rawId = typeof params?.datasetId === 'string' ? params.datasetId : '';
  const dataset = getMapsDataset(rawId);

  if (!dataset || !isMapsDatasetId(rawId)) {
    return (
      <div className="maps-root">
        <div className="maps-header-gap">
          <Header title="Maps" subtitle="Unknown dataset" />
        </div>
        <div className="maps-empty">
          <h3>Dataset not found</h3>
          <p>
            Open the Maps library and pick a Public, Private, or Custom dataset.
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
        {dataset.id === 'eonet' ? <MapsEonet /> : null}
        {dataset.id === 'openaq' ? <MapsOpenaq /> : null}
        {dataset.id === 'nws' ? <MapsNws /> : null}
        {dataset.id === 'nhc' ? <MapsNhc /> : null}
        {dataset.id === 'volcanoes' ? <MapsVolcanoes /> : null}
        {dataset.id === 'flights' ? <MapsFlights /> : null}
        {dataset.id === 'conflict' ? <MapsConflict /> : null}
        {dataset.id === 'news' ? <MapsNews /> : null}
        {dataset.id === 'ais' ? <MapsAis /> : null}
        {dataset.id === 'iss' ? <MapsIss /> : null}
        {dataset.id === 'presence' ? <MapsPresence /> : null}
        {dataset.id === 'wog' ? <MapsWog /> : null}
      </div>
    </div>
  );
}
