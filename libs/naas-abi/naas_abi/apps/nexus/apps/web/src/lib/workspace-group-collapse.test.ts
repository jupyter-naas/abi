import { describe, expect, it } from 'vitest';

import { OTHERS_GROUP } from './workspace-picker';
import {
  defaultWorkspaceGroupCollapsed,
  isWorkspaceGroupExpanded,
  readWorkspaceGroupCollapse,
  writeWorkspaceGroupCollapsed,
  WORKSPACE_GROUP_COLLAPSE_STORAGE_KEY,
} from './workspace-group-collapse';

function memoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear() {
      map.clear();
    },
    getItem(key: string) {
      return map.get(key) ?? null;
    },
    key(index: number) {
      return [...map.keys()][index] ?? null;
    },
    removeItem(key: string) {
      map.delete(key);
    },
    setItem(key: string, value: string) {
      map.set(key, value);
    },
  };
}

describe('defaultWorkspaceGroupCollapsed', () => {
  it('collapses Others by default and expands Demo and named groups', () => {
    expect(defaultWorkspaceGroupCollapsed(OTHERS_GROUP)).toBe(true);
    expect(defaultWorkspaceGroupCollapsed('OTHERS')).toBe(true);
    expect(defaultWorkspaceGroupCollapsed('Demo')).toBe(false);
    expect(defaultWorkspaceGroupCollapsed('Key Accounts')).toBe(false);
  });
});

describe('isWorkspaceGroupExpanded', () => {
  it('respects saved collapse state', () => {
    expect(isWorkspaceGroupExpanded('Demo', { demo: true })).toBe(false);
    expect(isWorkspaceGroupExpanded('Demo', { demo: false })).toBe(true);
  });

  it('forces expanded when searching', () => {
    expect(isWorkspaceGroupExpanded(OTHERS_GROUP, { others: true }, { forceExpanded: true })).toBe(true);
  });
});

describe('workspace group collapse persistence', () => {
  it('stores collapse per organization scope', () => {
    const storage = memoryStorage();
    writeWorkspaceGroupCollapsed('org-a', 'Demo', true, storage);
    expect(readWorkspaceGroupCollapse('org-a', storage)).toEqual({ demo: true });
    expect(readWorkspaceGroupCollapse('org-b', storage)).toEqual({});

    writeWorkspaceGroupCollapsed('org-b', OTHERS_GROUP, false, storage);
    expect(readWorkspaceGroupCollapse('org-b', storage)).toEqual({ others: false });

    const raw = storage.getItem(WORKSPACE_GROUP_COLLAPSE_STORAGE_KEY);
    expect(raw).toContain('org-a');
    expect(raw).toContain('org-b');
  });
});
