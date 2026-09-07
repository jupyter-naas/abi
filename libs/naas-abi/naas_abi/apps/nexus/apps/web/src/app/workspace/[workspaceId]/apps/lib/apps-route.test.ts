import { describe, expect, it } from 'vitest';

import { appsPath, nextAppsRestoreUrl } from './apps-route';

const WS_A = 'ws-43114186ff0d';
const WS_B = 'ws-valeo';
const ARMOR = 'operations.audit.armor:armor';

describe('appsPath', () => {
  it('points at the section home', () => {
    expect(appsPath(WS_A)).toBe(`/workspace/${WS_A}/apps`);
  });

  it('encodes the open app id', () => {
    expect(appsPath(WS_A, ARMOR)).toBe(
      `/workspace/${WS_A}/apps?open=${encodeURIComponent(ARMOR)}`,
    );
  });
});

describe('nextAppsRestoreUrl', () => {
  it('restores last-open for the workspace in the URL', () => {
    expect(
      nextAppsRestoreUrl({
        urlWorkspaceId: WS_A,
        storeWorkspaceId: WS_A,
        searchOpen: null,
        savedOpen: ARMOR,
      }),
    ).toBe(appsPath(WS_A, ARMOR));
  });

  it('does not rewrite to the previous workspace mid-switch', () => {
    // URL already moved to Valeo; store still has Next Gen. Restoring from the
    // store id sent the user back to Next Gen with ?open=armor.
    expect(
      nextAppsRestoreUrl({
        urlWorkspaceId: WS_B,
        storeWorkspaceId: WS_A,
        searchOpen: null,
        savedOpen: ARMOR,
      }),
    ).toBeNull();
  });

  it('does not restore from a saved id that belongs to another workspace key', () => {
    expect(
      nextAppsRestoreUrl({
        urlWorkspaceId: WS_B,
        storeWorkspaceId: WS_B,
        searchOpen: null,
        savedOpen: null,
      }),
    ).toBeNull();
  });

  it('leaves an explicit ?open= alone', () => {
    expect(
      nextAppsRestoreUrl({
        urlWorkspaceId: WS_A,
        storeWorkspaceId: WS_A,
        searchOpen: ARMOR,
        savedOpen: ARMOR,
      }),
    ).toBeNull();
  });

  it('skips restore after a workspace switch', () => {
    expect(
      nextAppsRestoreUrl({
        urlWorkspaceId: WS_B,
        storeWorkspaceId: WS_B,
        searchOpen: null,
        savedOpen: ARMOR,
        skipRestore: true,
      }),
    ).toBeNull();
  });

  it('waits until a workspace id is in the URL', () => {
    expect(
      nextAppsRestoreUrl({
        urlWorkspaceId: null,
        storeWorkspaceId: WS_A,
        searchOpen: null,
        savedOpen: ARMOR,
      }),
    ).toBeNull();
  });
});
