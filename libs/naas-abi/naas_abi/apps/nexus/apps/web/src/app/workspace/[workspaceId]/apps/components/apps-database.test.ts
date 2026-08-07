import { describe, expect, it } from 'vitest';
import {
  applyFilters,
  applySearch,
  applySort,
  facetValues,
  groupRecords,
  propertyText,
  toRecord,
  toTenantRecord,
  type AppInfo,
  type AppRecord,
  type Filter,
} from './types';

const app = (overrides: Partial<AppInfo> & Pick<AppInfo, 'app_id' | 'name'>): AppInfo => ({
  module_path: 'naas_abi_marketplace.alpha.wsr',
  module_name: 'wsr',
  app_name: 'dashboard',
  category: 'application',
  description: '',
  url: 'https://example.com/app',
  installed: true,
  enabled: true,
  ...overrides,
});

const records: AppRecord[] = [
  toRecord(
    app({
      app_id: 'a',
      name: 'Zulu',
      module_name: 'wsr',
      category: 'application',
      description: 'Weekly status reporting',
      maintainer: 'Florent',
      keywords: ['reporting', 'ops'],
    }),
  ),
  toRecord(
    app({
      app_id: 'b',
      name: 'Alpha',
      module_name: 'intel',
      category: 'ai',
      description: 'Threat intelligence console',
      keywords: ['ops'],
    }),
  ),
  toRecord(
    app({ app_id: 'c', name: 'Mike', module_name: 'intel', category: 'application' }),
  ),
  toTenantRecord({ name: 'Docs', url: 'https://docs.example.com', description: 'External docs' }),
];

const filter = (partial: Omit<Filter, 'id'>): Filter => ({ id: 'f', ...partial });

const names = (rows: AppRecord[]) => rows.map((r) => r.name);

describe('normalisation', () => {
  it('derives the module name from the path when the API omits it', () => {
    const record = toRecord(app({ app_id: 'x', name: 'X', module_name: undefined }));
    expect(record.module).toBe('wsr');
  });

  it('marks tenant apps as external and keeps the URL as the row id', () => {
    const record = toTenantRecord({ name: 'Docs', url: 'https://docs.example.com' });
    expect(record.source).toBe('external');
    expect(record.id).toBe('https://docs.example.com');
    expect(propertyText(record, 'source')).toBe('External');
  });
});

describe('applyFilters', () => {
  it('returns every row when no filter has a value', () => {
    expect(applyFilters(records, [filter({ property: 'category', operator: 'is', value: '' })])).toHaveLength(4);
  });

  it('filters on an exact select value, case-insensitively', () => {
    const rows = applyFilters(records, [filter({ property: 'module', operator: 'is', value: 'Intel' })]);
    expect(names(rows).sort()).toEqual(['Alpha', 'Mike']);
  });

  it('supports negation', () => {
    const rows = applyFilters(records, [filter({ property: 'category', operator: 'is_not', value: 'application' })]);
    expect(names(rows).sort()).toEqual(['Alpha', 'Docs']);
  });

  it('supports contains on text properties', () => {
    const rows = applyFilters(records, [
      filter({ property: 'description', operator: 'contains', value: 'intelligence' }),
    ]);
    expect(names(rows)).toEqual(['Alpha']);
  });

  it('treats a multi-value property as matching when any value matches', () => {
    const rows = applyFilters(records, [filter({ property: 'keywords', operator: 'is', value: 'ops' })]);
    expect(names(rows).sort()).toEqual(['Alpha', 'Zulu']);
  });

  it('finds rows with and without a value', () => {
    expect(names(applyFilters(records, [filter({ property: 'maintainer', operator: 'is_not_empty', value: '' })]))).toEqual(['Zulu']);
    expect(applyFilters(records, [filter({ property: 'maintainer', operator: 'is_empty', value: '' })])).toHaveLength(3);
  });

  it('ands multiple filters together', () => {
    const rows = applyFilters(records, [
      { ...filter({ property: 'module', operator: 'is', value: 'intel' }), id: '1' },
      { ...filter({ property: 'category', operator: 'is', value: 'ai' }), id: '2' },
    ]);
    expect(names(rows)).toEqual(['Alpha']);
  });
});

describe('applySearch', () => {
  it('matches across every property, not just the name', () => {
    expect(names(applySearch(records, 'threat'))).toEqual(['Alpha']);
    expect(names(applySearch(records, 'intel')).sort()).toEqual(['Alpha', 'Mike']);
  });

  it('is a no-op when blank', () => {
    expect(applySearch(records, '   ')).toHaveLength(4);
  });
});

describe('applySort', () => {
  it('defaults to name ascending', () => {
    expect(names(applySort(records, null))).toEqual(['Alpha', 'Docs', 'Mike', 'Zulu']);
  });

  it('reverses on descending', () => {
    expect(names(applySort(records, { property: 'name', direction: 'desc' }))).toEqual([
      'Zulu', 'Mike', 'Docs', 'Alpha',
    ]);
  });

  it('sinks rows missing the sort property to the bottom in both directions', () => {
    const asc = applySort(records, { property: 'maintainer', direction: 'asc' });
    const desc = applySort(records, { property: 'maintainer', direction: 'desc' });
    expect(asc[0].name).toBe('Zulu');
    expect(desc[0].name).toBe('Zulu');
  });

  it('does not mutate the input', () => {
    const input = [...records];
    applySort(input, { property: 'name', direction: 'desc' });
    expect(names(input)).toEqual(['Zulu', 'Alpha', 'Mike', 'Docs']);
  });
});

describe('groupRecords', () => {
  it('returns a single anonymous group when ungrouped', () => {
    const groups = groupRecords(records, null);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('__all__');
    expect(groups[0].records).toHaveLength(4);
  });

  it('splits by a property, alphabetically, with the empty bucket last', () => {
    const groups = groupRecords(records, 'module');
    expect(groups.map((g) => g.key)).toEqual(['intel', 'wsr', '__empty__']);
    expect(groups[2].label).toBe('No module');
    expect(names(groups[2].records)).toEqual(['Docs']);
  });

  it('places a row in every group of a multi-value property', () => {
    const groups = groupRecords(records, 'keywords');
    expect(groups.map((g) => g.key)).toEqual(['ops', 'reporting', '__empty__']);
    expect(names(groups[0].records).sort()).toEqual(['Alpha', 'Zulu']);
    expect(names(groups[1].records)).toEqual(['Zulu']);
  });
});

describe('facetValues', () => {
  it('lists the distinct values a property actually takes', () => {
    expect(facetValues(records, 'category')).toEqual(['ai', 'application', 'external']);
    expect(facetValues(records, 'source')).toEqual(['External', 'Module app']);
  });
});
