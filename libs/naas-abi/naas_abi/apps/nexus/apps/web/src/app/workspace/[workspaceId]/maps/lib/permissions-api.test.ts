import { describe, expect, it } from 'vitest';

import { accessSummary } from './permissions-api';

const NAMES = new Map([
  ['ws-fr', 'Forvis Mazars en France'],
  ['ws-valeo', 'Valeo'],
  ['ws-x', 'X'],
]);

describe('accessSummary', () => {
  it('describes deployment items', () => {
    expect(accessSummary({ owner: '', all_workspaces: true, workspace_ids: [] }, NAMES)).toBe('All workspaces');
    expect(accessSummary({ owner: '', all_workspaces: false, workspace_ids: ['ws-fr', 'ws-valeo'] }, NAMES)).toBe(
      'Forvis Mazars en France, Valeo',
    );
    expect(accessSummary({ owner: '', all_workspaces: false, workspace_ids: ['ws-fr', 'ws-valeo', 'ws-x'] }, NAMES)).toBe(
      '3 workspaces',
    );
    expect(accessSummary({ owner: '', all_workspaces: false, workspace_ids: [] }, NAMES)).toBe('No workspace');
  });

  it('describes custom items from their owner', () => {
    expect(accessSummary({ owner: 'ws-fr', all_workspaces: false, workspace_ids: [] }, NAMES)).toBe(
      'This workspace only',
    );
    expect(accessSummary({ owner: 'ws-fr', all_workspaces: false, workspace_ids: ['ws-valeo'] }, NAMES)).toBe(
      'Shared with Valeo',
    );
  });
});
