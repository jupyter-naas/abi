import { describe, expect, it } from 'vitest';
import {
  clampSettingsNavWidth,
  SETTINGS_NAV_WIDTH_DEFAULT,
  SETTINGS_NAV_WIDTH_MAX,
  SETTINGS_NAV_WIDTH_MIN,
} from './settings-layout-nav';

describe('clampSettingsNavWidth', () => {
  it('keeps the width between the bounds', () => {
    expect(clampSettingsNavWidth(10)).toBe(SETTINGS_NAV_WIDTH_MIN);
    expect(clampSettingsNavWidth(5000)).toBe(SETTINGS_NAV_WIDTH_MAX);
    expect(clampSettingsNavWidth(300.6)).toBe(301);
  });

  it('falls back to the default for unreadable values', () => {
    expect(clampSettingsNavWidth(Number('abc'))).toBe(SETTINGS_NAV_WIDTH_DEFAULT);
  });
});
