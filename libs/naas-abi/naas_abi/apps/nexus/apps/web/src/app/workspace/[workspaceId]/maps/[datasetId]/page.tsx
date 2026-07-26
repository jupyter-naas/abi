'use client';

import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { getMapsDataset, isMapsDatasetId } from '../lib/datasets';
import { MapsPresence } from '../components/maps-presence';
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
            Open the Maps library and pick Here (presence) or World Organization
            Graph.
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
        {dataset.id === 'presence' ? <MapsPresence /> : null}
        {dataset.id === 'wog' ? <MapsWog /> : null}
      </div>
    </div>
  );
}
