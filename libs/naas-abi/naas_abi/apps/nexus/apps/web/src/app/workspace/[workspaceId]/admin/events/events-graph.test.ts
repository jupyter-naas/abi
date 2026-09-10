import { describe, expect, it } from 'vitest';
import type { PlatformEvent } from './bfo-event-projection';
import {
  GRAPH_MAX_NODES,
  bfoColumnSwatch,
  bucketHubId,
  buildEventJsonGraph,
  eventForGraph,
  jsonChildPath,
  pathIsOnTrail,
  shortClassName,
  shortJsonLabel,
} from './events-graph';

function baseEvent(overrides: Partial<PlatformEvent> = {}): PlatformEvent {
  return {
    _uri: 'http://ontology.naas.ai/abi/agent/evt-1',
    _class_uri: 'http://ontology.naas.ai/abi/agent/AgentToolCalled',
    _seq: 42,
    _stored_at: '2026-07-31T12:00:00Z',
    ...overrides,
  };
}

describe('shortClassName', () => {
  it('takes the last path or hash segment', () => {
    expect(shortClassName('http://ontology.naas.ai/abi/object_storage/ObjectPut')).toBe('ObjectPut');
    expect(shortClassName('http://ontology.naas.ai/abi/triple_store/SchemaLoaded')).toBe(
      'SchemaLoaded',
    );
    expect(shortClassName('http://example.com/vocab#name')).toBe('name');
  });
});

describe('shortJsonLabel', () => {
  it('keeps short strings and shortens URIs to the last segment', () => {
    expect(shortJsonLabel('ok')).toBe('ok');
    expect(shortJsonLabel('http://ontology.naas.ai/abi/agent/AgentToolCalled')).toBe(
      'AgentToolCalled',
    );
  });

  it('shortens hashes and keeps the full string out of the label', () => {
    const hash = 'a'.repeat(40);
    expect(shortJsonLabel(hash)).toBe('aaaaaaaa...');
    expect(shortJsonLabel(hash).includes(hash)).toBe(false);
  });
});

describe('jsonChildPath / pathIsOnTrail', () => {
  it('builds object and array paths', () => {
    expect(jsonChildPath('$', '_uri')).toBe('$._uri');
    expect(jsonChildPath('$', 0)).toBe('$[0]');
    expect(jsonChildPath('$', 'weird.key')).toBe('$["weird.key"]');
  });

  it('treats ancestors as on the selected trail', () => {
    expect(pathIsOnTrail('$', '$.tags[0]')).toBe(true);
    expect(pathIsOnTrail('$.tags', '$.tags[0]')).toBe(true);
    expect(pathIsOnTrail('$.tags[0]', '$.tags[0]')).toBe(true);
    expect(pathIsOnTrail('$._uri', '$._uri_extra')).toBe(false);
    expect(pathIsOnTrail('$.tags[1]', '$.tags[0]')).toBe(false);
  });
});

