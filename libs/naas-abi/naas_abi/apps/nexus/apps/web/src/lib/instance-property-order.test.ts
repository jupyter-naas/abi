import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { propertyPriority, sortInstanceProperties } from './instance-property-order';

const LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';
const PREF = 'http://www.w3.org/2004/02/skos/core#prefLabel';
const COMMENT = 'http://www.w3.org/2000/01/rdf-schema#comment';
const JOB = 'http://schema.org/jobTitle';
const HAS_JOB = 'http://example.org/onto/hasJobTitle';
const ENGAGEMENT = 'http://example.org/onto/hasEngagementTitle';
const EMAIL = 'http://example.org/onto/hasEmail';
const BIO = 'http://example.org/onto/hasBiography';

function row(uri: string, label: string, value: string) {
  return { predicate_uri: uri, predicate_label: label, value };
}

describe('propertyPriority', () => {
  it('ranks label, comment, and job title ahead of other fields', () => {
    assert.equal(propertyPriority(LABEL, 'label'), 0);
    assert.equal(propertyPriority(PREF, 'preferred label'), 0);
    assert.equal(propertyPriority(COMMENT, 'comment'), 1);
    assert.equal(propertyPriority('http://purl.org/dc/terms/description', 'description'), 1);
    assert.equal(propertyPriority(HAS_JOB, 'has job title'), 2);
    assert.equal(propertyPriority(JOB, 'job title'), 2);
    assert.equal(propertyPriority(ENGAGEMENT, 'has engagement title'), 3);
    assert.ok(propertyPriority(EMAIL, 'has email') > propertyPriority(JOB, 'job title'));
  });
});

describe('sortInstanceProperties', () => {
  it('puts label, comment, and job title first without dropping rows', () => {
    const input = [
      row(EMAIL, 'has email', 'a@example.com'),
      row(BIO, 'has biography', 'A short bio'),
      row(JOB, 'job title', 'Advisor'),
      row(COMMENT, 'comment', 'Notes'),
      row(LABEL, 'label', 'Ada'),
      row(HAS_JOB, 'has job title', 'Advisor'),
    ];
    const sorted = sortInstanceProperties(input);
    assert.deepEqual(
      sorted.map(item => item.predicate_uri),
      [LABEL, COMMENT, JOB, HAS_JOB, EMAIL, BIO]
    );
    assert.equal(sorted.length, input.length);
  });

  it('keeps original order inside the same rank and for remaining properties', () => {
    const input = [
      row(EMAIL, 'has email', 'a@example.com'),
      row(BIO, 'has biography', 'A short bio'),
      row(COMMENT, 'comment', 'First note'),
      row(COMMENT, 'comment', 'Second note'),
    ];
    const sorted = sortInstanceProperties(input);
    assert.deepEqual(
      sorted.map(item => item.value),
      ['First note', 'Second note', 'a@example.com', 'A short bio']
    );
  });

  it('treats display name as a label and engagement title after job title', () => {
    const input = [
      row(ENGAGEMENT, 'engagement title', 'Partner'),
      row('http://example.org/displayName', 'display name', 'Ada Lovelace'),
    ];
    const sorted = sortInstanceProperties(input);
    assert.deepEqual(
      sorted.map(item => item.predicate_uri),
      ['http://example.org/displayName', ENGAGEMENT]
    );
  });
});
