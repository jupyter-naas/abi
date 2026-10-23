import { describe, expect, it } from 'vitest';
import { TASK_SCOPES } from '@/lib/tasks';
import { reorderScopes } from './scope-tabs';

describe('reorderScopes', () => {
  it('drops a tab after a tab to its right and before a tab to its left', () => {
    expect(reorderScopes(TASK_SCOPES, 'current', 'next')).toEqual(['last', 'next', 'current', 'inbox', 'backlog']);
    expect(reorderScopes(TASK_SCOPES, 'backlog', 'last')).toEqual(['current', 'backlog', 'last', 'next', 'inbox']);
  });

  it('leaves the order alone when a tab is dropped on itself', () => {
    expect(reorderScopes(TASK_SCOPES, 'inbox', 'inbox')).toBe(TASK_SCOPES);
  });
});
