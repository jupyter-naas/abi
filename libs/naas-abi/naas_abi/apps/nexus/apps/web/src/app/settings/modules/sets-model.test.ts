import { describe, expect, it } from 'vitest';
import { catalog, crm, people } from './sets-fixtures';
import {
  coverage,
  displayCoverage,
  expandModule,
  listCovers,
  materialise,
  moduleCoverage,
  moduleMatches,
  outsideOfBound,
  partSummary,
  rowOutside,
  sameParts,
  toggleRow,
  withinBound,
  type SetRow,
} from './sets-model';

const everything = { modules: null, features: null };
const recruiter: SetRow = { kind: 'item', module: 'acme.people', type: 'agent', name: 'Recruiter' };
const directory: SetRow = { kind: 'item', module: 'acme.people', type: 'app', name: 'Directory' };
const report: SetRow = { kind: 'action', module: 'acme.people', action: 'acme_people:ExportReport' };
const peopleRow: SetRow = { kind: 'module', module: 'acme.people' };
const crmRow: SetRow = { kind: 'module', module: 'acme.crm' };

describe('contains', () => {
  it('holds everything when nothing is recorded, nothing when the list is empty', () => {
    expect(coverage(everything, recruiter, catalog)).toBe('all');
    expect(coverage(everything, { kind: 'feature', feature: 'files' }, catalog)).toBe('all');
    expect(coverage({ modules: [], features: [] }, peopleRow, catalog)).toBe('none');
    expect(coverage({ modules: [], features: [] }, { kind: 'feature', feature: 'chat' }, catalog)).toBe('none');
  });

  it('holds every item and declared action of a whole module', () => {
    const parts = { modules: ['acme.people'], features: null };
    expect(coverage(parts, peopleRow, catalog)).toBe('all');
    expect(coverage(parts, recruiter, catalog)).toBe('all');
    expect(coverage(parts, report, catalog)).toBe('all');
    expect(coverage(parts, crmRow, catalog)).toBe('none');
  });

  it('holds a module in part through one item, a wildcard or an action', () => {
    expect(moduleCoverage(['agent/acme.people/Recruiter'], people)).toBe('some');
    expect(moduleCoverage(['acme_people:ExportReport'], people)).toBe('some');
    expect(listCovers(['agent/acme.people/*'], 'agent/acme.people/Coach', catalog)).toBe(true);
    expect(listCovers(['agent/acme.people/*'], 'app/acme.people/Directory', catalog)).toBe(false);
    expect(moduleCoverage(['agent/acme.peoplex/A'], people)).toBe('none');
  });
});

