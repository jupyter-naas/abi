import { describe, expect, it } from 'vitest';

import {
  filterWorkspaces,
  pushRecentWorkspaceId,
  recentWorkspaces,
} from './workspace-picker';

const ws = (id: string, name: string) => ({ id, name });
const list = [ws('a', 'TPO'), ws('b', 'Valeo'), ws('c', 'Core Team')];

describe('filterWorkspaces', () => {
  it('returns all when the query is empty', () => {
    expect(filterWorkspaces(list, '  ')).toEqual(list);
  });

  it('matches name case-insensitively', () => {
    expect(filterWorkspaces(list, 'tpo')).toEqual([ws('a', 'TPO')]);
  });
});

describe('recentWorkspaces', () => {
  it('skips the current workspace and unknown ids', () => {
    expect(recentWorkspaces(list, ['c', 'a', 'gone'], 'a')).toEqual([ws('c', 'Core Team')]);
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