describe('buildEventJsonGraph', () => {
  it('returns an empty graph when there is no event', () => {
    expect(buildEventJsonGraph(null).nodes).toEqual([]);
    expect(buildEventJsonGraph(undefined).eventUri).toBeNull();
  });

  it('makes a root plus one child per JSON key, with key-labeled edges', () => {
    const graph = buildEventJsonGraph(
      baseEvent({
        _site: 'deploy.example',
        user_id: 'user-123',
      }),
    );

    expect(graph.eventUri).toBe('http://ontology.naas.ai/abi/agent/evt-1');
    expect(graph.nodes.some((n) => n.kind === 'root' && n.path === '$')).toBe(true);
    expect(graph.nodes.find((n) => n.path === '$')?.label).toBe('AgentToolCalled');

    const jsonEdges = graph.edges.filter((e) => e.kind === 'json');
    const keys = jsonEdges.map((e) => e.label).sort();
    expect(keys).toEqual(['_class_uri', '_seq', '_site', '_stored_at', '_uri', 'user_id']);
    expect(jsonEdges.every((e) => e.source === '$')).toBe(true);

    const uriNode = graph.nodes.find((n) => n.path === '$._uri');
    expect(uriNode?.kind).toBe('value');
    expect(uriNode?.label).toBe('evt-1');
    expect(uriNode?.title).toBe('http://ontology.naas.ai/abi/agent/evt-1');
  });

  it('maps nested objects and array items and keeps JSON key edges', () => {
    const graph = buildEventJsonGraph(
      baseEvent({
        _property_uris: { name: 'http://example.com/vocab#name' },
        tags: ['alpha', 'beta'],
      }),
    );

    expect(graph.nodes.find((n) => n.path === '$._property_uris')?.label).toBe('_property_uris');
    expect(graph.nodes.some((n) => n.path === '$._property_uris' && n.kind === 'object')).toBe(
      true,
    );
    expect(graph.nodes.some((n) => n.path === '$._property_uris.name' && n.kind === 'value')).toBe(
      true,
    );
    expect(graph.nodes.find((n) => n.path === '$._property_uris.name')?.label).toBe('name');
    expect(graph.nodes.some((n) => n.path === '$.tags' && n.kind === 'array')).toBe(true);
    expect(graph.nodes.find((n) => n.path === '$.tags[0]')?.label).toBe('alpha');
    expect(graph.edges.some((e) => e.kind === 'json' && e.source === '$.tags' && e.label === '[0]')).toBe(
      true,
    );
    expect(
      graph.edges.some((e) => e.kind === 'json' && e.source === '$._property_uris' && e.label === 'name'),
    ).toBe(true);

    const jsonKinds = ['root', 'object', 'array', 'value'];
    expect(graph.nodes.filter((n) => n.kind !== 'bucket').every((n) => jsonKinds.includes(n.kind))).toBe(
      true,
    );
  });

  it('adds bucket hubs only for mapped columns and omits Unknown', () => {
    const graph = buildEventJsonGraph(
      baseEvent({
        _site: 'deploy.example',
        user_id: 'user-123',
      }),
    );

    const hubs = graph.nodes.filter((n) => n.kind === 'bucket');
    expect(hubs.map((n) => n.label).sort()).toEqual([
      'ICE',
      'Material',
      'Process',
      'Site',
      'Temporal',
    ]);
    expect(hubs.some((n) => n.label === 'Unknown' || n.title === 'Unknown')).toBe(false);
    expect(hubs.some((n) => n.label === 'Quality' || n.label === 'Realizable')).toBe(false);

    expect(graph.nodes.find((n) => n.path === '$._class_uri')?.bucket).toBe('process');
    expect(graph.nodes.find((n) => n.path === '$.user_id')?.bucket).toBe('materialEntity');
    expect(graph.nodes.find((n) => n.path === '$._site')?.bucket).toBe('site');
    expect(graph.nodes.find((n) => n.path === '$._seq')?.bucket).toBe('ice');
    expect(graph.nodes.find((n) => n.path === '$._stored_at')?.bucket).toBe('temporalRegion');
    expect(graph.nodes.find((n) => n.path === '$._uri')?.bucket).toBeNull();

    expect(
      graph.edges.some(
        (e) =>
          e.kind === 'bucket' &&
          e.source === bucketHubId('process') &&
          e.target === '$._class_uri' &&
          e.label === '_class_uri',
      ),
    ).toBe(true);
    expect(
      graph.edges.some(
        (e) => e.kind === 'bucket' && e.source === bucketHubId('materialEntity') && e.target === '$.user_id',
      ),
    ).toBe(true);

    expect(bfoColumnSwatch('process').color).toBe('#22c55e');
    expect(bfoColumnSwatch('ice').color).toBe('#06b6d4');
  });

  it('maps ICE to _uri when seq is missing', () => {
    const graph = buildEventJsonGraph(baseEvent({ _seq: null, _uri: 'http://example.com/e1' }));
    expect(graph.nodes.find((n) => n.path === '$._uri')?.bucket).toBe('ice');
    expect(graph.nodes.find((n) => n.path === '$._seq')).toBeUndefined();
    expect(
      graph.edges.some(
        (e) => e.kind === 'bucket' && e.source === bucketHubId('ice') && e.target === '$._uri',
      ),
    ).toBe(true);
  });

  it('omits null leaves so creator and empty fields do not clutter the tree', () => {
    const graph = buildEventJsonGraph(
      baseEvent({
        creator: null,
        created_by: null,
        prefix: 'assets',
      }),
    );
    expect(graph.nodes.some((n) => n.path === '$.creator')).toBe(false);
    expect(graph.nodes.some((n) => n.path === '$.created_by')).toBe(false);
    expect(graph.edges.some((e) => e.label === 'creator' || e.label === 'created_by')).toBe(false);
    expect(graph.nodes.find((n) => n.path === '$.prefix')?.label).toBe('assets');
  });

  it('omits a bucket hub when that column is Unknown', () => {
    const graph = buildEventJsonGraph(baseEvent());
    const hubLabels = graph.nodes.filter((n) => n.kind === 'bucket').map((n) => n.label);
    expect(hubLabels).toContain('Process');
    expect(hubLabels).toContain('ICE');
    expect(hubLabels).toContain('Temporal');
    expect(hubLabels).not.toContain('Material');
    expect(hubLabels).not.toContain('Site');
    expect(hubLabels).not.toContain('Quality');
    expect(hubLabels).not.toContain('Realizable');
    expect(hubLabels).not.toContain('Unknown');
    expect(graph.nodes.some((n) => n.title === 'Unknown')).toBe(false);
  });

  it('links a Quality hub to every JSON field that fills that column', () => {
    const graph = buildEventJsonGraph(
      baseEvent({
        status: 'ok',
        latency_ms: 12,
      }),
    );
    const qualityHub = graph.nodes.find((n) => n.path === bucketHubId('quality'));
    expect(qualityHub?.kind).toBe('bucket');
    expect(qualityHub?.title).toBe('ok · 12ms');
    const targets = graph.edges
      .filter((e) => e.kind === 'bucket' && e.source === bucketHubId('quality'))
      .map((e) => e.target)
      .sort();
    expect(targets).toEqual(['$.latency_ms', '$.status']);
    expect(graph.nodes.find((n) => n.path === '$.status')?.bucket).toBe('quality');
    expect(graph.nodes.find((n) => n.path === '$.latency_ms')?.bucket).toBe('quality');
  });

  it('keeps SchemaLoaded / ObjectPut payload keys in the JSON tree', () => {
    const schema = buildEventJsonGraph(
      baseEvent({
        _uri: 'http://ontology.naas.ai/abi/triple_store/evt-schema',
        _class_uri: 'http://ontology.naas.ai/abi/triple_store/SchemaLoaded',
        _site: 'localhost',
        filepath: '/ontologies/core.ttl',
        created_at: '2026-09-10T00:36:00Z',
      }),
    );
    expect(schema.nodes.find((n) => n.path === '$')?.label).toBe('SchemaLoaded');
    expect(schema.edges.some((e) => e.kind === 'json' && e.label === 'filepath')).toBe(true);
    expect(schema.nodes.find((n) => n.path === '$._class_uri')?.bucket).toBe('process');
    expect(schema.nodes.find((n) => n.path === '$.filepath')?.bucket).toBeNull();
    expect(schema.nodes.some((n) => n.kind === 'bucket' && n.label === 'Process')).toBe(true);
    expect(schema.nodes.some((n) => n.kind === 'bucket' && n.label === 'Quality')).toBe(false);

    const put = buildEventJsonGraph(
      baseEvent({
        _uri: 'http://ontology.naas.ai/abi/object_storage/evt-put',
        _class_uri: 'http://ontology.naas.ai/abi/object_storage/ObjectPut',
        _site: 'localhost',
        prefix: 'assets',
        key: 'logo.svg',
        size_bytes: 2048,
        created_at: '2026-09-10T00:36:00Z',
      }),
    );
    expect(put.nodes.find((n) => n.path === '$')?.label).toBe('ObjectPut');
    expect(put.nodes.find((n) => n.path === '$.prefix')?.key).toBe('prefix');
    expect(put.nodes.find((n) => n.path === '$.prefix')?.label).toBe('assets');
    expect(put.nodes.find((n) => n.path === '$._class_uri')?.key).toBe('_class_uri');
    expect(put.edges.filter((e) => e.kind === 'json').map((e) => e.label)).toEqual(
      expect.arrayContaining(['prefix', 'key', 'size_bytes', '_class_uri']),
    );
    expect(put.nodes.find((n) => n.path === '$.key')?.bucket).toBeNull();
    expect(put.nodes.find((n) => n.path === '$.prefix')?.bucket).toBeNull();
    expect(put.nodes.some((n) => n.kind === 'bucket' && n.label === 'Material entity')).toBe(false);
    expect(put.nodes.some((n) => n.kind === 'bucket' && n.label === 'Process')).toBe(true);
    expect(put.nodes.some((n) => n.kind === 'bucket' && n.label === 'Site')).toBe(true);
  });

  it('caps JSON node count and marks truncated', () => {
    const extra: Record<string, string> = {};
    for (let i = 0; i < GRAPH_MAX_NODES; i += 1) extra[`k${i}`] = `v${i}`;
    const graph = buildEventJsonGraph(baseEvent(extra));
    expect(graph.truncated).toBe(true);
    expect(graph.nodes.filter((n) => n.kind !== 'bucket').length).toBe(GRAPH_MAX_NODES);
  });
});

describe('eventForGraph', () => {
  const newer = baseEvent({ _uri: 'evt-new', _seq: 2 });
  const older = baseEvent({ _uri: 'evt-old', _seq: 1 });

  it('uses selectedUri when that event is in the list', () => {
    expect(eventForGraph([newer, older], 'evt-old')?._uri).toBe('evt-old');
  });

  it('falls back to the newest list entry when nothing is selected', () => {
    expect(eventForGraph([newer, older], null)?._uri).toBe('evt-new');
  });

  it('returns null when the list is empty', () => {
    expect(eventForGraph([], null)).toBeNull();
    expect(eventForGraph([], 'missing')).toBeNull();
  });
});
