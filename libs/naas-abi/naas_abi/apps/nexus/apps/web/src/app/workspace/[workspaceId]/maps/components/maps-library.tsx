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
          Pick one basemap, then switch on the layouts to draw on it. Custom
          stays empty upstream so a deployment can add its own pin layouts.
        </p>
      </div>

      <div className="maps-library-sources">
        <MapsDatasetGroups dense />
      </div>
    </div>
  );
}
