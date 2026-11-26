import { describe, expect, it } from 'vitest';
import { blankTopic } from '@/lib/search-topics';
import { FEATURE_SCOPES, WEB_ENGINES } from '@/lib/search-scopes';
import {
  searchCellValues,
  searchEntries,
  searchExportRow,
  searchSearchTexts,
  searchSortValue,
} from './search-settings-model';

const people = { ...blankTopic('people'), plural_label: 'People', source: 'builtin' as const };
const projects = { ...blankTopic('project'), plural_label: 'Projects', enabled: false };

function entries({ off = [] as string[], featureOn = true } = {}) {
  return searchEntries({
    topics: [people, projects],
    drafts: new Set(['project']),
    disabledScopes: off,
    featureOn: () => featureOn,
  });
}

describe('the rows of Settings › Search', () => {
  it('lists topics, then the Nexus features, then the web engines', () => {
    const rows = entries();
    expect(rows.map((row) => row.kind)).toEqual([
      'topic',
      'topic',
      ...FEATURE_SCOPES.map(() => 'feature'),
      ...WEB_ENGINES.map(() => 'engine'),
    ]);
    expect(rows.at(-1)?.id).toBe(`web.${WEB_ENGINES.at(-1)!.id}`);
  });

  it('types a topic by where it comes from, Draft while it is not saved', () => {
    const [builtin, draft] = entries();
    expect(searchCellValues(builtin!, 'type')).toEqual(['Built-in']);
    expect(searchCellValues(draft!, 'type')).toEqual(['Draft']);
    expect(searchCellValues(draft!, 'enabled')).toEqual(['Disabled']);
  });

  it('a feature off in the workspace is never on, and says why', () => {
    const scope = FEATURE_SCOPES[0]!;
    const off = entries({ featureOn: false }).find((row) => row.id === scope.id)!;
    expect(searchCellValues(off, 'enabled')).toEqual(['Disabled']);
    expect(off.description).toContain('feature is off in this workspace');
    const disabled = entries({ off: [scope.id] }).find((row) => row.id === scope.id)!;
    expect(disabled.on).toBe(false);
    expect(entries().find((row) => row.id === scope.id)!.on).toBe(true);
  });

  it('sorts groups as listed, filters and searches on group and type', () => {
    const rows = entries();
    const [topic] = rows;
    const engine = rows.at(-1)!;
    expect(searchSortValue(topic!, 'group')).toBeLessThan(searchSortValue(engine, 'group') as number);
    expect(searchCellValues(engine, 'group')).toEqual(['Web']);
    expect(searchSearchTexts(engine)).toContain('Web engine');
    expect(searchSearchTexts(engine).join(' ')).toContain('the query leaves Nexus');
  });

  it('exports a row as the table shows it', () => {
    expect(searchExportRow(entries()[0]!)).toEqual(['People', 'people', 'Custom', 'Built-in', 'Yes']);
  });
});
