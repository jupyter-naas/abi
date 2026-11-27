import { describe, expect, it } from 'vitest';
import { WS, publishedType } from '@/components/access/access-fixtures';
import {
  groupCellValues,
  groupSearchTexts,
  groupSummary,
  moduleCellValues,
  moduleDrafts,
  moduleExportRow,
  moduleGroups,
  moduleRows,
  moduleRowHref,
  moduleSearchTexts,
  offerSummary,
} from './modules-model';

describe('moduleRowHref', () => {
  it("opens Access › Modules on a module's row, through its search", () => {
    expect(moduleRowHref('ws 1', 'acme.people')).toBe('/workspace/ws%201/settings/modules?module=acme.people');
    expect(moduleRowHref('ws-1', '')).toBe('/workspace/ws-1/settings/modules');
  });
});

const PUBLISHERS = {
  scope: WS,
  publishers: [
    {
      id: 'acme.people',
      kind: 'module' as const,
      types: [
        publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/*']]], { module: 'acme.people' }),
        publishedType('module', 'app', [['module:UseApp', ['${scope}/module:app/acme.people/*']]], { module: 'acme.people' }),
      ],
    },
  ],
};

const OFFERED = {
  agents: [{ module: 'acme.people', name: '*' }],
  apps: [
    { module: 'acme.people', name: 'Roster' },
    { module: 'acme.people', name: 'Hiring' },
  ],
  workflows: [{ module: 'old.module', name: 'Sync' }],
  pipelines: [],
};

describe('the modules of the offer', () => {
  const rows = moduleRows(PUBLISHERS, OFFERED);

  it('is one row per module and kind: what may be given here, and what is already offered', () => {
    expect(rows.map((r) => [r.key, r.offer, r.grantable])).toEqual([
      ['agents|acme.people', 'whole', true],
      ['apps|acme.people', 'items', true],
      ['workflows|old.module', 'items', false],
    ]);
    expect(rows[1].items).toEqual(['Hiring', 'Roster']);
  });

  it('filters, searches, sums up and exports a row as the table shows it', () => {
    expect(moduleCellValues(rows[0], 'offer')).toEqual(['Whole module']);
    expect(moduleCellValues(rows[1], 'kind')).toEqual(['Apps']);
    expect(moduleSearchTexts(rows[1])).toContain('Roster');
    expect(offerSummary(rows[1])).toBe('2 items: Hiring, Roster');
    expect(offerSummary(rows[0])).toBe('Whole module');
    expect(moduleExportRow(rows[1])).toEqual(['acme.people', 'Apps', 'Item by item', 'Hiring; Roster']);
  });

  it('says Not offered for a module that may be given but is not', () => {
    const none = moduleRows(PUBLISHERS, { agents: [], apps: [], workflows: [], pipelines: [] });
    expect(none.map((r) => r.offer)).toEqual(['none', 'none']);
  });
});

describe('one row per module, its contents unfolded under it', () => {
  it('groups a module\'s kinds, offered whole, in part or not', () => {
    const [people] = moduleGroups(PUBLISHERS, OFFERED);
    expect(people.module).toBe('acme.people');
    expect(people.kinds.map((k) => k.kind)).toEqual(['agents', 'apps']);
    // Agents whole, apps item by item: the module is offered in part.
    expect(people.offer).toBe('partial');
    expect(groupSummary(people)).toBe('Agents: whole · Apps: 2 items');
    expect(groupCellValues(people, 'kind')).toEqual(['Agents', 'Apps']);
    expect(groupCellValues(people, 'offer')).toEqual(['In part']);
    expect(groupSearchTexts(people)).toEqual(expect.arrayContaining(['acme.people', 'Agents', 'Apps', 'Roster', 'Hiring']));

    const whole = moduleGroups(PUBLISHERS, { ...OFFERED, apps: [{ module: 'acme.people', name: '*' }] })[0];
    expect(whole.offer).toBe('whole');
    expect(groupSummary(whole)).toBe('Whole module');
    const none = moduleGroups(PUBLISHERS, { agents: [], apps: [], workflows: [], pipelines: [] })[0];
    expect(none.offer).toBe('none');
    expect(groupSummary(none)).toBe('Not offered');
  });

  it('offers a whole module (every kind) or takes all of it back, its items included', () => {
    const [people] = moduleGroups(PUBLISHERS, OFFERED);
    expect(moduleDrafts(people, true)).toEqual({ 'agents|acme.people|*': true, 'apps|acme.people|*': true });
    expect(moduleDrafts(people, false)).toEqual({
      'agents|acme.people|*': false,
      'apps|acme.people|*': false,
      'apps|acme.people|Hiring': false,
      'apps|acme.people|Roster': false,
    });
  });
});
