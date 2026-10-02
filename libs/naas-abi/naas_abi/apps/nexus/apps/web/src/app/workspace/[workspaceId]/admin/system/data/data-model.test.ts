import { describe, expect, it } from 'vitest';
import {
  ROOT_CRUMB,
  appendPage,
  childId,
  compactIri,
  confirmed,
  dayLabel,
  decodeLocation,
  detectLanguage,
  encodeLocation,
  filterEntries,
  formatBytes,
  formatDuration,
  initials,
  openOnPath,
  parseJson,
  relativeTime,
  tail,
} from './data-model';
import type { ResourceEntry } from './data-types';

const entry = (id: string, summary = ''): ResourceEntry => ({
  id,
  name: id.split('/').pop() ?? id,
  kind: 'item',
  actions: ['read'],
  size: null,
  modified: null,
  attributes: summary ? { summary } : {},
});

describe('data model', () => {
  it('records opened containers and cuts back to a crumb', () => {
    const repo = { id: 'acme/site', label: 'site' };
    const dir = { id: 'acme/site/docs', label: 'docs' };
    const path = openOnPath(openOnPath([ROOT_CRUMB], repo), dir);
    expect(path).toEqual([ROOT_CRUMB, repo, dir]);
    expect(openOnPath(path, repo)).toEqual([ROOT_CRUMB, repo]);
    expect(childId('docs', '/a.txt')).toBe('docs/a.txt');
    expect(confirmed('a', 'a') && !confirmed('', '') && !confirmed('A', 'a')).toBe(true);
  });

  it('round-trips the location through query parameters', () => {
    const location = {
      service: 'document',
      path: [ROOT_CRUMB, { id: 'ns', label: 'ns' }, { id: 'ns/coll', label: 'coll' }],
      item: 'ns/coll/doc-1',
    };
    const params = encodeLocation(location, new URLSearchParams('tab=data'));
    expect(params.get('tab')).toBe('data');
    expect(decodeLocation(params)).toEqual(location);
    expect(decodeLocation(new URLSearchParams('in=not-json')).path).toEqual([ROOT_CRUMB]);
  });

  it('filters loaded entries by name, id or summary', () => {
    const entries = [entry('a/alpha'), entry('b/beta', 'mentions gamma'), entry('c/delta')];
    expect(filterEntries(entries, 'GAMMA').map((e) => e.id)).toEqual(['b/beta']);
    expect(filterEntries(entries, '  ')).toHaveLength(3);
    expect(appendPage([entry('x')], [entry('x'), entry('y')]).map((e) => e.id)).toEqual(['x', 'y']);
  });

  it('formats sizes, durations and times', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1536)).toBe('1.5 KB');
    expect(formatBytes(80 * 1024 * 1024)).toBe('80 MB');
    expect(formatDuration(3900)).toBe('1 h 5 min');
    const now = Date.parse('2026-10-02T12:00:00Z');
    expect(relativeTime('2026-10-02T11:59:50Z', now)).toBe('just now');
    expect(relativeTime('2026-10-02T11:30:00Z', now)).toBe('30 min ago');
    expect(relativeTime('2026-10-02T15:00:00Z', now)).toBe('in 3 h');
    expect(relativeTime('2026-10-01T10:00:00Z', now)).toBe('yesterday');
  });

  it('detects languages, JSON and IRIs', () => {
    expect(detectLanguage('src/app.py')).toBe('python');
    expect(detectLanguage('Dockerfile')).toBe('dockerfile');
    expect(detectLanguage('blob', 'application/json')).toBe('json');
    expect(detectLanguage('value', undefined, '{"a": 1}')).toBe('json');
    expect(parseJson('{"a": [1]}')).toEqual({ a: [1] });
    expect(parseJson('plain')).toBeUndefined();
    expect(compactIri('http://www.w3.org/2000/01/rdf-schema#label')).toBe('rdfs:label');
    expect(compactIri('http://x.org/a', { ex: 'http://x.org/' })).toBe('ex:a');
    expect(tail('http://ontology.naas.ai/graph/palantir/')).toBe('palantir');
    expect(initials('ada lovelace')).toBe('AL');
  });

  it('labels days for log separators', () => {
    const now = new Date(2026, 9, 2, 15, 0, 0).getTime();
    expect(dayLabel(new Date(2026, 9, 2, 9, 0).toISOString(), now)).toBe('Today');
    expect(dayLabel(new Date(2026, 9, 1, 23, 0).toISOString(), now)).toBe('Yesterday');
    expect(dayLabel(new Date(2026, 8, 28, 12, 0).toISOString(), now)).toBe('Mon, Sep 28');
    expect(dayLabel(null, now)).toBe('Unknown time');
  });
});
