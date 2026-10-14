'use client';

import { MapsDatasetGroups } from './maps-section';
import './maps-components.css';

/**
 * Desktop / shared library chrome. Mobile list uses MapsSection via the shell.
 */
export function MapsLibrary() {
  return (
    <div className="maps-library">
      <div className="maps-library-intro">
        <h2>Maps</h2>
        <p>
          Switch data layers on in Public (and Custom when configured). Choose
          the basemap from the control on the map (top-right).
        </p>
      </div>

      <div className="maps-library-sources">
        <MapsDatasetGroups dense />
      </div>
    </div>
  );
}
