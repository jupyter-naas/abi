'use client';

import { useEffect, useMemo, useState } from 'react';
import type { Map as LeafletMap } from 'leaflet';
import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { coverageCountries, coverageCountry, type CountryBorders } from '../lib/maps-coverage';

interface Props {
  map: LeafletMap;
  leaflet: typeof import('leaflet');
  pins: MapsPinMarker[];
  selectedCountry: string;
  onSelectCountry: (country: string) => void;
}

/** Geography is a display layer. Coverage and counts come only from the scoped feed. */
export function MapsCoverageLayer({ map, leaflet: L, pins, selectedCountry, onSelectCountry }: Props) {
  const [borders, setBorders] = useState<CountryBorders | null>(null);
  const [error, setError] = useState(false);
  const countries = useMemo(() => coverageCountries(pins), [pins]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    fetch(MAPS_PUBLIC_FEEDS.naturalEarth, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Country borders unavailable');
        const data = await response.json();
        if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) throw new Error('Invalid country borders');
        if (!controller.signal.aborted) setBorders(data);
      })
      .catch(() => { if (active) setError(true); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; controller.abort(); clearTimeout(timeout); };
  }, []);

  useEffect(() => {
    if (!borders) return;
    const layer = L.geoJSON(borders, {
      filter: feature => !!coverageCountry(feature, countries),
      style: feature => ({
        className: 'maps-coverage-country' + (feature && coverageCountry(feature, countries) === selectedCountry ? ' maps-coverage-country--selected' : ''),
        weight: 1.5,
        fillOpacity: 0.25,
      }),
      onEachFeature: (feature, polygon) => {
        const country = coverageCountry(feature, countries)!;
        const count = countries.get(country)!;
        const label = country + ' · ' + count + (count === 1 ? ' city' : ' cities');
        const tooltip = document.createElement('span');
        tooltip.textContent = label;
        polygon.bindTooltip(tooltip, { sticky: true, className: 'maps-coverage-tooltip' });
        polygon.on('click', () => onSelectCountry(country));
        polygon.on('add', () => {
          const element = (polygon as import('leaflet').Path).getElement();
          if (!element) return;
          element.setAttribute('tabindex', '0');
          element.setAttribute('role', 'button');
          element.setAttribute('aria-label', label);
          element.addEventListener('keydown', event => {
            const key = (event as KeyboardEvent).key;
            if (key === 'Enter' || key === ' ') {
              event.preventDefault();
              event.stopPropagation();
              onSelectCountry(country);
            }
          });
        });
      },
      attribution: '<a href="https://www.naturalearthdata.com/">Natural Earth</a>',
    }).addTo(map);
    return () => { layer.remove(); };
  }, [borders, countries, map, L, selectedCountry, onSelectCountry]);

  return <div className="maps-legend maps-coverage-legend" aria-live="polite">
    <strong>City coverage</strong>
    <span><i className="maps-coverage-swatch"/>Countries with listed offices</span>
    <span>{pins.length} cities · {countries.size} countries</span>
    <small>Country shading summarizes listed city presence.</small>
    {error && <small>Country shading unavailable. City markers remain available.</small>}
    {!borders && !error && <small>Loading country boundaries…</small>}
  </div>;
}
