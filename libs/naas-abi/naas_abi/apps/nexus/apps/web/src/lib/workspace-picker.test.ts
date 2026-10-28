import { describe, expect, it } from 'vitest';

import {
  filterWorkspaces,
  groupWorkspaces,
  listWorkspaces,
  OTHERS_GROUP,
  pushRecentWorkspaceId,
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

describe('filterWorkspaces with groups', () => {
  it('matches the group name too', () => {
    const list = [
      { id: '1', name: 'Orange', group: 'Key Accounts' },
      { id: '2', name: 'ABI', group: null },
    ];
    expect(listWorkspaces(list, 'key acc').map((w) => w.name)).toEqual(['Orange']);
  });
});
