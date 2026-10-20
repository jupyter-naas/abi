import { describe, expect, it } from 'vitest';
import { collectGdacsPins, GDACS_EVENT_TYPES, gdacsEventUrl } from './gdacs';

describe('gdacs', () => {
  it('asks for one event type per call', () => {
    expect(gdacsEventUrl('EQ')).toBe(
      'https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventtype=EQ',
    );
    expect(GDACS_EVENT_TYPES).toEqual(['EQ', 'TC', 'FL', 'VO', 'DR', 'WF']);
  });

  it('merges the collections, each event once, and caps the pins', () => {
    const quake = {
      properties: { eventtype: 'EQ', eventid: 1, name: 'M 6.1', alertlevel: 'Orange' },
      geometry: { type: 'Point', coordinates: [-175.1, -18.7] },
    };
    const pins = collectGdacsPins([
      { features: [quake, quake, { properties: { eventtype: 'EQ' }, geometry: { coordinates: [0] } }] },
      { features: [{ properties: { eventtype: 'TC', eventid: 1 }, geometry: { coordinates: [120, 15] } }] },
    ]);

    expect(pins).toHaveLength(2);
    expect(pins[0]).toMatchObject({
      id: 'EQ-1',
      lat: -18.7,
      lng: -175.1,
      label: 'M 6.1',
      detail: 'EQ · Orange · GDACS',
      color: '#ea580c',
    });
    expect(pins[1]).toMatchObject({ id: 'TC-1', label: 'TC event', color: '#2563eb' });

    expect(collectGdacsPins([{ features: [quake] }, { features: [quake] }], 1)).toHaveLength(1);
  });

  it('lets the collections take turns when the limit is reached', () => {
    const event = (eventtype: string, eventid: number) => ({
      properties: { eventtype, eventid },
      geometry: { coordinates: [eventid, 1] },
    });
    const earthquakes = Array.from({ length: 10 }, (_, n) => event('EQ', n));
    const pins = collectGdacsPins(
      [{ features: earthquakes }, { features: [event('TC', 1), event('TC', 2)] }, { features: [event('FL', 1)] }],
      6,
    );

    expect(pins.map((p) => p.id)).toEqual(['EQ-0', 'TC-1', 'FL-1', 'EQ-1', 'TC-2', 'EQ-2']);
  });
});
