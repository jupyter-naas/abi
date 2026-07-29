'use client';

import { MapsDatasetGroups } from './maps-section';
import './maps-components.css';

/**
 * Desktop / shared library chrome. Mobile list uses MapsSection via the shell;
 * this page mirrors the same Public / Private grouping (Custom hidden when empty).
 */
export function MapsLibrary() {
  return (
    <div className="maps-library">
      <div className="maps-library-intro">
        <h2>Maps</h2>
        <p>
          Sources mirror Search: Public free layers and Private presence. Custom
          stays empty upstream so product overlays can inject their own datasets.
        </p>
      </div>

      <div className="maps-library-sources">
        <MapsDatasetGroups dense />
      </div>
    </div>
  );
}
