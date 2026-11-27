import { describe, expect, it } from 'vitest';
import {
  resourceCellValues,
  resourceColumns,
  resourceExportHeaders,
  resourceExportRow,
  resourceRows,
  resourceSearchTexts,
  type ResourceEntry,
} from './resource-access-model';

const entry = (over: Partial<ResourceEntry> & Pick<ResourceEntry, 'id'>): ResourceEntry => ({
  name: over.id,
  description: '',
  available: true,
  ...over,
});

const people = entry({ id: 'people', name: 'People' });
const schema = entry({ id: 'schema', name: 'Schema', read_only: true });
const mine = entry({ id: 'mine', name: 'Mine', owned: true });
const gone = entry({ id: 'gone', name: 'Gone', available: false });

describe('what the draft gives each resource', () => {
  it('ontologies: enabled or not', () => {
    const [on, off] = resourceRows('ontologies', [people, gone], { enabled: ['people'] });
    expect([on!.access, off!.access]).toEqual(['enabled', 'disabled']);
    expect(resourceCellValues(on!, 'enabled')).toEqual(['Enabled']);
    expect(resourceCellValues(off!, 'availability')).toEqual(['Unavailable']);
  });

  it('graphs: edit, read or none; a read-only graph is never editable; owned graphs when included', () => {
    const rows = resourceRows('graphs', [people, schema, mine, gone], {
      read: ['gone', 'schema'],
      write: ['people', 'schema'],
      include_owned: true,
    });
    expect(rows.map((row) => row.access)).toEqual(['edit', 'read', 'edit', 'read']);
    const [, readOnly] = rows;
    expect(resourceCellValues(readOnly!, 'read')).toEqual(['Yes']);
    expect(resourceCellValues(readOnly!, 'edit')).toEqual(['No']);
    expect(resourceRows('graphs', [mine], {})[0]!.access).toBe('none');
    expect(resourceRows('graphs', [people], { read_all: true })[0]!.access).toBe('read');
  });
});

describe('the resource table (as Settings › Users)', () => {
  it('has the columns of its kind', () => {
    expect(resourceColumns('ontologies').map((c) => c.id)).toEqual(['name', 'enabled', 'availability']);
    expect(resourceColumns('graphs').map((c) => c.id)).toEqual(['name', 'read', 'edit', 'availability']);
  });

  it('searches the name, the description, the access and the availability', () => {
    const [row] = resourceRows('graphs', [{ ...gone, description: 'Old data' }], { read: ['gone'] });
    expect(resourceSearchTexts(row!)).toEqual(['Gone', 'Old data', 'Read only', 'Unavailable']);
  });

  it('exports a row as the table shows it', () => {
    const [graph] = resourceRows('graphs', [people], { write: ['people'] });
    expect(resourceExportHeaders('graphs')).toHaveLength(resourceExportRow('graphs', graph!).length);
    expect(resourceExportRow('graphs', graph!)).toEqual(['People', 'people', '', 'Yes', 'Yes', 'Available']);
    const [ontology] = resourceRows('ontologies', [people], {});
    expect(resourceExportRow('ontologies', ontology!)).toEqual(['People', 'people', '', 'No', 'Available']);
  });
});
