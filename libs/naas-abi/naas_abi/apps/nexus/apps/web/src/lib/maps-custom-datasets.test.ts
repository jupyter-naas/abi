import { afterEach, describe, expect, it, vi } from 'vitest';

import { parseMapsCustomDatasets } from './maps-custom-datasets';

const VALID = {
  id: 'acme-sites',
  title: 'Acme Sites',
  description: 'Sites Acme operates.',
  icon: 'MapPin',
  order: 2,
  endpoint: '/api/acme/sites',
};

afterEach(() => {
  vi.restoreAllMocks();
});

function silenceWarnings() {
  return vi.spyOn(console, 'warn').mockImplementation(() => {});
}

describe('parseMapsCustomDatasets', () => {
  it('registers nothing when unset, empty, or not a JSON array', () => {
    silenceWarnings();
    expect(parseMapsCustomDatasets(undefined)).toEqual([]);
    expect(parseMapsCustomDatasets(null)).toEqual([]);
    expect(parseMapsCustomDatasets('   ')).toEqual([]);
    expect(parseMapsCustomDatasets('not json')).toEqual([]);
    expect(parseMapsCustomDatasets('{"id":"x"}')).toEqual([]);
  });

  it('parses a valid descriptor and defaults the optional fields', () => {
    const [dataset] = parseMapsCustomDatasets(JSON.stringify([VALID]));
    expect(dataset).toMatchObject({
      id: 'acme-sites',
      title: 'Acme Sites',
      icon: 'MapPin',
      order: 2,
      endpoint: '/api/acme/sites',
    });
    expect(dataset.emptyTitle).toBeUndefined();

    const [minimal] = parseMapsCustomDatasets(
      JSON.stringify([{ id: 'a', title: 'A', endpoint: '/api/a' }]),
    );
    expect(minimal.icon).toBe('Map');
    expect(minimal.order).toBe(0);
    expect(minimal.description).toBe('');
  });

  it('drops entries whose endpoint is not a Nexus API path', () => {
    silenceWarnings();
    const offHost = [
      { ...VALID, endpoint: 'https://evil.example.com/pins' },
      { ...VALID, id: 'b', endpoint: '//evil.example.com/pins' },
      { ...VALID, id: 'c', endpoint: 'api/relative' },
      { ...VALID, id: 'd', endpoint: '' },
    ];
    expect(parseMapsCustomDatasets(JSON.stringify(offHost))).toEqual([]);
  });

  it('drops entries whose id would escape the /api/maps/custom segment', () => {
    silenceWarnings();
    const unsafe = [
      { ...VALID, id: '../secrets' },
      { ...VALID, id: 'Has Spaces' },
      { ...VALID, id: 'UPPER' },
      { ...VALID, id: '-leading-dash' },
      { ...VALID, id: '' },
    ];
    expect(parseMapsCustomDatasets(JSON.stringify(unsafe))).toEqual([]);
  });

  it('keeps one entry per id and sorts by order', () => {
    silenceWarnings();
    const entries = [
      { ...VALID, id: 'second', order: 5 },
      { ...VALID, id: 'first', order: 1 },
      { ...VALID, id: 'second', order: 0, title: 'Duplicate' },
    ];
    expect(parseMapsCustomDatasets(JSON.stringify(entries)).map((d) => d.id)).toEqual([
      'first',
      'second',
    ]);
  });

  it('keeps the valid entries when a sibling is malformed', () => {
    const warn = silenceWarnings();
    const datasets = parseMapsCustomDatasets(
      JSON.stringify([VALID, { id: 'broken' }, null, 'nope']),
    );
    expect(datasets.map((d) => d.id)).toEqual(['acme-sites']);
    expect(warn).toHaveBeenCalled();
  });
});