describe('toggle', () => {
  it('checks a whole module as `<module>`, dropping its single items', () => {
    const parts = { modules: ['agent/acme.people/Recruiter', 'acme.crm'], features: null };
    expect(toggleRow(parts, peopleRow, true, catalog).modules).toEqual(['acme.crm', 'acme.people']);
    expect(toggleRow(parts, peopleRow, false, catalog).modules).toEqual(['acme.crm']);
  });

  it('unchecking one item of a whole module lists the others instead', () => {
    const next = toggleRow({ modules: ['acme.people'], features: null }, recruiter, false, catalog);
    expect(next.modules).toEqual([
      'agent/acme.people/Coach',
      'app/acme.people/*',
      'acme_people:ExportReport',
    ]);
    expect(next.features).toBeNull();
  });

  it('unchecking a declared action of a whole module keeps every item type whole', () => {
    const next = toggleRow({ modules: ['acme.people'], features: [] }, report, false, catalog);
    expect(next.modules).toEqual(['agent/acme.people/*', 'app/acme.people/*']);
  });

  it('unchecking one item of a wildcard lists the others by name', () => {
    const next = toggleRow({ modules: ['agent/acme.people/*'], features: [] }, recruiter, false, catalog);
    expect(next.modules).toEqual(['agent/acme.people/Coach']);
  });

  it('checking the last item of a type collapses to a wildcard', () => {
    const next = toggleRow({ modules: ['agent/acme.people/Coach'], features: [] }, recruiter, true, catalog);
    expect(next.modules).toEqual(['agent/acme.people/*']);
    const app = toggleRow({ modules: [], features: [] }, directory, true, catalog);
    expect(app.modules).toEqual(['app/acme.people/*']);
  });

  it('checks and unchecks a declared action', () => {
    expect(toggleRow({ modules: [], features: [] }, report, true, catalog).modules).toEqual([
      'acme_people:ExportReport',
    ]);
    expect(toggleRow({ modules: ['acme_people:ExportReport'], features: [] }, report, false, catalog).modules).toEqual(
      [],
    );
  });

  it('unchecking from everything materialises everything first', () => {
    const next = toggleRow(everything, crmRow, false, catalog);
    expect(next).toEqual({ modules: ['acme.people'], features: null });
    const feature = toggleRow(everything, { kind: 'feature', feature: 'files' }, false, catalog);
    expect(feature).toEqual({ modules: null, features: ['chat', 'apps'] });
  });

  it('a workspace materialises its organization’s set, not everything', () => {
    const bound = { modules: ['acme.people'], features: ['chat', 'files'] };
    expect(toggleRow(everything, recruiter, false, catalog, bound).modules).toEqual([
      'agent/acme.people/Coach',
      'app/acme.people/*',
      'acme_people:ExportReport',
    ]);
    expect(toggleRow(everything, { kind: 'feature', feature: 'chat' }, false, catalog, bound).features).toEqual([
      'files',
    ]);
  });

  it('keeps features in the deployment’s order', () => {
    const next = toggleRow({ modules: null, features: ['apps'] }, { kind: 'feature', feature: 'chat' }, true, catalog);
    expect(next.features).toEqual(['chat', 'apps']);
  });

  it('leaves entries of modules the catalog no longer knows alone', () => {
    const next = toggleRow({ modules: ['gone.module', 'acme.people'], features: [] }, recruiter, false, catalog);
    expect(next.modules).toContain('gone.module');
  });
});

describe('materialise', () => {
  it('makes both parts explicit from the bound, else the catalog', () => {
    expect(materialise(everything, null, catalog)).toEqual({
      modules: ['acme.people', 'acme.crm'],
      features: ['chat', 'files', 'apps'],
    });
    expect(materialise(everything, { modules: ['acme.crm'], features: null }, catalog)).toEqual({
      modules: ['acme.crm'],
      features: ['chat', 'files', 'apps'],
    });
    expect(expandModule(crm)).toEqual(['agent/acme.crm/*', 'workflow/acme.crm/*']);
  });
});

describe('intersection with the organization', () => {
  const org = { modules: ['acme.people'], features: ['chat'] };

  it('a workspace shows its organization’s set where it records nothing', () => {
    expect(displayCoverage(everything, org, crmRow, catalog)).toBe('none');
    expect(displayCoverage(everything, org, peopleRow, catalog)).toBe('all');
    expect(displayCoverage(everything, org, { kind: 'feature', feature: 'files' }, catalog)).toBe('none');
    expect(displayCoverage(everything, null, crmRow, catalog)).toBe('all');
  });

  it('offers only what the organization has', () => {
    expect(withinBound(org, peopleRow, catalog)).toBe(true);
    expect(withinBound(org, crmRow, catalog)).toBe(false);
    expect(withinBound({ modules: ['agent/acme.people/Recruiter'], features: null }, peopleRow, catalog)).toBe(false);
    expect(withinBound({ modules: ['agent/acme.people/Recruiter'], features: null }, recruiter, catalog)).toBe(true);
    expect(withinBound(null, crmRow, catalog)).toBe(true);
  });

  it('marks what a workspace records outside its organization', () => {
    const ws = { modules: ['acme.people', 'acme.crm'], features: ['chat', 'files'] };
    expect(rowOutside(ws, org, crmRow, catalog)).toBe(true);
    expect(rowOutside(ws, org, { kind: 'item', module: 'acme.crm', type: 'agent', name: 'Sales' }, catalog)).toBe(true);
    expect(rowOutside(ws, org, peopleRow, catalog)).toBe(false);
    expect(rowOutside(ws, org, { kind: 'feature', feature: 'files' }, catalog)).toBe(true);
    expect(rowOutside(ws, org, { kind: 'feature', feature: 'chat' }, catalog)).toBe(false);
    expect(rowOutside(everything, org, crmRow, catalog)).toBe(false);
    expect(outsideOfBound(ws, org, catalog)).toEqual(['acme.crm', 'feature files']);
  });

  it('a whole module is outside an organization that has only part of it', () => {
    const partial = { modules: ['agent/acme.people/Recruiter'], features: null };
    const ws = { modules: ['acme.people'], features: null };
    expect(rowOutside(ws, partial, peopleRow, catalog)).toBe(true);
    expect(rowOutside(ws, partial, recruiter, catalog)).toBe(false);
    expect(rowOutside(ws, partial, directory, catalog)).toBe(true);
    expect(outsideOfBound(ws, partial, catalog)).toEqual(['acme.people']);
  });
});

