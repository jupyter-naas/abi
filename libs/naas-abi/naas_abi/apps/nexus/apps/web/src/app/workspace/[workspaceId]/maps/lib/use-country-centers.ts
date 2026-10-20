'use client';

import { useEffect, useState } from 'react';
import type { CountryCenterRow } from '@/app/api/maps/country-centers/centers';
import { buildCountryCenterIndex, type CountryCenterIndex } from './maps-country-centers';

let indexPromise: Promise<CountryCenterIndex> | null = null;

function loadIndex(): Promise<CountryCenterIndex> {
  indexPromise ??= fetch('/api/maps/country-centers')
    .then(async (response) => {
      if (!response.ok) throw new Error('Country centers unavailable');
      const data = (await response.json()) as { countries?: CountryCenterRow[] };
      return buildCountryCenterIndex(data.countries ?? []);
    })
    .catch((error) => {
      indexPromise = null; // countries fall back to the mean of their pins
      throw error;
    });
  return indexPromise;
}

/** Country label points and continents for map grouping (loaded once when first needed). */
export function useCountryCenters(enabled: boolean): CountryCenterIndex | null {
  const [index, setIndex] = useState<CountryCenterIndex | null>(null);
  useEffect(() => {
    if (!enabled || index) return;
    let cancelled = false;
    loadIndex()
      .then((value) => {
        if (!cancelled) setIndex(value);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [enabled, index]);
  return index;
}
