import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { browserInstanceImageSrc, instanceImageValue } from './instance-image';

const LOGO = 'http://ontology.naas.ai/nexus/logo_url';
const DEPICTION = 'http://xmlns.com/foaf/0.1/depiction';
const IMAGE = 'http://schema.org/image';
const HAS_DEPICTION = 'http://example.org/onto/hasDepiction';
const DEPICTION_PATH = 'http://example.org/onto/hasDepictionPath';

describe('instanceImageValue', () => {
  it('prefers logo_url over other depiction predicates', () => {
    assert.equal(instanceImageValue({
      dataProperties: [
        { predicate_uri: DEPICTION_PATH, predicate_label: 'depiction path', value: 'src/mod/apps/site/a.png' },
        { predicate_uri: LOGO, predicate_label: 'logo url', value: 'https://cdn.example/face.png' },
      ],
    }), 'https://cdn.example/face.png');
  });

  it('prefers a fetchable path over a file URI for the same portrait', () => {
    assert.equal(instanceImageValue({
      dataProperties: [
        { predicate_uri: LOGO, value: 'file:///tmp/host/src/mod/apps/site/a.png' },
        { predicate_uri: DEPICTION_PATH, predicate_label: 'has depiction path', value: 'src/mod/apps/site/a.png' },
      ],
      relations: [
        { predicate_uri: HAS_DEPICTION, predicate_label: 'has depiction', other_uri: 'file:///tmp/host/src/mod/apps/site/a.png' },
        { predicate_uri: DEPICTION, other_uri: 'file:///tmp/host/src/mod/apps/site/a.png' },
        { predicate_uri: IMAGE, other_uri: 'file:///tmp/host/src/mod/apps/site/a.png' },
      ],
    }), 'src/mod/apps/site/a.png');
  });

  it('reads flattened graph properties including spaced keys', () => {
    assert.equal(instanceImageValue({
      properties: { 'logo url': 'https://cdn.example/mark.png' },
    }), 'https://cdn.example/mark.png');
  });

  it('returns nothing when there is no image predicate', () => {
    assert.equal(instanceImageValue({
      dataProperties: [{ predicate_uri: 'http://www.w3.org/2000/01/rdf-schema#label', value: 'Ada' }],
      relations: [{ predicate_uri: 'http://example.org/memberOf', other_uri: 'http://example.org/Team' }],
    }), undefined);
  });
});

describe('browserInstanceImageSrc', () => {
  it('proxies file URIs and repo-relative paths through the image route', () => {
    assert.equal(
      browserInstanceImageSrc('file:///Users/dev/repo/src/mod/apps/site/a.png'),
      '/api/image-data?raw=1&url=' + encodeURIComponent('file:///Users/dev/repo/src/mod/apps/site/a.png'),
    );
    assert.equal(
      browserInstanceImageSrc('src/mod/apps/site/a.png'),
      '/api/image-data?raw=1&url=' + encodeURIComponent('src/mod/apps/site/a.png'),
    );
  });

  it('keeps same-origin app and api paths', () => {
    assert.equal(browserInstanceImageSrc('/app-html/mod/demo/avatar.png'), '/app-html/mod/demo/avatar.png');
    assert.equal(browserInstanceImageSrc('/api/files/raw/portrait.png'), '/api/files/raw/portrait.png');
  });

  it('leaves public http URLs unchanged', () => {
    assert.equal(browserInstanceImageSrc('https://cdn.example/face.png'), 'https://cdn.example/face.png');
  });
});
