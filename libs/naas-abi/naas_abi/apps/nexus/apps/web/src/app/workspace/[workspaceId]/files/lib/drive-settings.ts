import { PLATFORM_DRIVES_PATH } from '@/app/settings/drives/drives-model';
import { DRIVES_ITEM, holds, type PlatformActions } from '@/app/settings/lib/nav';

/** Files › Drive settings… opens Platform settings › Drives (the drives, File System…). */
export const DRIVE_SETTINGS_PATH = PLATFORM_DRIVES_PATH;

/**
 * Whether Files shows "Drive settings…": only to who may open Platform settings ›
 * Drives (`nexus:ListDrives` at the platform, from `GET /api/iam/admin/access`);
 * hidden until IAM has answered.
 */
export function driveSettingsShown(actions: PlatformActions | null): boolean {
  return holds(DRIVES_ITEM.needs, actions);
}
