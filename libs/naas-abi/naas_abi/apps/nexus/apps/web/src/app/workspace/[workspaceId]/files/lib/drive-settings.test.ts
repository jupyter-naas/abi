import { describe, expect, it } from 'vitest';

import { DRIVE_SETTINGS_PATH, driveSettingsShown } from './drive-settings';

describe('Files › Drive settings…', () => {
  it('opens Platform settings › Drives', () => {
    expect(DRIVE_SETTINGS_PATH).toBe('/settings/drives');
  });

  it('is shown only to who holds nexus:ListDrives at the platform', () => {
    expect(driveSettingsShown({ 'nexus:ListDrives': true })).toBe(true);
    expect(driveSettingsShown({ 'nexus:ListDrives': false, 'nexus:ReadSystem': true })).toBe(false);
    expect(driveSettingsShown({})).toBe(false);
  });

  it('is hidden until IAM has answered', () => {
    expect(driveSettingsShown(null)).toBe(false);
  });
});
