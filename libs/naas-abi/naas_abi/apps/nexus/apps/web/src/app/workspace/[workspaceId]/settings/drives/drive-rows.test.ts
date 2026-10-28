import { describe, expect, it } from 'vitest';
import { buildDriveRows, canToggleDrives, type DriveViewer } from './drive-rows';

const off = { platformOn: false, systemOn: false };
const rowIds = (viewer: DriveViewer, state = off, syncedFolders: { id: string; name: string; localPath: string }[] = []) =>
  buildDriveRows({ viewer, ...state, syncedFolders }).map((row) => row.id);
const row = (viewer: DriveViewer, id: string, state = off) =>
  buildDriveRows({ viewer, ...state, syncedFolders: [] }).find((r) => r.id === id);

const superadmin: DriveViewer = { role: 'member', isSuperadmin: true };
const owner: DriveViewer = { role: 'owner', isSuperadmin: false };
const admin: DriveViewer = { role: 'admin', isSuperadmin: false };
const member: DriveViewer = { role: 'member', isSuperadmin: false };

describe('drive rows visibility', () => {
  it('shows the platform and system drives to a superadmin, even when both are off', () => {
    expect(rowIds(superadmin)).toEqual(['my-drive', 'workspace', 'platform-drive', 'system-drive']);
    expect(rowIds({ role: null, isSuperadmin: true })).toEqual(['my-drive', 'workspace', 'platform-drive', 'system-drive']);
  });

  it('shows both rows to owners and admins', () => {
    for (const viewer of [owner, admin]) {
      expect(rowIds(viewer)).toEqual(['my-drive', 'workspace', 'platform-drive', 'system-drive']);
    }
  });

  it('shows a member the platform drive only when it is on, and never the system drive', () => {
    expect(rowIds(member)).toEqual(['my-drive', 'workspace']);
    expect(rowIds(member, { platformOn: true, systemOn: true })).toEqual(['my-drive', 'workspace', 'platform-drive']);
  });

  it('appends synced folders last', () => {
    const folders = [{ id: 'f1', name: 'Docs', localPath: '/docs' }];
    const rows = buildDriveRows({ viewer: member, ...off, syncedFolders: folders });
    expect(rows.at(-1)).toMatchObject({ id: 'f1', description: 'Synced folder · /docs', access: 'This browser' });
  });

  it('keeps the system drive access label for owners and admins', () => {
    expect(row(owner, 'system-drive')?.access).toBe('Owners & admins');
  });
});

describe('drive rows toggling', () => {
  it('lets only a superadmin toggle the platform and system drives', () => {
    expect(canToggleDrives(superadmin)).toBe(true);
    for (const viewer of [owner, admin, member]) expect(canToggleDrives(viewer)).toBe(false);

    for (const id of ['platform-drive', 'system-drive']) {
      expect(row(superadmin, id)?.toggleable).toBe(true);
      expect(row(owner, id)?.toggleable).toBe(false);
      expect(row(admin, id)?.toggleable).toBe(false);
    }
  });

  it('lets a superadmin untick an enabled drive', () => {
    const state = { platformOn: true, systemOn: true };
    expect(row(superadmin, 'platform-drive', state)).toMatchObject({ enabled: true, toggleable: true });
    expect(row(superadmin, 'system-drive', state)).toMatchObject({ enabled: true, toggleable: true });
  });

  it('keeps the locked drives enabled and never toggleable, whoever looks', () => {
    const folders = [{ id: 'f1', name: 'Docs', localPath: '/docs' }];
    for (const viewer of [superadmin, owner, admin, member]) {
      const locked = buildDriveRows({ viewer, ...off, syncedFolders: folders }).filter(
        (r) => r.id === 'my-drive' || r.id === 'workspace' || r.id === 'f1'
      );
      expect(locked).toHaveLength(3);
      for (const r of locked) {
        expect(r.enabled).toBe(true);
        expect(r.flag).toBeUndefined();
        expect(r.toggleable).toBe(false);
      }
    }
  });

  it('maps each drive to its workspace flag', () => {
    expect(row(superadmin, 'platform-drive')?.flag).toBe('platform_drive_enabled');
    expect(row(superadmin, 'system-drive')?.flag).toBe('system_drive_enabled');
  });
});
