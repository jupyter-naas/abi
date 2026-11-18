import { describe, expect, it } from 'vitest';

import { isWorkspaceHome, panelFromPathChange, panelSectionOnPage } from './home-route';

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

describe('panelFromPathChange', () => {
  const chat = '/workspace/ws-1/chat';
  const files = '/workspace/ws-1/files';

  it('keeps a closed column on refresh of the same page', () => {
    expect(
      panelFromPathChange({
        previousPath: null,
        pathname: chat,
        urlSection: 'chat',
        keepPanelClosed: false,
        currentPanel: null,
      }),
    ).toBe('keep');
  });

  it('opens the new section when navigating after the first paint', () => {
    expect(
      panelFromPathChange({
        previousPath: chat,
        pathname: files,
        urlSection: 'files',
        keepPanelClosed: false,
        currentPanel: null,
      }),
    ).toBe('files');
  });

  it('closes the column on Home, unless Workspaces is sitting over it', () => {
    expect(
      panelFromPathChange({
        previousPath: chat,
        pathname: '/workspace/ws-1/home',
        urlSection: 'home',
        keepPanelClosed: false,
        currentPanel: 'chat',
      }),
    ).toBeNull();
    expect(
      panelFromPathChange({
        previousPath: null,
        pathname: '/workspace/ws-1/home',
        urlSection: 'home',
        keepPanelClosed: false,
        currentPanel: 'workspaces',
      }),
    ).toBe('keep');
  });

  it('closes the column on /admin/ and when a launch asked to keep it closed', () => {
    expect(
      panelFromPathChange({
        previousPath: chat,
        pathname: '/workspace/ws-1/admin/users',
        urlSection: null,
        keepPanelClosed: false,
        currentPanel: 'chat',
      }),
    ).toBeNull();
    expect(
      panelFromPathChange({
        previousPath: chat,
        pathname: files,
        urlSection: 'files',
        keepPanelClosed: true,
        currentPanel: 'chat',
      }),
    ).toBeNull();
  });
});
