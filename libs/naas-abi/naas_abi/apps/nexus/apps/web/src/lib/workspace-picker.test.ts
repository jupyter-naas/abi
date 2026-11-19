import { describe, expect, it } from 'vitest';

import {
  filterWorkspaces,
  groupByOrganization,
  groupWorkspaces,
  hasWorkspaceGroups,
  listWorkspaces,
  OTHERS_GROUP,
  PERSONAL_ORGANIZATION,
  pushRecentWorkspaceId,
  spansOrganizations,
} from './workspace-picker';

const ws = (id: string, name: string) => ({ id, name });
const list = [ws('c', 'Gamma'), ws('a', 'Alpha'), ws('b', 'Beta')];

describe('filterWorkspaces', () => {
  it('returns all when the query is empty', () => {
    expect(filterWorkspaces(list, '  ')).toEqual(list);
  });

  it('matches name case-insensitively', () => {
    expect(filterWorkspaces(list, 'alpha')).toEqual([ws('a', 'Alpha')]);
  });
});

describe('listWorkspaces', () => {
  it('returns one alphabetical list', () => {
    expect(listWorkspaces(list, '')).toEqual([
      ws('a', 'Alpha'),
      ws('b', 'Beta'),
      ws('c', 'Gamma'),
    ]);
  });

  it('keeps the same order after a different workspace is current', () => {
    const before = listWorkspaces(list, '');
    const afterSwitch = listWorkspaces(
      [ws('b', 'Beta'), ws('c', 'Gamma'), ws('a', 'Alpha')],
      '',
    );
    expect(afterSwitch.map((w) => w.id)).toEqual(before.map((w) => w.id));
  });

  it('filters the same list without splitting sections', () => {
    expect(listWorkspaces(list, 'alp')).toEqual([ws('a', 'Alpha')]);
  });
});

describe('pushRecentWorkspaceId', () => {
  it('puts the previous workspace first and drops the destination', () => {
    expect(pushRecentWorkspaceId(['b'], 'a', 'c')).toEqual(['a', 'b']);
  });

  it('does not record a no-op switch', () => {
    expect(pushRecentWorkspaceId(['b'], 'a', 'a')).toEqual(['b']);
  });
});


describe('groupWorkspaces', () => {
  const ws = (name: string, group?: string | null) => ({ id: name, name, group });

  it('lists named groups alphabetically, then Others for workspaces without a group', () => {
    const grouped = groupWorkspaces([
      ws('ABI'),
      ws('Allianz', 'Key Accounts'),
      ws('EDF', 'Forvis Mazars France'),
      ws('Core Team', '  '),
      ws('Orange', 'Key Accounts'),
    ]);
    expect(grouped.map((g) => [g.group, g.workspaces.map((w) => w.name)])).toEqual([
      ['Forvis Mazars France', ['EDF']],
      ['Key Accounts', ['Allianz', 'Orange']],
      [OTHERS_GROUP, ['ABI', 'Core Team']],
    ]);
  });

  it('returns nothing for no workspaces', () => {
    expect(groupWorkspaces([])).toEqual([]);
  });
});

describe('hasWorkspaceGroups', () => {
  const ws = (name: string, group?: string | null) => ({ id: name, name, group });

  it('needs no headings when no workspace has a group', () => {
    expect(hasWorkspaceGroups([ws('JOE'), ws('Core', '  '), ws('Ops', null)])).toBe(false);
    expect(hasWorkspaceGroups([])).toBe(false);
  });

  it('needs headings once one workspace has a group', () => {
    expect(hasWorkspaceGroups([ws('JOE'), ws('Allianz', 'Key Accounts')])).toBe(true);
  });
});

describe('filterWorkspaces with groups', () => {
  it('matches the group name too', () => {
    const list = [
      { id: '1', name: 'Orange', group: 'Key Accounts' },
      { id: '2', name: 'ABI', group: null },
    ];
    expect(listWorkspaces(list, 'key acc').map((w) => w.name)).toEqual(['Orange']);
  });
});

describe('organizations', () => {
  const ws = (
    name: string,
    organizationId: string | null,
    organizationName: string | null,
    group?: string,
  ) => ({ id: name, name, group, organizationId, organizationName });
  const acme = (name: string, group?: string) => ws(name, 'org-a', 'Acme', group);
  const globex = (name: string, group?: string) => ws(name, 'org-g', 'Globex', group);
  const personal = (name: string) => ws(name, null, null);

  it('needs headings only when the workspaces span more than one organization', () => {
    expect(spansOrganizations([acme('One'), acme('Two')])).toBe(false);
    expect(spansOrganizations([personal('Mine')])).toBe(false);
    expect(spansOrganizations([acme('One'), globex('Two')])).toBe(true);
    expect(spansOrganizations([acme('One'), personal('Mine')])).toBe(true);
  });

  it('keeps two organizations\' groups of the same name apart', () => {
    const sections = groupByOrganization([
      acme('Paris', 'Operations'),
      globex('Berlin', 'Operations'),
      acme('Lyon', 'Operations'),
    ]);
    expect(
      sections.map((s) => [s.name, s.groups.map((g) => [g.group, g.workspaces.map((w) => w.name)])]),
    ).toEqual([
      ['Acme', [['Operations', ['Paris', 'Lyon']]]],
      ['Globex', [['Operations', ['Berlin']]]],
    ]);
  });

  it('puts the current organization first, the others alphabetically, Personal last', () => {
    const sections = groupByOrganization(
      [personal('Mine'), acme('One'), globex('Two'), ws('Three', 'org-b', 'Beta')],
      'org-g',
    );
    expect(sections.map((s) => s.name)).toEqual(['Globex', 'Acme', 'Beta', PERSONAL_ORGANIZATION]);
    expect(sections.at(-1)?.organizationId).toBeNull();
  });

  it('names an organization by its id when its name is unknown', () => {
    expect(groupByOrganization([ws('One', 'org-x', null)])[0].name).toBe('org-x');
  });

  it('finds workspaces by their organization\'s name', () => {
    const list = [acme('One'), globex('Two')];
    expect(filterWorkspaces(list, 'glob').map((w) => w.name)).toEqual(['Two']);
  });
});
