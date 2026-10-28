import { describe, expect, it } from 'vitest';
import { TASK_SCOPES } from '@/lib/tasks';
import { reorderScopes } from './scope-tabs';

describe('reorderScopes', () => {
  it('drops a tab after a tab to its right and before a tab to its left', () => {
    expect(reorderScopes(TASK_SCOPES, 'last', 'next')).toEqual(['inbox', 'backlog', 'current', 'next', 'last']);
    expect(reorderScopes(TASK_SCOPES, 'next', 'backlog')).toEqual(['inbox', 'next', 'backlog', 'last', 'current']);
  });

  it('leaves the order alone when a tab is dropped on itself', () => {
    expect(reorderScopes(TASK_SCOPES, 'inbox', 'inbox')).toBe(TASK_SCOPES);
  });
});
