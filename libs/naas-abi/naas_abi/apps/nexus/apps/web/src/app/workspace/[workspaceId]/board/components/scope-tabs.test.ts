import { describe, expect, it } from 'vitest';
import { BOARD_SCOPES } from '@/lib/board';
import { reorderScopes } from './scope-tabs';

describe('reorderScopes', () => {
  it('drops a tab after a tab to its right and before a tab to its left', () => {
    expect(reorderScopes(BOARD_SCOPES, 'current', 'next')).toEqual(['last', 'next', 'current', 'inbox', 'backlog']);
    expect(reorderScopes(BOARD_SCOPES, 'backlog', 'last')).toEqual(['current', 'backlog', 'last', 'next', 'inbox']);
  });

  it('leaves the order alone when a tab is dropped on itself', () => {
    expect(reorderScopes(BOARD_SCOPES, 'inbox', 'inbox')).toBe(BOARD_SCOPES);
  });
});
