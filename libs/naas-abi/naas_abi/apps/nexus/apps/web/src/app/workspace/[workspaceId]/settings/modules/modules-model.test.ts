import { describe, expect, it } from 'vitest';
import { WS, publishedType } from '@/components/access/access-fixtures';
import {
  moduleCellValues,
  moduleExportRow,
  moduleRows,
  moduleSearchTexts,
  offerSummary,
} from './modules-model';

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
