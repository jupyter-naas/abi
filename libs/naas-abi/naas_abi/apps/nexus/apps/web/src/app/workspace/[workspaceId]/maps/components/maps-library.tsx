'use client';

import { useRouter } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { MAPS_DATASETS } from '../lib/datasets';
import { mapsDatasetPath } from '../lib/maps-route';
import './maps-components.css';

export function MapsLibrary() {
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  return (
    <div className="maps-library">
      <div className="maps-library-intro">
        <h2>Maps</h2>
        <p>
          Load a dataset onto the canvas. Start with Here (presence), then open the
          World Organization Graph when you need org search.
        </p>
      </div>

      <div className="maps-dataset-grid">
        {MAPS_DATASETS.map((dataset) => (
          <button
            key={dataset.id}
            type="button"
            className={
              dataset.id === 'presence'
                ? 'maps-dataset-card maps-dataset-card--primer'
                : 'maps-dataset-card'
            }
            onClick={() =>
              router.push(mapsDatasetPath(currentWorkspaceId, dataset.id))
            }
          >
            <span className="maps-dataset-card__eyebrow">
              {dataset.id === 'presence' ? 'Primer' : 'Library'}
            </span>
            <span className="maps-dataset-card__title">{dataset.title}</span>
            <span className="maps-dataset-card__desc">{dataset.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