describe('helpers', () => {
  it('compares sets regardless of order', () => {
    expect(sameParts({ modules: ['a', 'b'], features: null }, { modules: ['b', 'a'], features: null })).toBe(true);
    expect(sameParts({ modules: null, features: null }, { modules: [], features: null })).toBe(false);
  });

  it('sums a part up', () => {
    expect(partSummary(everything, 'modules', catalog)).toBe('Everything');
    expect(partSummary({ modules: [], features: [] }, 'features', catalog)).toBe('Nothing');
    expect(partSummary({ modules: ['agent/acme.crm/Sales'], features: null }, 'modules', catalog)).toBe('1 of 2');
    expect(partSummary({ modules: null, features: ['chat'] }, 'features', catalog)).toBe('1 of 3');
  });

  it('filters modules by id, item or action', () => {
    expect(moduleMatches(people, 'recruit')).toBe(true);
    expect(moduleMatches(people, 'exportreport')).toBe(true);
    expect(moduleMatches(crm, 'recruit')).toBe(false);
    expect(moduleMatches(crm, '  ')).toBe(true);
  });
});

describe('wildcards of every module', () => {
  const seeded = {
    modules: ['agent/acme.people/Recruiter', 'app/*/*', 'workflow/*/*', 'pipeline/*/*', '*:*'],
    features: null,
  };
  const sales: SetRow = { kind: 'item', module: 'acme.crm', type: 'agent', name: 'Sales' };
  const sync: SetRow = { kind: 'item', module: 'acme.crm', type: 'workflow', name: 'Sync' };

  it('reads them as covering every module of their kind', () => {
    expect(coverage(seeded, recruiter, catalog)).toBe('all');
    expect(coverage(seeded, directory, catalog)).toBe('all');
    expect(coverage(seeded, report, catalog)).toBe('all');
    expect(coverage(seeded, sync, catalog)).toBe('all');
    expect(coverage(seeded, sales, catalog)).toBe('none');
    // People: Coach is out, so some of it; CRM: its workflow but not its agent.
    expect(moduleCoverage(seeded.modules, people)).toBe('some');
    expect(moduleCoverage(seeded.modules, crm)).toBe('some');
    expect(listCovers(['acme_people:*'], 'acme_people:ExportReport', catalog)).toBe(true);
  });

  it('lists them per module once the column is edited', () => {
    const next = toggleRow(seeded, sales, true, catalog);
    expect(next.modules).toEqual(
      expect.arrayContaining([
        'agent/acme.people/Recruiter',
        // CRM's only agent: listed as all of them.
        'agent/acme.crm/*',
        'app/acme.people/*',
        'workflow/acme.crm/*',
        'acme_people:ExportReport',
      ]),
    );
    expect(next.modules).not.toContain('*:*');
    expect(next.modules).not.toContain('app/*/*');
  });
});
