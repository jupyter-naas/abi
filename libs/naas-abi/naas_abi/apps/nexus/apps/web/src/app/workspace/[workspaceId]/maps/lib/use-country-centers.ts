'use client';

import { useEffect, useState } from 'react';
import { buildCountryCenterIndex, type CountryCenterIndex } from './maps-country-centers';
import { fetchNaturalEarthCountries } from './maps-natural-earth-basemap';

let indexPromise: Promise<CountryCenterIndex> | null = null;

/** Country label points for group-by-country (Natural Earth, loaded once when first needed). */
export function useCountryCenters(enabled: boolean): CountryCenterIndex | null {
  const [index, setIndex] = useState<CountryCenterIndex | null>(null);
  useEffect(() => {
    if (!enabled || index) return;
    let cancelled = false;
    indexPromise ??= fetchNaturalEarthCountries().then(buildCountryCenterIndex);
    indexPromise
      .then((value) => {
        if (!cancelled) setIndex(value);
      })
      .catch(() => {
        indexPromise = null; // countries fall back to the mean of their pins
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, index]);
  return index;
}
