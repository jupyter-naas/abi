import { describe, expect, it } from 'vitest';

import { isWorkspaceHome, panelSectionOnPage } from './home-route';

describe('isWorkspaceHome', () => {
  it('is the Home route of the current workspace', () => {
    expect(isWorkspaceHome('/workspace/ws-1/home', 'ws-1')).toBe(true);
    expect(isWorkspaceHome('/workspace/ws-1/home/anything', 'ws-1')).toBe(true);
  });

  it('is not another route, another workspace, or a lookalike', () => {
    expect(isWorkspaceHome('/workspace/ws-1/chat', 'ws-1')).toBe(false);
    expect(isWorkspaceHome('/workspace/ws-2/home', 'ws-1')).toBe(false);
    expect(isWorkspaceHome('/workspace/ws-1/homepage', 'ws-1')).toBe(false);
    expect(isWorkspaceHome(null, 'ws-1')).toBe(false);
    expect(isWorkspaceHome('/workspace/ws-1/home', null)).toBe(false);
  });
});

describe('panelSectionOnPage', () => {
  it('shows no section column on Home, whatever the store holds', () => {
    for (const section of ['chat', 'files', 'apps', 'slides'] as const) {
      expect(panelSectionOnPage(section, '/workspace/ws-1/home', 'ws-1')).toBeNull();
    }
  });

  it('keeps the Workspaces panel the workspace mark opens over Home', () => {
    expect(panelSectionOnPage('workspaces', '/workspace/ws-1/home', 'ws-1')).toBe('workspaces');
  });

  it('leaves every other page alone', () => {
    expect(panelSectionOnPage('chat', '/workspace/ws-1/chat', 'ws-1')).toBe('chat');
    expect(panelSectionOnPage(null, '/workspace/ws-1/chat', 'ws-1')).toBeNull();
  });
});
