import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { resolveInstanceDisplayTitle, uriLocalName } from './instance-display-title';

const URI = 'http://example.org/onto/Person-AdaLovelace';
const LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';
const PREF = 'http://www.w3.org/2004/02/skos/core#prefLabel';
const NAME = 'http://xmlns.com/foaf/0.1/name';
const JOB = 'http://schema.org/jobTitle';

describe('uriLocalName', () => {
  it('returns the fragment after the last slash or hash', () => {
    assert.equal(uriLocalName(URI), 'Person-AdaLovelace');
    assert.equal(uriLocalName('http://example.org/onto#Term'), 'Term');
  });
});

describe('resolveInstanceDisplayTitle', () => {
  it('prefers rdfs:label over the IRI local name on the API label field', () => {
    assert.equal(
      resolveInstanceDisplayTitle({
        uri: URI,
        label: 'Person-AdaLovelace',
        dataProperties: [
          { predicate_uri: LABEL, predicate_label: 'label', value: 'Ada Lovelace' },
          { predicate_uri: JOB, predicate_label: 'job title', value: 'Mathematician' },
        ],
      }),
      'Ada Lovelace',
    );
  });

  it('uses prefLabel when rdfs:label is missing', () => {
    assert.equal(
      resolveInstanceDisplayTitle({
        uri: URI,
        label: 'Person-AdaLovelace',
        dataProperties: [{ predicate_uri: PREF, predicate_label: 'preferred label', value: 'Ada' }],
      }),
      'Ada',
    );
  });

  it('uses a name property after label predicates', () => {
    assert.equal(
      resolveInstanceDisplayTitle({
        uri: URI,
        label: 'Person-AdaLovelace',
        properties: { [NAME]: 'Ada King' },
      }),
      'Ada King',
    );
  });

  it('keeps a real API label when no title triples are present', () => {
    assert.equal(
      resolveInstanceDisplayTitle({
        uri: URI,
        label: 'Ada Lovelace',
      }),
      'Ada Lovelace',
    );
  });

  it('falls back to the IRI local name when nothing else is a display label', () => {
    assert.equal(
      resolveInstanceDisplayTitle({
        uri: URI,
        label: 'Person-AdaLovelace',
        dataProperties: [{ predicate_uri: JOB, value: 'Mathematician' }],
      }),
      'Person-AdaLovelace',
    );
  });
});
