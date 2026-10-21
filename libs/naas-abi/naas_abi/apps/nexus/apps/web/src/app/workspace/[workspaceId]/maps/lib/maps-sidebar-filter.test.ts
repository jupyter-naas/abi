import { describe, expect, it } from 'vitest';

import type { LayoutEntry } from './layouts';
import {
  filterSidebarEntries,
  sidebarFeedOptions,
  sidebarFilterLabel,
  sidebarGroupOptions,
  toggleValue,
} from './maps-sidebar-filter';

const entry = (id: string, group: string, feed?: [string, string]): LayoutEntry => ({
  id,
  title: id,
  description: '',
  group,
  icon: 'MapPin',
  order: 0,
  kind: 'workspace',
  combinable: true,
  ...(feed ? { feedId: feed[0], feedTitle: feed[1] } : {}),
});

const ENTRIES = [
  entry('alpha-offices', 'Organizations Facilities', ['alpha', 'Alpha Org']),
  entry('alpha-hq', 'Organizations Facilities', ['alpha', 'Alpha Org']),
  entry('beta-offices', 'Organizations Facilities', ['beta', 'Beta Org']),
  entry('gdacs', 'Environment'),
  entry('notes', ''),
];

describe('sidebar group and feed options', () => {
  it('lists groups (Custom last) and feeds, a plain layer being its own feed', () => {
    expect(sidebarGroupOptions(ENTRIES)).toEqual([
      { value: 'environment', label: 'Environment', detail: '1 feed' },
      { value: 'organizations facilities', label: 'Organizations Facilities', detail: '2 feeds' },
      { value: 'custom', label: 'Custom', detail: '1 feed' },
    ]);
    expect(sidebarFeedOptions(ENTRIES).map((o) => [o.value, o.label, o.detail])).toEqual([
      ['alpha', 'Alpha Org', 'Organizations Facilities · 2 layers'],
      ['beta', 'Beta Org', 'Organizations Facilities · 1 layer'],
      ['gdacs', 'gdacs', 'Environment · 1 layer'],
      ['notes', 'notes', 'Custom · 1 layer'],
    ]);
  });

  it('offers only the feeds of the selected groups', () => {
    expect(sidebarFeedOptions(ENTRIES, ['environment', 'custom']).map((o) => o.value)).toEqual([
      'gdacs',
      'notes',
    ]);
  });
});

describe('filterSidebarEntries', () => {
  it('keeps everything with no selection', () => {
    expect(filterSidebarEntries(ENTRIES, { groups: [], feeds: [] })).toBe(ENTRIES);
  });

  it('keeps entries matching every non-empty selection', () => {
    const ids = (groups: string[], feeds: string[]) =>
      filterSidebarEntries(ENTRIES, { groups, feeds }).map((e) => e.id);
    expect(ids(['organizations facilities'], [])).toEqual(['alpha-offices', 'alpha-hq', 'beta-offices']);
    expect(ids([], ['alpha', 'gdacs'])).toEqual(['alpha-offices', 'alpha-hq', 'gdacs']);
    expect(ids(['environment'], ['alpha'])).toEqual([]);
  });
});

describe('sidebarFilterLabel', () => {
  it('names all, one, or a count', () => {
    const options = sidebarFeedOptions(ENTRIES);
    expect(sidebarFilterLabel([], options, 'feeds')).toBe('All feeds');
    expect(sidebarFilterLabel(['beta'], options, 'feeds')).toBe('Beta Org');
    expect(sidebarFilterLabel(['gone'], options, 'feeds')).toBe('1 feed selected');
    expect(sidebarFilterLabel(['alpha', 'beta'], options, 'feeds')).toBe('2 feeds selected');
  });

  it('toggles a value in or out', () => {
    expect(toggleValue(['a'], 'b')).toEqual(['a', 'b']);
    expect(toggleValue(['a', 'b'], 'a')).toEqual(['b']);
  });
});
