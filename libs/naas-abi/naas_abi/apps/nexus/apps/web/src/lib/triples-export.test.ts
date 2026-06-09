import { describe, expect, it } from 'vitest';
import {
  buildPrefixMap,
  groupTriplesBySubject,
  serializeTriples,
  triplesToNTriples,
  triplesToTurtle,
  type ExportTriple,
} from './triples-export';

const RDF_TYPE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

const triples: ExportTriple[] = [
  {
    s: 'http://example.org/ind#1',
    p: RDF_TYPE,
    o: 'http://www.w3.org/2002/07/owl#NamedIndividual',
    isLiteral: false,
  },
  {
    s: 'http://example.org/ind#1',
    p: RDFS_LABEL,
    o: 'Alice',
    isLiteral: true,
  },
];

describe('triplesToNTriples', () => {
  it('emits full URIs for subject, predicate, and object', () => {
    const nt = triplesToNTriples(triples);
    expect(nt).toContain('<http://example.org/ind#1>');
    expect(nt).toContain(`<${RDF_TYPE}>`);
    expect(nt).toContain('<http://www.w3.org/2002/07/owl#NamedIndividual>');
    expect(nt).toContain('"Alice"');
  });
});

describe('triplesToTurtle', () => {
  it('declares standard prefixes and uses prefixed terms', () => {
    const ttl = triplesToTurtle(triples);
    expect(ttl).toContain('@prefix rdf:');
    expect(ttl).toContain('@prefix rdfs:');
    expect(ttl).toContain('@prefix owl:');
    expect(ttl).toContain('rdf:type');
    expect(ttl).toContain('rdfs:label "Alice"');
    expect(ttl).toContain('owl:NamedIndividual');
  });

  it('groups predicates under the same subject with semicolons', () => {
    const ttl = triplesToTurtle(triples);
    expect(ttl).toContain(';');
    expect(groupTriplesBySubject(triples).size).toBe(2);
  });
});

describe('buildPrefixMap', () => {
  it('maps example.org hash namespace to a dedicated prefix', () => {
    const map = buildPrefixMap(triples);
    const exampleNs = 'http://example.org/ind#';
    expect(map.get(exampleNs)).toBeTruthy();
  });
});

describe('serializeTriples', () => {
  it('returns nt, ttl, and owl filenames', () => {
    expect(serializeTriples(triples, 'nt').filename).toBe('triples.nt');
    expect(serializeTriples(triples, 'ttl').filename).toBe('triples.ttl');
    expect(serializeTriples(triples, 'owl').filename).toBe('triples.owl');
  });
});
