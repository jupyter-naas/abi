'use client';

import { MapsDatasetGroups } from './maps-section';
import './maps-components.css';

/**
 * Desktop / shared library chrome. Mobile list uses MapsSection via the shell;
 * this page mirrors the same Public / Private / Custom grouping.
 */
export function MapsLibrary() {
  return (
    <div className="maps-library">
      <div className="maps-library-intro">
        <h2>Maps</h2>
        <p>
          Sources mirror Search: Public free layers, Private presence, Custom
          domain graphs such as the World Organization Graph.
        </p>
      </div>

      <div className="maps-library-sources">
        <MapsDatasetGroups dense />
      </div>
    </div>
  );
}
