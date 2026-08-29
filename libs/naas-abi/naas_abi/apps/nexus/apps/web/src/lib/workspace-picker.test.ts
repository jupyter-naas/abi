import { describe, expect, it } from 'vitest';

import {
  filterWorkspaces,
  listWorkspaces,
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
