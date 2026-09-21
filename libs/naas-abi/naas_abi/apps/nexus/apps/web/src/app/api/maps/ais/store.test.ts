import { describe, expect, it } from 'vitest';
import {
  aisVesselsToPins,
  inAisBounds,
  ingestAisEnvelope,
  parseAisBounds,
  parseAisFrame,
  vesselsInView,
} from './store';

const POSITION = {
  MessageType: 'PositionReport',
  Message: {
    PositionReport: { Sog: 12.4, Cog: 90, Destination: 'ROTTERDAM' },
  },
  MetaData: {
    MMSI: 244660000,
    latitude: 51.9,
    longitude: 4.3,
    ShipName: 'EXAMPLE',
    time_utc: '2026-09-21T00:00:00Z',
  },
};

describe('AIS store', () => {
  it('classifies auth errors and ignores malformed frames', () => {
    expect(parseAisFrame('not-json').kind).toBe('malformed');
    expect(parseAisFrame('{"error":"Invalid API Key"}')).toEqual({
      kind: 'error',
      message: 'Invalid API Key',
    });
    expect(parseAisFrame(JSON.stringify(POSITION)).kind).toBe('data');
  });

  it('ingests a position and filters by viewport, including dateline wrap', () => {
    const vessels = new Map();
    expect(ingestAisEnvelope(vessels, POSITION, 1_000)).toBe(true);
    expect(vessels.get('244660000')?.name).toBe('EXAMPLE');

    const inView = vesselsInView(
      vessels,
      { west: 4, south: 51, east: 5, north: 52 },
      400,
      1_000,
    );
    expect(inView).toHaveLength(1);
    expect(
      vesselsInView(
        vessels,
        { west: -1, south: 51, east: 1, north: 52 },
        400,
        1_000,
      ),
    ).toHaveLength(0);

    expect(inAisBounds(0, 179, { west: 170, south: -10, east: -170, north: 10 })).toBe(
      true,
    );
    expect(inAisBounds(0, 0, { west: 170, south: -10, east: -170, north: 10 })).toBe(
      false,
    );
  });

  it('parses bounds from query params and builds pins with source evidence', () => {
    const bounds = parseAisBounds(
      new URLSearchParams('west=-1&south=51&east=1&north=52'),
    );
    expect(bounds).toEqual({ west: -1, south: 51, east: 1, north: 52 });
    expect(parseAisBounds(new URLSearchParams('west=abc'))).toBeNull();

    const vessels = new Map();
    ingestAisEnvelope(vessels, POSITION, 1_000);
    const pins = aisVesselsToPins([...vessels.values()]);
    expect(pins[0]).toMatchObject({
      id: '244660000',
      label: 'EXAMPLE',
      sources: [{ title: 'AISStream', url: 'https://aisstream.io/' }],
    });
  });
});
