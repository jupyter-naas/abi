import {afterEach, describe, expect, it, vi} from 'vitest';
import {fetchMapsFeedPins, graphObjectHref, normalizeFeedLoad} from './maps-feed';
afterEach(() => vi.unstubAllGlobals());
describe('graph map pin contract', () => {
  it('keeps entity identity and evidence while discarding invalid coordinates and unsafe links', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true, json:async () => ({pins:[
      {id:'one',lat:48,lng:2,label:'Paris',entityUri:'urn:office',graphUri:'urn:snapshot',country:'France',precision:'City reference point',observedAt:'2026-09-20',address:'5 Rue Charlot',streetViewUrl:'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=48,2',imageSearchUrl:'https://www.google.com/search?tbm=isch&q=Paris',photoUrl:'javascript:alert(1)',sources:[{title:'Evidence',url:'https://example.com/source'},{title:'Bad',url:'javascript:alert(1)'}],relationships:[{label:'Organization',value:'Example',entityUri:'urn:company'}]},
      {id:'invalid',lat:999,lng:2},
    ]})}));
    const {pins} = await fetchMapsFeedPins('/feed');
    expect(pins).toHaveLength(1);
    expect(pins[0]).toMatchObject({entityUri:'urn:office',graphUri:'urn:snapshot',country:'France',address:'5 Rue Charlot'});
    expect(pins[0].streetViewUrl).toBe('https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=48,2');
    expect(pins[0].imageSearchUrl).toBe('https://www.google.com/search?tbm=isch&q=Paris');
    expect(pins[0].photoUrl).toBeUndefined();
    expect(pins[0].sources).toEqual([{title:'Evidence',url:'https://example.com/source'}]);
    expect(pins[0].relationships?.[0].entityUri).toBe('urn:company');
  });
  it('keeps feed freshness and attribution without treating needsKey as a thrown error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true, json:async () => ({
      pins: [{id:'ship',lat:1,lng:2,label:'Vessel'}],
      source: 'aisstream',
      attribution: 'AISStream',
      observedAt: '2026-09-21T00:00:00Z',
      stale: false,
      coverage: 'viewport',
    })}));
    const feed = await fetchMapsFeedPins('/api/maps/ais');
    expect(feed.source).toBe('aisstream');
    expect(feed.attribution).toBe('AISStream');
    expect(feed.observedAt).toBe('2026-09-21T00:00:00Z');
    expect(feed.coverage).toBe('viewport');
    expect(feed.empty).toBe(false);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true, json:async () => ({
      pins: [], empty: true, needsKey: true, reason: 'Set AISSTREAM_API_KEY',
    })}));
    const missing = await fetchMapsFeedPins('/api/maps/ais');
    expect(missing.needsKey).toBe(true);
    expect(missing.empty).toBe(true);
    expect(missing.reason).toBe('Set AISSTREAM_API_KEY');
  });
  it('constructs KG links in the current workspace, encoding graph and entity IRIs', () => {
    expect(graphObjectHref('ws-one','urn:graph','https://example.com/id?a=b')).toBe('/workspace/ws-one/graph/individuals?graph=urn%3Agraph&selected=https%3A%2F%2Fexample.com%2Fid%3Fa%3Db');
  });
});


describe('normalizeFeedLoad', () => {
  const paris = {id:'paris',lat:48.86,lng:2.35,label:'Paris',country:'France'};
  const london = {id:'london',lat:51.5,lng:-0.12,label:'London',country:'United Kingdom'};

  it('unwraps a Palantir offices payload instead of iterating the wrapper', () => {
    const feed = normalizeFeedLoad({
      coverage: {pins: [{...paris, memberIds: ['street']}]},
      pins: [paris, london],
      count: 2,
      empty: false,
      graph_uri: 'urn:snapshot',
      layer_title: 'Palantir Offices',
      message: 'Source-reported street addresses',
    });
    expect(feed.pins).toHaveLength(2);
    expect(feed.pins.map(p => p.label)).toEqual(['Paris', 'London']);
    expect(feed.coveragePins).toHaveLength(1);
    expect(feed.coverage).toBeUndefined();
    expect(feed.reason).toBe('Source-reported street addresses');
  });

  it('reads GeoJSON Point features and URI-keyed pin dicts', () => {
    const fromFeatures = normalizeFeedLoad({
      type: 'FeatureCollection',
      features: [
        {type:'Feature', id:'paris', geometry:{type:'Point', coordinates:[2.35, 48.86]}, properties:{label:'Paris'}},
      ],
    });
    expect(fromFeatures.pins).toEqual([expect.objectContaining({id:'paris', lat:48.86, lng:2.35, label:'Paris'})]);

    const fromDict = normalizeFeedLoad({
      pins: {'urn:office:paris': paris, 'urn:office:london': london},
    });
    expect(fromDict.pins).toHaveLength(2);
  });

  it('throws a clear error for a non-feed object instead of loaded is not iterable', () => {
    expect(() => normalizeFeedLoad({detail: 'Internal Server Error'})).toThrow('Map feed did not return locations');
  });
});

it('validates coverage coordinates and evidence and links only members in the same feed', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({
    pins:[{id:'address',lat:48,lng:2,label:'Street address'}],
    coverage:{pins:[
      {id:'city',lat:48.1,lng:2.1,label:'City',entityUri:'urn:city',memberIds:['address','other-workspace'],sources:[{title:'Valid',url:'https://example.com'},{title:'Unsafe',url:'javascript:alert(1)'}]},
      {id:'bad',lat:1000,lng:2},
    ]},
  })}));
  const feed=await fetchMapsFeedPins('/feed');
  expect(feed.coveragePins).toHaveLength(1);
  expect(feed.coveragePins?.[0].memberIds).toEqual(['address']);
  expect(feed.coveragePins?.[0].sources).toHaveLength(1);
  expect(feed.coveragePins?.[0].entityUri).toBe('urn:city');
});
