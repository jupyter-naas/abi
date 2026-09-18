import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { classDefinitionHref, individualHref, instancePage, instancePageRequest, INSTANCE_PAGE_SIZE } from './graph-instance-browser';

describe('graph instance browsing', () => {
  it('keeps a paged request scoped to one workspace, graph and class', () => {
    const request = instancePageRequest('workspace-a', 'urn:graph:a', 'urn:class:a', 2, '  Alice  ');
    assert.equal(request.workspace_id, 'workspace-a');
    assert.equal(request.graph_uri, 'urn:graph:a');
    assert.deepEqual(request.class_uris, ['urn:class:a']);
    assert.equal(request.offset, 50);
    assert.equal(request.limit, 26);
    assert.equal(request.search, 'Alice');
    assert.equal(request.enrich, false);
  });

  it('uses lookahead without dropping the first instance on the next page', () => {
    const source = Array.from({ length: 51 }, (_, index) => `urn:instance:${index}`);
    const first = instancePage(source.slice(0, 26));
    const second = instancePage(source.slice(25, 51));
    const last = instancePage(source.slice(50));
    assert.equal(first.hasMore, true);
    assert.equal(first.rows.length, INSTANCE_PAGE_SIZE);
    assert.equal(second.hasMore, true);
    assert.equal(last.hasMore, false);
    assert.deepEqual([...first.rows, ...second.rows, ...last.rows], source);
    assert.deepEqual(instancePage([]), { rows: [], hasMore: false });
  });

  it('preserves graph and instance identities, including URI fragments, in full-page links', () => {
    const uri = 'https://example.org/object#Alice & Bob';
    const url = new URL(individualHref('workspace-a', 'urn:graph:a&b', 'urn:class:a#b', uri), 'http://example.test');
    assert.equal(url.pathname, '/workspace/workspace-a/graph/individuals');
    assert.equal(url.searchParams.get('graph'), 'urn:graph:a&b');
    assert.equal(url.searchParams.get('class'), 'urn:class:a#b');
    assert.equal(url.searchParams.get('selected'), uri);
    assert.equal(new URL(individualHref('workspace-a', 'urn:graph:a', ''), url).searchParams.has('class'), false);
  });

  it('opens a class definition in the same workspace dictionary', () => {
    const url = new URL(classDefinitionHref('workspace-b', 'urn:class:a#b'), 'http://example.test');
    assert.equal(url.pathname, '/workspace/workspace-b/ontology');
    assert.deepEqual(Object.fromEntries(url.searchParams), { browser: 'dictionary', view: 'classes', term: 'urn:class:a#b', termType: 'entity' });
  });
});
