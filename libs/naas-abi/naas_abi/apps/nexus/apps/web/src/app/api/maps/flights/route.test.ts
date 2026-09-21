import { describe, expect, it } from 'vitest';
import { aircraftToPin, collectFlightPins, parseFlightsQuery } from './flights';

describe('flights query', () => {
  it('uses a viewport query at zoom 4+ and a global sample when zoomed out', () => {
    expect(parseFlightsQuery(new URLSearchParams())).toEqual({ mode: 'sample' });
    expect(
      parseFlightsQuery(
        new URLSearchParams('lat=51.5&lng=-0.1&zoom=2&radiusNm=250'),
      ),
    ).toEqual({ mode: 'sample' });
    expect(
      parseFlightsQuery(
        new URLSearchParams('lat=51.5&lng=-0.1&zoom=8&radiusNm=80'),
      ),
    ).toEqual({ mode: 'viewport', lat: 51.5, lng: -0.1, radiusNm: 80 });
    expect(
      parseFlightsQuery(
        new URLSearchParams('lat=51.5&lng=-0.1&zoom=8&radiusNm=900'),
      ),
    ).toEqual({ mode: 'viewport', lat: 51.5, lng: -0.1, radiusNm: 250 });
  });

  it('drops invalid aircraft and caps the pin list', () => {
    expect(aircraftToPin({ hex: 'abc', lat: 999, lon: 0 }, 'adsb.lol')).toBeNull();
    const pins = collectFlightPins(
      [
        { hex: 'abc', lat: 51, lon: 0, flight: 'BAW1', alt_baro: 35000, gs: 420 },
        { hex: 'ABC', lat: 52, lon: 1, flight: 'BAW1' },
        { hex: 'def', lat: 48, lon: 2, military: true, alt_baro: 20000 },
      ],
      'adsb.lol',
      2,
    );
    expect(pins).toHaveLength(2);
    expect(pins[0]).toMatchObject({
      id: 'abc',
      label: 'BAW1',
      sources: [{ title: 'adsb.lol', url: 'https://adsb.lol/' }],
    });
    expect(String(pins[1].detail)).toContain('military');
  });
});
